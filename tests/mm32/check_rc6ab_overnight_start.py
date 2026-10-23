"""One normal initial overnight Stop2Go lap, followed by phase-preserving park."""
import unittest
from pathlib import Path
from check_rc6aa_settings_restart import Tests as Prior, ButtonTests as ButtonPrior, RTCTests as RTCPrior

ARTIFACT=Path(__file__).parent/'release_candidate_rc6ab/build/MM32SPIN05PF_OVERNIGHT_START_RC6AB_20261022.axf'

class Tests(Prior):
    artifact=ARTIFACT
    signature=0x4d505285

    def initial_release(self,style=3,saver=1,hour=5):
        self.start_pwm(style)
        normal_pair=self.pair()
        self.call('fine_stop')
        for i in (56,57,58,255):self.setword('seconds_log',i,0)
        self.setword('minute_log',185,0)
        self.setword('minute_log',192,saver)
        self.put(16,hour);self.put(15,0);self.put(5,0);self.put(22,(hour%12)*60)
        self.put(30,0);self.fixture_clock()
        self.pad_edges=[];self.overlaps=[]
        self.call('fine_runtime_tick',self.get(4),7,0)
        self.assertEqual(self.get(3),0)
        return normal_pair

    def test_overnight_start_runs_one_lap_parks_then_resumes_preserved_phase_at_6(self):
        for style in (2,3):
            self.setUp();pair=self.initial_release(style)
            self.assertTrue(self.gate());self.assertEqual(self.pair(),pair)
            self.assertEqual(self.word('seconds_log',60),0)
            self.complete_lap()
            self.assertEqual(self.word('seconds_log',255),1)
            frozen=(self.counter,self.down,self.reg(0x2c),self.reg(0x38),self.reg(0x3c))
            edges=len(self.pad_edges)
            for _ in range(128):self.tick()
            self.assertEqual(self.get(3),0)
            self.assertEqual(len(self.pad_edges),edges)
            self.assertFalse(self.gate())
            self.assertEqual(self.pad,[False,False])
            self.assertEqual((self.counter,self.down,self.reg(0x2c),self.reg(0x38),self.reg(0x3c)),frozen)
            self.assertEqual(self.word('seconds_log',58),0)
            # Fast-forward the clock AND minute-hand fixture through the night.
            self.put(16,6);self.put(15,0);self.put(5,0);self.put(22,360)
            self.setword('minute_log',191,0);self.fixture_clock()
            self.call('fine_runtime_tick',self.get(4),7,1)
            self.assertEqual(self.get(3),0)
            self.assertTrue(self.gate())
            self.assertEqual(self.word('seconds_log',58),1)
            self.assertEqual((self.counter,self.down,self.reg(0x2c),self.reg(0x38),self.reg(0x3c)),frozen)
            self.complete_lap()
            self.assertEqual(self.word('seconds_log',255),2)
            self.assertFalse(self.overlaps)

    def test_daytime_normal_modes_and_permanent_parking_are_unchanged(self):
        for style in range(4):
            for saver in (1,2):
                for hour in (5,6):
                    self.setUp();self.initial_release(style,saver,hour)
                    expected=saver==1 and (hour>=6 or style>=2)
                    self.assertEqual(bool(self.reg(0)&1),expected,(style,saver,hour))
                    self.assertEqual(self.get(30),0 if expected else 1)
                    self.assertEqual(self.get(3),0)

class ButtonTests(ButtonPrior):
    artifact=ARTIFACT
    signature=0x4d505285

class RTCTests(RTCPrior):
    artifact=ARTIFACT
    signature=0x4d505285

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
            'test_saver_change_alone_finishes_one_safe_restart',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_pending_correction_snapshot_is_not_replaced',
            'test_same_pair_schedule_save_and_legacy_time_do_not_reset',
            'test_unexpected_timer_stop_is_not_treated_as_first_launch']
    suite=unittest.TestSuite([Tests(n) for n in names]+[
        ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'),
        ButtonTests('test_sleep_closes_lease_without_reply_or_motor_change'),
        RTCTests('test_slave_held_sda_recovers_then_verifies_calendar')])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
