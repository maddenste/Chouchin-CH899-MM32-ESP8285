"""Focused RC6K real-ARM calendar/countdown interleaving regression."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.analysis_deps'))
from check_rc6j_quartz import Tests as Prior
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6k/build/MM32SPIN05PF_QUARTZ_REFERENCE_RC6K_20261021.axf'
    signature=0x4d505274

    def test_bad_reads_and_long_gap_fall_back_without_stopping_motor(self):
        self.mode_run(3);self.start_counter()
        rate=self.word('rtc_pace',1)
        for _ in range(3):self.call('quartz_sample',100,0,200000)
        self.assertEqual(self.q(1),3)
        self.assertEqual(self.word('rtc_pace',1),rate)
        self.assertEqual(self.get(3),0)
        # A valid read after a scheduling gap reseeds; it is not an I2C error.
        self.setUp();self.start_counter()
        for i in range(8):
            self.call('quartz_sample',100,i*500000,10000)
        self.assertEqual(self.q(1),1)
        self.assertEqual(self.q(36),7)
        self.assertEqual(self.q(11),1)
        self.assertEqual(self.q(7),0)
        self.assertEqual(self.q(14),0)
        self.assertEqual(self.q(21),6)

    @staticmethod
    def calendar_and_counter(t,loops=160):
        t.tick();t.seed()
        for i in range(40):t.q(i,0)
        t.bus.data[14:16]=[3,255]
        cycles=[0];origin=[0];enabled=[False]
        tx=t.bus.tx_level
        def live_tx():
            if t.bus.index==0 and t.bus.bits==0 and t.bus.data[14]&128:
                t.bus.data[15]=255-((cycles[0]-origin[0])*4096//8000000)%255
            tx()
        t.bus.tx_level=live_tx
        def timebase(*args):
            # Stress model: two HCLK cycles per ARM instruction, plus explicit
            # idle gaps. Not a cycle-accurate silicon/IRQ/motor simulation.
            cycles[0]+=2
            t.put(4,cycles[0]//62500)
            on=bool(t.bus.data[14]&128)
            if on and not enabled[0]:origin[0]=cycles[0]
            enabled[0]=on
        def hclk(cpu,access,address,size,value,user):
            cpu.mem_write(address,(cycles[0]&0xffffffff).to_bytes(4,'little'))
        a=t.cpu.hook_add(UC_HOOK_CODE,timebase)
        b=t.cpu.hook_add(UC_HOOK_MEM_READ,hclk,begin=0x40000024,end=0x40000024)
        t.cpu.ctl_remove_cache(0x08000000,0x08008000)
        try:
            for _ in range(loops):
                t.call('quartz_poll')
                t.result('rtc_motion_read',0x20000f80,0x20000f84,0x20000f88)
                t.call('quartz_poll')
                cycles[0]+=125000
                if t.q(1)==3 or t.q(14)>=2:break
        finally:
            t.cpu.hook_del(a);t.cpu.hook_del(b);t.bus.tx_level=tx
        return t.q(1),t.q(14),t.q(36),cycles[0]

    def test_rc6j_reproduces_fallback_with_interleaved_calendar(self):
        Prior.setUpClass();old=Prior();old.setUp()
        state,updates,resets,cycles=self.calendar_and_counter(old)
        self.assertEqual((state,updates),(3,0))
        self.assertEqual(old.q(21),3)
        print('RC6J calendar coexistence reproduced: fallback before calibration')

    def test_calendar_counter_coexist_and_complete_calibrations(self):
        state,updates,resets,cycles=self.calendar_and_counter(self)
        self.assertEqual(state,1)
        self.assertGreaterEqual(updates,2)
        self.assertLess(abs(self.q(16)-64000000),640000)
        self.assertEqual(self.q(36),0)
        self.assertEqual(self.get(3),0)
        print('RC6K calendar coexistence:',updates,'calibrations;',cycles/8000000,'model seconds; max gap',self.q(34))

if __name__=='__main__':
    names=['test_rc6j_reproduces_fallback_with_interleaved_calendar',
           'test_calendar_counter_coexist_and_complete_calibrations',
           'test_bad_reads_and_long_gap_fall_back_without_stopping_motor',
           'test_new_build_accepts_counter_advancing_during_i2c',
           'test_timestamped_pair_accepts_valid_interrupt_delay_over_old_limit',
           'test_counter_driver_preserves_calendar_alarm_clkout_and_pauses',
           'test_foreign_timer_interrupt_is_not_taken_over',
           'test_rate_calibration_reload_wrap_and_motor_unchanged',
           'test_clock_rates_and_fractional_precision',
           'test_calendar_set_pauses_counter_and_reseeds',
           'test_poll_uses_actual_i2c_counter_and_tim2_without_touching_tim3',
           'test_shared_grid_four_modes']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
