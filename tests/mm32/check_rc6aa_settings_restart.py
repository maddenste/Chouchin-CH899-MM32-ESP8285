"""Restart on battery-saver setting changes; initially parked release regression."""
import unittest
from pathlib import Path
from check_rc6z_style_restart import Tests as Prior, ButtonTests as ButtonPrior, RTCTests as RTCPrior

ARTIFACT=Path(__file__).parent/'release_candidate_rc6aa/build/MM32SPIN05PF_SETTINGS_RESTART_RC6AA_20261022.axf'

class Tests(Prior):
    artifact=ARTIFACT
    signature=0x4d505284

    def start_pwm(self,mode=3):
        super().start_pwm(mode)
        self.setword('minute_log',192,0) # Match the saved setting in test TIME.

    def test_all_saver_transitions_in_all_styles_request_restart_without_live_change(self):
        for style in range(4):
            for old in range(3):
                for new in range(3):
                    if old==new:continue
                    self.setUp();self.start_pwm(style);self.setword('minute_log',192,old)
                    self.wire(style,new)
                    self.assertEqual(self.word('minute_log',190),1,(style,old,new))
                    self.assertEqual(self.word('minute_log',189),style)
                    self.assertEqual(self.word('minute_log',192),old)
                    self.assertEqual(self.get(3),0)

    def test_first_boot_latches_each_style_saver_pair_without_reset(self):
        for style in range(4):
            for saver in range(3):
                self.setUp();self.setword('minute_log',188,0)
                self.wire(style,saver);self.wire(style,saver)
                self.assertEqual(self.word('minute_log',189),style)
                self.assertEqual(self.word('minute_log',192),saver)
                self.assertEqual(self.word('minute_log',190),0)

    def test_same_pair_schedule_save_and_legacy_time_do_not_reset(self):
        self.start_pwm(3)
        for _ in range(3):self.wire(3,0)
        data=b'+TIME:Thu Oct 22 14:20:30 2026 +0100 11:30 30\r\n'
        for b in data:self.call('uart_probe_consume',b)
        self.assertEqual((self.word('daily_log',10),self.word('daily_log',11)),(11,30))
        self.wire()
        self.assertEqual(self.word('minute_log',190),0)
        self.assertEqual((self.word('daily_log',10),self.word('daily_log',11)),(10,0))
        self.assertEqual(self.word('minute_log',192),0)

    def test_saver_change_alone_finishes_one_safe_restart(self):
        self.start_pwm(3);self.advance_timer(8000)
        events=self.reset_capture();self.wire(3,2)
        for _ in range(64):
            self.tick()
            if events:break
        self.assertEqual(len(events),1)
        self.assertEqual(events[0][0],0x05fa0004)
        self.assertEqual(events[0][2:5],((False,False),0,0))
        self.assertEqual(self.word('minute_log',192),0)
        self.assertEqual(self.get(3),0)

    def test_initial_night_park_launches_once_at_6am_then_uses_phase_resume(self):
        for style in (2,3):
            self.setUp();self.start_pwm(style);self.call('fine_stop')
            self.setword('seconds_log',56,0);self.setword('seconds_log',57,0)
            self.setword('minute_log',192,1)
            self.put(16,5);self.put(30,0)
            self.put(22,5*60+self.get(15))
            self.call('fine_runtime_tick',self.get(4),7,0)
            self.assertEqual(self.get(30),1)
            self.assertEqual(self.reg(0)&1,0)
            self.put(16,6)
            self.put(22,6*60+self.get(15))
            self.fixture_clock() # Advance the projected-clock fixture too.
            self.call('fine_runtime_tick',self.get(4),7,1)
            self.assertEqual(self.get(3),0)
            self.assertTrue(self.gate())
            self.assertEqual(self.word('seconds_log',58),0) # A launch, not resume.
            self.complete_lap()
            self.put(5,0);self.setword('rtc_boundary',0,1);self.tick()
            self.assertEqual(self.get(3),0)
            self.assertTrue(self.gate())
            self.assertEqual(self.word('seconds_log',58),1)

    def test_unexpected_timer_stop_is_not_treated_as_first_launch(self):
        self.start_pwm(3)
        self.assertEqual(self.word('seconds_log',60),0)
        self.bt_count=960;self.setword('seconds_log',219,960);self.put(30,1)
        self.counter=self.reg(0x34);self.down=False
        self.store(0x40000400,0) # Unexpected loss of CEN, not initialisation.
        self.call('fine_runtime_tick',self.get(4),7,1)
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',17),7)

class ButtonTests(ButtonPrior):
    artifact=ARTIFACT
    signature=0x4d505284
    def start_pwm(self,mode=3):
        super().start_pwm(mode);self.setword('minute_log',192,0)

class RTCTests(RTCPrior):
    artifact=ARTIFACT
    signature=0x4d505284

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_all_twelve_style_changes_request_reset_without_live_switch',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_pending_correction_snapshot_is_not_replaced',
            'test_fresh_boot_accepts_new_saved_style_without_another_restart',
            'test_drain_timeout_faults_instead_of_resetting_live_motor',
            'test_release_does_not_write_pwm_or_motor_gpio_registers']
    suite=unittest.TestSuite([Tests(n) for n in names]+[
        ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'),
        ButtonTests('test_sleep_closes_lease_without_reply_or_motor_change'),
        RTCTests('test_slave_held_sda_recovers_then_verifies_calendar')])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
