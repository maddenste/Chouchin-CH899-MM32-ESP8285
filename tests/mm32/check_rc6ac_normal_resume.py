"""Normal-mode first overnight lap and preserved PWM release; correction unchanged."""
import unittest
from pathlib import Path
from check_rc6ab_overnight_start import Tests as Prior, ButtonTests as ButtonPrior, RTCTests as RTCPrior
from unicorn import UC_HOOK_MEM_WRITE

ARTIFACT=Path(__file__).parent/'release_candidate_rc6ac/build/MM32SPIN05PF_ALL_MODE_RESUME_RC6AC_20261022.axf'

class Tests(Prior):
    artifact=ARTIFACT
    signature=0x4d505286

    def test_normal_overnight_lap_and_morning_release_preserve_waveform(self):
        for style in (0,1):
            self.setUp();pair=self.initial_release(style)
            self.assertEqual(self.pair(),pair)
            self.assertTrue(self.gate())
            self.complete_lap()
            rises=[e for e in self.pad_edges if e[2]]
            falls=[e for e in self.pad_edges if not e[2]]
            p,w=pair
            self.assertEqual((len(rises),len(falls)),(960,960))
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
            last_pin=rises[-1][1]
            frozen=self.counter,self.down,self.reg(0x2c),self.reg(0x38),self.reg(0x3c)
            before=len(self.pad_edges)
            for _ in range(128):self.tick()
            self.assertEqual(self.get(3),0)
            self.assertFalse(self.gate())
            self.assertEqual(len(self.pad_edges),before)
            self.put(16,6);self.put(15,0);self.put(5,0);self.put(22,360)
            self.setword('minute_log',191,0);self.fixture_clock()
            writes=[]
            hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,
                lambda c,a,address,size,value,u:writes.append((address,value)))
            self.cpu.ctl_remove_cache(0x08000000,0x08008000)
            self.call('fine_runtime_tick',self.get(4),7,1)
            self.cpu.hook_del(hook)
            self.assertEqual(self.get(3),0)
            self.assertTrue(self.gate())
            self.assertEqual(self.word('seconds_log',58),1)
            self.assertEqual(self.counter,self.reg(0x34))
            self.assertEqual((self.counter,self.down,self.reg(0x2c),self.reg(0x38),self.reg(0x3c)),frozen)
            self.assertEqual(len(self.pad_edges),before)
            self.assertEqual(self.raw(0x40012c2c),959)
            self.assertEqual(self.bt_count,0)
            # No PWM/AF/ownership writes during morning release. Sensor
            # selection and the separate observer counter may still change.
            self.assertFalse([(a,v) for a,v in writes if 0x40000400<=a<=0x40000440])
            self.assertFalse([(a,v) for a,v in writes if a in (0x48000000,0x48000020,0x48000400,0x48000420)])
            # Autonomous edges across two complete wraps, with no CPU service.
            self.advance_timer(p*1930,dispatch=False)
            events=self.pad_edges[before:]
            rises=[e for e in events if e[2]];falls=[e for e in events if not e[2]]
            self.assertEqual((len(rises),len(falls),self.bt_count),(1930,1930,10))
            self.assertNotEqual(rises[0][1],last_pin)
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
            self.assertTrue(all(a[1]!=b[1] for a,b in zip(rises,rises[1:])))
            self.assertTrue(self.gate());self.assertFalse(self.overlaps)

    def test_all_styles_start_one_scheduled_night_lap_but_permanent_park_does_not(self):
        for style in range(4):
            for saver in (1,2):
                for hour in (5,6):
                    self.setUp();self.initial_release(style,saver,hour)
                    expected=saver==1
                    self.assertEqual(bool(self.reg(0)&1),expected,(style,saver,hour))
                    self.assertEqual(self.get(3),0)

    @staticmethod
    def correction_release_fixture(t,phase):
        t.start_pwm(0)
        t.bt_count=960;t.setword('seconds_log',219,960)
        t.store(0x40012c2c,65535);t.store(0x40012c34,960)
        t.counter=t.reg(0x34);t.down=False
        # Exercise explicit drain release AND a full-reference correction hold.
        t.setword('seconds_log',220,1 if phase==0 else 0)
        t.put(30,1);t.setword('daily_log',13,phase)

    def test_correction_drain_keeps_prior_release_path(self):
        Prior.setUpClass()
        for phase in (0,1,2):
            self.setUp();old=Prior();old.setUp()
            results=[]
            for t in (old,self):
                self.correction_release_fixture(t,phase)
                writes=[]
                hook=t.cpu.hook_add(UC_HOOK_MEM_WRITE,
                    lambda c,a,address,size,value,u:writes.append((address,value)),
                    begin=0x40000400,end=0x40000440)
                t.cpu.ctl_remove_cache(0x08000000,0x08008000)
                t.call('fine_runtime_tick',t.get(4),7,1)
                t.cpu.hook_del(hook)
                results.append((writes,t.get(3),t.get(30),t.word('daily_log',13),t.word('seconds_log',58)))
            self.assertEqual(results[0],results[1],phase)
            self.assertEqual(self.word('seconds_log',58),0)
            if phase==0:self.assertIn((0x40000414,1),results[1][0]) # Existing reinitialisation.
            else:self.assertEqual(results[1][0],[]) # Still waiting; no premature release.

class ButtonTests(ButtonPrior):
    artifact=ARTIFACT
    signature=0x4d505286

class RTCTests(RTCPrior):
    artifact=ARTIFACT
    signature=0x4d505286

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_overnight_start_runs_one_lap_parks_then_resumes_preserved_phase_at_6',
            'test_normal_calibration_changes_only_safe_gap_without_extra_counts',
            'test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_same_pair_schedule_save_and_legacy_time_do_not_reset',
            'test_unexpected_timer_stop_is_not_treated_as_first_launch']
    suite=unittest.TestSuite([Tests(n) for n in names]+[
        ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'),
        ButtonTests('test_sleep_closes_lease_without_reply_or_motor_change'),
        RTCTests('test_slave_held_sda_recovers_then_verifies_calendar')])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
