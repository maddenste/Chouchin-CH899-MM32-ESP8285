"""Focused ARM execution checks for M.SET while correction owns the hands."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.analysis_deps'))
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP
from check_rc6s_stack import Tests as Prior

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6t/build/MM32SPIN05PF_MANUAL_WAKE_RC6T_20261022.axf'
    signature=0x4d50527d

    def poll_web(self):
        # buttons_poll/manual_web_poll are inlined in the distributed binary.
        # Execute that real caller, stopping before unrelated RTC/daily I/O.
        stop={self.symbols[n]&~1 for n in ('quartz_poll','rtc_pace_poll','daily_poll')}
        saved_sp=self.cpu.reg_read(UC_ARM_REG_SP)
        hook=self.cpu.hook_add(UC_HOOK_CODE,
            lambda cpu,address,size,user:cpu.emu_stop() if address in stop else None)
        try:self.call('parallel_poll_once')
        finally:
            self.cpu.hook_del(hook)
            self.cpu.reg_write(UC_ARM_REG_SP,saved_sp)

    def pending(self,phase=1,stage=7,awake=0):
        self.start_pwm(3)
        self.setword('parallel_log',2,stage)
        self.setword('daily_log',0,7 if phase==1 else 3)
        self.setword('daily_log',13,phase)
        self.setword('minute_log',211,awake)
        self.setword('minute_log',217,0)
        self.setword('minute_log',227,1) # Qualified M.SET action.

    def test_mset_wakes_during_each_correction_stage_without_motor_changes(self):
        for phase,stage in ((1,7),(2,7),(3,10),(3,11)):
            with self.subTest(phase=phase,stage=stage):
                self.setUp();self.pending(phase,stage)
                daily=bytes(self.cpu.mem_read(self.symbols['daily_log'],64))
                waveform=(self.reg(0),self.reg(0x2c),self.reg(0x38),self.reg(0x3c),self.counter)
                self.poll_web()
                self.assertEqual(self.word('minute_log',211),1)
                self.assertEqual(self.word('minute_log',217),1)
                self.assertEqual(self.word('minute_log',237),1)
                self.assertEqual(self.word('minute_log',227),0)
                self.assertEqual(self.word('minute_log',228),0) # No new daily acquisition.
                self.assertEqual(self.get(28),4) # Red/requesting indication now.
                self.assertEqual(self.get(2),stage)
                self.assertEqual(bytes(self.cpu.mem_read(self.symbols['daily_log'],64)),daily)
                self.assertEqual(waveform,(self.reg(0),self.reg(0x2c),self.reg(0x38),self.reg(0x3c),self.counter))

    def test_already_awake_mset_keeps_uart_state_and_starts_led(self):
        self.pending(awake=1)
        self.setword('minute_log',157,1) # Obsolete SLEEP from old session.
        self.feed(b'+TI')
        self.poll_web()
        self.assertEqual(self.word('minute_log',157),0)
        self.assertEqual(self.word('line_length'),3) # No destructive radio reinit.
        self.assertEqual(self.get(28),4)

    def test_manual_user_transmits_during_wait_and_snapshot_stays_frozen(self):
        self.pending()
        tx=[]
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,
            lambda cpu,access,address,size,value,user:tx.append(value),
            begin=0x40004400,end=0x40004400)
        self.cpu.mem_write(0x40004408,b'\x01\x00\x00\x00') # UART TX ready.
        address=self.symbols['uart_probe_time_event']
        snapshot=bytes(self.cpu.mem_read(address,20))
        for _ in range(5):self.poll_web()
        self.assertEqual(bytes(tx),b'USER\n')
        self.feed(b'+TIME:Thu Oct 22 11:55:30 2026 +0100 10:00 30\r\n')
        self.assertEqual(bytes(self.cpu.mem_read(address,20)),snapshot)
        self.assertEqual(self.word('daily_log',0),7)
        self.assertEqual(self.word('daily_log',13),1)

    def test_clean_still_waits_and_rec_still_wins(self):
        self.pending()
        self.setword('minute_log',227,3)
        self.poll_web()
        self.assertEqual(self.word('minute_log',227),3)
        self.assertEqual(self.word('minute_log',211),0)
        self.setword('minute_log',229,1)
        self.setword('minute_log',227,1)
        self.poll_web()
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.word('minute_log',217),0)

    def test_red_flashes_and_correction_finish_keeps_manual_lease(self):
        self.pending()
        self.poll_web()
        self.call('parallel_leds_tick',48)
        self.assertEqual(self.raw(0x48000010),1<<31)
        self.call('parallel_leds_tick',56)
        self.assertEqual(self.raw(0x48000010),1<<15)
        self.call('daily_finish',3,845985000)
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(self.word('minute_log',217),1)
        self.assertEqual(self.word('daily_log',13),1)
        self.assertEqual(self.get(28),4)

    def test_explicit_sleep_can_close_new_manual_session_during_correction(self):
        self.pending()
        self.poll_web()
        self.feed(b'SLEEP\r\n')
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.word('minute_log',217),0)
        self.assertEqual(self.word('daily_log',0),7)
        self.assertEqual(self.word('daily_log',13),1)

if __name__=='__main__':
    names=[name for name in Tests.__dict__ if name.startswith('test_')]
    names += ['test_sleep_closes_lease_without_reply_or_motor_change',
              'test_complete_time_is_preserved_and_processed_before_poweroff',
              'test_clean_defers_sleep_and_new_wake_discards_old_request',
              'test_native_rec_drain_enters_homing',
              'test_all_modes_select_hardware_pwm',
              'test_sampled_lap_without_any_seconds_irq']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
