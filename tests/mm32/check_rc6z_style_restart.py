"""Native ARM restart-on-style-change checks; timer model, not live hardware."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.analysis_deps'))
from check_rc6x_phase_resume import Tests as PhasePrior
from check_rc6t_manual_wake import Tests as ButtonPrior
from check_rc6w_startup_rtc import Tests as RTCPrior
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP

ARTIFACT=Path(__file__).parent/'release_candidate_rc6z/build/MM32SPIN05PF_STYLE_RESTART_RC6Z_20261022.axf'

class Tests(PhasePrior):
    artifact=ARTIFACT
    signature=0x4d505283

    def setUp(self):
        super().setUp()
        # The inherited motor model tracks BSRR, but radio_off uses BRR.
        # Model that documented GPIO write as well for the ESP-low checks.
        def brr(cpu,access,address,size,value,user):
            self.output &= ~(value & 65535)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,brr,begin=0x48000414,end=0x48000414)

    def start_pwm(self,mode=3):
        super().start_pwm(mode)
        self.setword('minute_log',188,1) # Fixture bypasses startup TIME.

    def wire(self,style=None,parking=0):
        suffix='' if style is None else ' '+str(style)+str(parking)
        data=(' +TIME:Thu Oct 22 14:20:30 2026 +0100 10:00'+suffix+'\r\n').lstrip().encode()
        for b in data:self.call('uart_probe_consume',b)

    def test_first_time_latches_each_style_and_duplicates_do_not_restart(self):
        for style in range(4):
            self.setUp();self.setword('minute_log',188,0);self.setword('minute_log',189,0)
            self.wire(style)
            self.assertEqual(self.word('minute_log',188),1)
            self.assertEqual(self.word('minute_log',189),style)
            for _ in range(3):self.wire(style)
            self.assertEqual(self.word('minute_log',190),0)

    def test_all_twelve_style_changes_request_reset_without_live_switch(self):
        for old in range(4):
            for new in range(4):
                if old==new:continue
                self.setUp();self.start_pwm(old)
                self.wire(new)
                self.assertEqual(self.word('minute_log',190),1,(old,new))
                self.assertEqual(self.word('minute_log',189),old)
                self.assertEqual(self.get(3),0)

    def test_same_style_other_settings_and_legacy_time_do_not_reset(self):
        self.start_pwm(3)
        for parking in (0,1,2):
            self.wire(3,parking)
            self.assertEqual(self.word('minute_log',190),0)
        self.wire()
        self.assertEqual(self.word('minute_log',190),0)
        self.assertEqual(self.word('minute_log',189),3)

    def test_legacy_first_time_latches_default_and_later_change_restarts(self):
        self.setword('minute_log',188,0);self.setword('minute_log',189,0)
        self.wire()
        self.assertEqual(self.word('minute_log',188),1)
        self.assertEqual(self.word('minute_log',189),0)
        self.wire(3)
        self.assertEqual(self.word('minute_log',190),1)
        self.assertEqual(self.word('minute_log',189),0)

    def reset_capture(self):
        events=[]
        def write(cpu,access,address,size,value,user):
            if address==0xe000ed0c:
                events.append((value,self.get(4),tuple(self.pad),self.word('minute_active'),self.output&16))
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,write)
        return events

    def test_powered_pulses_finish_then_esp_off_then_exactly_one_reset(self):
        self.start_pwm(3)
        self.setword('minute_log',211,1)
        self.output|=16
        self.setword('request_pulses',0,6);self.call('pwm_minutes_queue')
        self.advance_timer(8000)
        self.assertTrue(any(self.pad));self.assertEqual(self.word('minute_active'),1)
        pending=self.raw(0x40014034)
        self.put(5,20)
        events=self.reset_capture();self.wire(0)
        first_edges=list(self.pad_edges)
        off_tick=None
        for _ in range(160):
            self.tick()
            self.assertEqual(self.get(3),0)
            if self.word('minute_log',190)==2 and off_tick is None:
                off_tick=self.get(4)
                self.assertFalse(any(self.pad));self.assertEqual(self.word('minute_active'),0)
                self.assertEqual(self.output&16,0)
            if events:break
        self.assertEqual(len(events),1)
        value,tick,pad,minute,esp=events[0]
        self.assertEqual(value,0x05fa0004)
        self.assertEqual((pad,minute,esp),((False,False),0,0))
        self.assertGreaterEqual(tick-off_tick,16)
        # Finish through hardware TIM14 compare, not by truncating its drive.
        self.assertGreaterEqual(self.mt_count,pending)
        self.assertEqual(self.get(13),1) # Remaining five minute pulses cancelled.
        for _ in range(32):self.tick()
        self.assertEqual(len(events),1)
        self.assertEqual(self.get(5),20) # No need to reach 00.
        self.assertFalse(self.overlaps)

    def test_pending_correction_snapshot_is_not_replaced(self):
        self.start_pwm(3);self.setword('daily_log',0,7);self.setword('daily_log',13,1)
        addr=self.symbols['uart_probe_time_event'];snapshot=bytes(self.cpu.mem_read(addr,20))
        self.wire(0)
        self.assertEqual(self.word('minute_log',190),1)
        self.assertEqual(bytes(self.cpu.mem_read(addr,20)),snapshot)
        self.assertEqual(self.word('daily_log',13),1)
        for _ in range(3):self.wire(0)
        self.assertEqual(self.word('minute_log',190),1)

    def test_fresh_boot_accepts_new_saved_style_without_another_restart(self):
        self.start_pwm(3);self.wire(0)
        self.assertEqual(self.word('minute_log',190),1)
        # Execute this binary's actual C-runtime reset entry. AIRCR itself is
        # recorded, not implemented by Unicorn; peripheral reset is not modeled.
        self.cpu.reg_write(UC_ARM_REG_SP,0x20001000)
        self.cpu.emu_start(self.symbols['Reset_Handler'],0x08007f00,count=200000)
        self.assertEqual(self.word('minute_log',188),0)
        self.assertEqual(self.word('minute_log',190),0)
        self.wire(0);self.wire(0)
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',189),self.word('minute_log',190)),(1,0,0))

    def test_drain_timeout_faults_instead_of_resetting_live_motor(self):
        self.start_pwm(3);self.advance_timer(16000);self.assertTrue(any(self.pad))
        events=self.reset_capture();self.wire(0)
        self.call('mode_restart_service',self.get(4)+129)
        self.assertEqual(self.get(3),10)
        self.assertEqual(events,[])
        self.assertEqual(self.pad,[False,False])

    def test_coarse_homing_pulse_finishes_before_reset(self):
        self.tick()
        self.setword('minute_log',188,0);self.wire(3)
        self.setword('second_active',0,1);self.setword('minute_active',0,1)
        self.setword('minute_end',0,self.get(4)+4)
        self.put(18,self.get(4))
        self.wire(0)
        self.assertEqual(self.word('minute_log',190),1)
        events=self.reset_capture()
        for _ in range(40):
            self.tick()
            if events:break
        self.assertEqual(len(events),1)
        self.assertEqual(events[0][2:4],((False,False),0))

class ButtonTests(ButtonPrior):
    artifact=ARTIFACT
    signature=0x4d505283

class RTCTests(RTCPrior):
    artifact=ARTIFACT
    signature=0x4d505283

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names += ['test_three_revolutions_in_both_stop_modes',
              'test_release_does_not_write_pwm_or_motor_gpio_registers',
              'test_normal_waveform_continues_across_three_hardware_wraps_without_cpu',
              'test_missing_reference_still_stops',
              'test_timer_stall_watchdog_releases_coils']
    buttons=['test_mset_wakes_during_each_correction_stage_without_motor_changes',
             'test_sleep_closes_lease_without_reply_or_motor_change']
    rtc=['test_slave_held_sda_recovers_then_verifies_calendar']
    suite=unittest.TestSuite([Tests(n) for n in names]+[ButtonTests(n) for n in buttons]+[RTCTests(n) for n in rtc])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
