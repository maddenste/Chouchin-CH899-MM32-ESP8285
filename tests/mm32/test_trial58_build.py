"""Trial57 plus alternating existing-cadence REC homing indication."""
import unittest
import test_trial57_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_REC_HOME_LEDS_TRIAL58_20261010.axf')
    signature=0x4d503538
    defines=prior.Tests.defines+['-DREC_HOME_LEDS']

    def test_rec_led_cadence_alternates_without_overlap(self):
        self.call('parallel_leds_rec_start',100)
        for elapsed in range(256):
            begin=len(self.writes)
            self.call('parallel_leds_tick',100+elapsed)
            writes=self.writes[begin:]
            red=any(a==0x48000010 and v==1<<31 for a,v in writes)
            blue=any(a==0x48000410 and v==1<<19 for a,v in writes)
            flash=elapsed%64 in range(48,56)
            self.assertEqual(red,flash and elapsed//64%2==0)
            self.assertEqual(blue,flash and elapsed//64%2==1)
            self.assertFalse(red and blue)

    def test_rec_starts_leds_and_radio_shutdown_preserves_phase(self):
        self.running(); self.hold(1)
        self.assertEqual(self.get(28),5)
        origin=self.get(29)
        self.call('parallel_leds_power_down',self.get(4),0)
        self.assertEqual((self.get(28),self.get(29)),(5,origin))
        self.assertFalse(self.output&16)

    def test_fault_overrides_rec_led_pattern(self):
        self.tick(); self.call('parallel_leds_rec_start',self.get(4))
        self.call('fail',4)
        self.assertEqual((self.get(2),self.get(28)),(6,0))

    def test_rec_leds_stop_only_after_both_home_and_remain_off(self):
        self.put(1,1); self.tick(); self.hold(1)
        saw_separate=False
        for _ in range(12000):
            high=0
            if self.get(19)==1:
                high=int(246<=self.word('seconds_log',5)+1<=262)
            elif self.get(19)==2:
                high=int(self.word('minute_log',5)+1>=13)
            self.tick(high)
            if self.get(7)!=self.get(8):
                saw_separate=True; self.assertEqual(self.get(28),5)
            if self.get(2)==12: break
        self.assertTrue(saw_separate)
        self.assertEqual((self.get(2),self.get(3),self.get(28)),(12,0,0))
        self.assertEqual(self.get(7)+self.get(8),2)
        self.hold(2); self.hold(3)
        self.assertEqual((self.get(2),self.get(28)),(12,0))

def load_tests(loader,tests,pattern):
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names += ['test_precise_minute_offset_across_six_entry_phases',
              'test_seconds_homing_and_runtime_use_same_offset',
              'test_scheduled_matching_time_keeps_blue_confirmation_on_recovery',
              'test_button_rec_can_park_without_time_and_locks_everything',
              'test_button_mset_works_before_startup_homing_completes',
              'test_button_clean_exact_protocol_and_ack_while_motors_run',
              'test_rec_precedes_scheduled_recovery',
              'test_recovery_preserves_settings_and_completes_real_homing']
    return unittest.TestSuite(Tests(n) for n in names)

if __name__=='__main__': unittest.main()
