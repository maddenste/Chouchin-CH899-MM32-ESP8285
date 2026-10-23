"""RTC byte-storage, UART coexistence and reset checks for RC6S."""
import unittest
from pathlib import Path
from check_rc6k_quartz import Tests as Prior
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6s/build/MM32SPIN05PF_STACK_RC6S_20261022.axf'
    signature=0x4d50527c

    def test_compact_calendar_failures_restore_bus(self):
        for nack in range(1,7):
            self.setUp(); self.tick(); self.seed()
            self.bus.nack_at=len(self.bus.received)+nack
            self.assertEqual(self.result('rtc_motion_set',self.symbols['uart_probe_time_event']),0)
            self.assertEqual(self.bus.crh&255,0x44)

    def test_real_reset_initializes_relocated_state_and_preserves_stack_reservation(self):
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
        from intelhex import IntelHex
        flash=IntelHex(str(self.artifact.with_suffix('.hex')))
        self.assertEqual(self.symbols['pulse_diag'],0x20000ae0)
        self.assertLessEqual(self.symbols['Image$$RW_IRAM1$$ZI$$Limit'],0x20000ae0)
        for pattern in (1,2,0xa5,0xff):
            cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
            cpu.mem_map(0x08000000,0x10000); cpu.mem_map(0x20000000,0x1000)
            cpu.mem_write(0x20000000,bytes([pattern])*4096)
            for start,end in flash.segments():
                cpu.mem_write(start,bytes(flash.tobinarray(start=start,end=end-1)))
            reached=[]
            def stop_at_main(cpu,address,size,user):
                if address==(self.symbols['main']&~1):
                    reached.append(True); cpu.emu_stop()
            cpu.hook_add(UC_HOOK_CODE,stop_at_main)
            cpu.reg_write(UC_ARM_REG_SP,0x20001000)
            cpu.emu_start(self.symbols['Reset_Handler'],0x08008000,count=100000)
            self.assertTrue(reached)
            self.assertEqual(bytes(cpu.mem_read(0x20000ae0,160)),bytes(160))
            self.assertEqual(bytes(cpu.mem_read(0x20000b80,256)),bytes([pattern])*256)

    def test_uart_receives_during_calendar_write_with_compact_storage(self):
        self.tick(); self.seed()
        event=self.symbols['uart_probe_time_event']
        snapshot=bytes(self.cpu.mem_read(event,20))
        original=self.bus.data[:]
        before_time=self.word('uart_probe_good_time')
        before_tick=self.word('uart_probe_good_tick')
        # Freeze the accepted correction while the radio publishes another
        # complete TIME and then requests sleep. No fake parser acceptance.
        self.setword('daily_log',0,7)
        payload=list(b'+TICK\r\n+TIME:Thu Oct 22 09:35:30 2026 +0100 10:00 30\r\nSLEEP\r\n')
        delivered=[]; low=[0x20001000]
        def reads(cpu,access,address,size,value,user):
            if address==0x40004408:
                cpu.mem_write(address,(2 if payload else 0).to_bytes(4,'little'))
            elif address==0x40004404 and payload:
                b=payload.pop(0); delivered.append(b)
                cpu.mem_write(address,b.to_bytes(4,'little'))
        def stack(cpu,address,size,user):
            low[0]=min(low[0],cpu.reg_read(UC_ARM_REG_SP))
        h=self.cpu.hook_add(UC_HOOK_MEM_READ,reads,begin=0x40004404,end=0x40004408)
        sh=self.cpu.hook_add(UC_HOOK_CODE,stack)
        self.cpu.mem_write(0x40004418,(1).to_bytes(4,'little'))
        try:
            self.assertEqual(self.result('rtc_motion_set',event),1)
        finally:
            self.cpu.hook_del(h); self.cpu.hook_del(sh)
        self.assertFalse(payload)
        self.assertEqual(bytes(self.cpu.mem_read(event,20)),snapshot)
        self.assertEqual(self.word('uart_probe_good_time'),before_time)
        self.assertEqual(self.word('uart_probe_good_tick'),before_tick+1)
        self.assertEqual(self.word('minute_log',157),1)
        self.assertEqual(self.word('uart_probe_overflow'),0)
        for i in (0,1,9,10,11,12,13):
            self.assertEqual(self.bus.data[i],original[i],i)
        self.assertEqual(self.bus.data[14],self.q(4)&127)
        self.assertEqual(self.bus.data[15],self.q(5))
        self.assertEqual(self.word('wifi_rtc',2),2)
        self.assertGreaterEqual(low[0],0x20000b80)
        print('Direct RTC/UART observed software stack:',0x20001000-low[0],'bytes')

if __name__=='__main__':
    names=['test_counter_driver_preserves_calendar_alarm_clkout_and_pauses',
           'test_compact_calendar_failures_restore_bus',
           'test_real_reset_initializes_relocated_state_and_preserves_stack_reservation',
           'test_foreign_timer_interrupt_is_not_taken_over',
           'test_calendar_set_pauses_counter_and_reseeds',
           'test_calendar_counter_coexist_and_complete_calibrations',
           'test_uart_receives_during_calendar_write_with_compact_storage']
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not r.wasSuccessful())
