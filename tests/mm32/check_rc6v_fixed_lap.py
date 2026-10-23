"""RC6S-based controlled test: latch Stop2Go timer counts at first launch."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.analysis_deps'))
from check_rc6s_stack import Tests as Prior

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6v/build/MM32SPIN05PF_FIXED_LAP_RC6V_20261022.axf'
    signature=0x4d50527f

    def pair(self):return self.word('minute_log',181),self.word('minute_log',182)

    def test_first_lap_uses_exact_rc6s_formula(self):
        for mode in (2,3):
            for rate in (50000,62500,62858,75000):
                self.setUp()
                self.setword('rtc_pace',1,rate-1)
                self.setword('release_state',1,20)
                self.start_pwm(mode)
                cycles=rate*1024+20
                expected=((cycles*123+131072)//262144,2*((cycles*3+8192)//16384))
                self.assertEqual(self.pair(),expected)
                self.assertEqual((self.word('seconds_log',56),self.word('seconds_log',57)),expected)

    def test_second_lap_keeps_first_pair_despite_new_calibration(self):
        self.start_pwm(3)
        first=self.pair()
        self.complete_lap()
        self.setword('rtc_pace',1,62857)
        self.setword('release_state',1,20)
        self.put(5,0)
        self.setword('rtc_boundary',0,1)
        self.tick()
        self.assertEqual(self.get(3),0)
        self.assertTrue(self.gate())
        self.assertEqual(self.pair(),first)
        self.assertEqual(self.word('minute_log',184),(62858*1024+20+1024)//2048)
        self.complete_lap()
        self.assertEqual(self.word('seconds_log',255),2)
        self.assertEqual(self.bt_count,960)
        self.assertEqual(self.pad,[False,False])
        self.assertFalse(self.overlaps)
        self.assertEqual(self.get(3),0)

    def test_cached_pair_survives_mode_change_but_does_not_affect_normal(self):
        self.start_pwm(3);first=self.pair()
        self.call('fine_stop')
        self.setword('rtc_pace',1,63107)
        self.setword('release_state',1,99)
        self.setword('minute_log',189,0)
        self.setword('minute_log',188,0)
        self.call('fine_runtime_tick',self.get(4),7,0)
        cycles=63108*1024+99
        self.assertEqual(self.pair(),((cycles+1024)//2048,2*((cycles*3+8192)//16384)))
        self.call('fine_stop')
        self.setword('minute_log',189,2)
        self.setword('minute_log',188,2)
        self.call('fine_runtime_tick',self.get(4),7,0)
        self.assertEqual(self.pair(),first)
        self.assertEqual(self.get(3),0)

    def test_rec_rehoming_clears_first_lap_cache(self):
        self.start_pwm(3)
        self.assertNotEqual(self.word('seconds_log',56),0)
        self.setword('minute_log',227,2)
        self.setword('minute_log',229,1)
        for _ in range(32):
            self.tick()
            if self.get(2)==1:break
        self.assertEqual(self.get(2),1)
        self.assertEqual((self.word('seconds_log',56),self.word('seconds_log',57)),(0,0))
        self.assertEqual(self.get(3),0)

if __name__=='__main__':
    names=[name for name in Tests.__dict__ if name.startswith('test_')]
    names += ['test_all_modes_select_hardware_pwm',
              'test_normal_calibration_changes_only_safe_gap_without_extra_counts',
              'test_stop2go_changes_back_to_normal_hardware_pwm',
              'test_sleep_closes_lease_without_reply_or_motor_change',
              'test_complete_time_is_preserved_and_processed_before_poweroff',
              'test_missing_reference_still_stops',
              'test_timer_stall_watchdog_releases_coils']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
