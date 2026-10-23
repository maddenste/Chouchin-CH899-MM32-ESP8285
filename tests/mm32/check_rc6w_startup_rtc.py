"""Bounded startup RTC precheck recovery, against actual ARM binaries."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.analysis_deps'))
from check_rc6s_rtc import Tests as Prior
from check_rc6v_fixed_lap import Tests as OriginalV

WIRE=b'+TIME:Thu Oct 22 13:04:00 2026 +0100 10:00 30\r\n'

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6w/build/MM32SPIN05PF_FIXED_LAP_RC6W_20261022.axf'
    signature=0x4d505280

    def first_time(self):
        self.tick()
        # Store the event without running main-loop RTC I/O before injecting
        # the startup condition; feed() would process it immediately.
        for b in WIRE:self.call('uart_probe_consume',b)
        self.cpu.mem_write(0x40004408,bytes(4))

    def test_rc6v_reproduces_zero_stage_zero_recovery_failure(self):
        OriginalV.setUpClass();old=OriginalV();old.setUp();old.tick()
        for b in WIRE:old.call('uart_probe_consume',b)
        old.bus.force_busy=True
        self.assertEqual(old.result('rtc_motion_set',old.symbols['uart_probe_time_event']),0)
        self.assertEqual(old.word('wifi_rtc',4),0)
        self.assertEqual(old.word('wifi_rtc',5),0)
        self.assertEqual(old.word('rtc_recovery'),0)
        self.assertEqual(old.word('seconds_log',56),0)

    def test_slave_held_sda_recovers_then_verifies_calendar(self):
        self.first_time();before=self.bus.data[:]
        self.bus.force_busy=True
        original=self.bus.write;release_at=self.bus.clocks+9
        def release_after_nine(address,value):
            original(address,value)
            if self.bus.clocks>=release_at:self.bus.force_busy=False
        self.bus.write=release_after_nine
        self.assertEqual(self.result('rtc_motion_set',self.symbols['uart_probe_time_event']),1)
        self.assertEqual(self.word('wifi_rtc',2),2)
        self.assertEqual(self.word('wifi_rtc',15),1)
        self.assertEqual(self.bus.crh&255,0x44)
        self.assertEqual(self.word('rtc_recovery'),2)
        self.assertEqual(self.word('rtc_recovery',1),18)
        for i in (0,1,9,10,11,12,13,14,15):self.assertEqual(self.bus.data[i],before[i],i)

    def test_permanently_held_sda_fails_bounded_and_releases_pins(self):
        self.first_time();self.bus.force_busy=True
        self.assertEqual(self.result('rtc_motion_set',self.symbols['uart_probe_time_event']),0)
        self.assertEqual(self.word('wifi_rtc',5),3)
        self.assertEqual(self.word('rtc_recovery'),1)
        self.assertEqual(self.word('rtc_recovery',1),9)
        self.assertEqual(self.bus.crh&255,0x44)
        self.assertEqual(self.bus.calendar_writes,[])

    def test_permanently_held_scl_fails_bounded_and_releases_pins(self):
        self.first_time();self.bus.stuck_at=0
        self.assertEqual(self.result('rtc_motion_set',self.symbols['uart_probe_time_event']),0)
        self.assertEqual(self.word('wifi_rtc',5),7)
        self.assertEqual(self.word('rtc_recovery'),1)
        self.assertEqual(self.bus.crh&255,0x44)
        self.assertEqual(self.bus.calendar_writes,[])

    def test_wrong_pin_modes_are_not_overridden(self):
        self.first_time();self.bus.crh=(self.bus.crh&~255)|0x66
        self.assertEqual(self.result('rtc_motion_set',self.symbols['uart_probe_time_event']),0)
        self.assertEqual(self.word('wifi_rtc',5),8)
        self.assertEqual(self.word('rtc_recovery'),0)
        self.assertEqual(self.bus.calendar_writes,[])

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names += ['test_counter_driver_preserves_calendar_alarm_clkout_and_pauses',
              'test_compact_calendar_failures_restore_bus',
              'test_foreign_timer_interrupt_is_not_taken_over',
              'test_calendar_set_pauses_counter_and_reseeds',
              'test_uart_receives_during_calendar_write_with_compact_storage']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
