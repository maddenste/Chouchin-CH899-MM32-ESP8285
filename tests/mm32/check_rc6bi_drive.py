"""RC6BI release drive and inherited regressions: compiled code, no hardware access."""
import sys
import os
import unittest
from pathlib import Path
import check_rc6bh_temperature as bh

IMAGE = Path(__file__).resolve().parents[2] / 'firmware/mm32/build/MM32SPIN05PF_DRIVE_TRIAL_RC6BI_20261029.axf'

class Drive(bh.Temperature):
    artifact = IMAGE
    signature = 0x4d5052a6

    def test_runtime_changes_only_seconds_drive_bits_in_all_styles(self):
        baseline = Path(os.environ.get("MM32_DRIVE_BASELINE_ELF", str(IMAGE.parents[4] / "MM32-Temperature-Trial-RC6BH/firmware/mm32/build/MM32SPIN05PF_TEMPERATURE_TRIAL_RC6BH_20261029.axf")))
        if not baseline.is_file():
            self.skipTest("Build RC6BH and set MM32_DRIVE_BASELINE_ELF for differential GPIO comparison")
        bh.Temperature.artifact = baseline
        bh.Temperature.setUpClass()
        for style in range(4):
            with self.subTest(style=style):
                self.setUp(); self.start_pwm(style)
                old = bh.Temperature('test_two_count_deadband_avoids_reference_noise')
                old.setUp(); old.start_pwm(style)
                self.assertEqual(self.raw(0x48000000) ^ old.raw(0x48000000),2<<28)
                self.assertEqual(self.raw(0x48000400) ^ old.raw(0x48000400),2)
                self.assertEqual((self.raw(0x48000000)>>28)&15,11)
                self.assertEqual(self.raw(0x48000400)&15,11)
                self.assertEqual(self.pair(),old.pair())
                for base, offsets in ((0x40000400,(0,4,8,0x18,0x1c,0x20,0x28,0x2c,0x34,0x38,0x3c,0x40)),
                                      (0x40012c00,(0,4,8,0x18,0x28,0x2c,0x34)),
                                      (0x40014000,(0,4,0x18,0x28,0x2c))):
                    for offset in offsets:
                        self.assertEqual(self.raw(base+offset),old.raw(base+offset),(style,hex(base+offset)))
                self.assertEqual(self.word('seconds_log',215),1)
                self.assertEqual(self.get(3),0)

    def test_minute_rmw_preserves_seconds_drive_and_stop_releases_gpio(self):
        self.start_pwm(3)
        self.setword('request_pulses',0,3)
        self.call('pwm_minutes_queue');self.advance_timer(32)
        self.assertEqual(self.raw(0x48000400)&15,11)
        self.assertEqual(self.raw(0x48000400)&0xff0,0x220)
        self.call('motors_off')
        self.assertEqual(self.raw(0x48000400)&15,4)
        self.assertEqual((self.raw(0x48000000)>>28)&15,4)
        self.assertEqual(self.reg(0x20),0)
        self.assertEqual(self.pad,[False,False])

if __name__ == '__main__':
    prior = bh.bg.prior
    for cls in (bh.bg.Diagnostic, prior.SessionSleep, prior.PendingSession,
                prior.baseline.Tests, prior.baseline.Buttons,
                prior.baseline.General, prior.baseline.RTCChecks,
                prior.baseline.RecoveryChecks, prior.Handover, prior.Deadline):
        cls.artifact = IMAGE
        cls.signature = Drive.signature
    selected = [Drive(n) for n in Drive.__dict__ if n.startswith('test_')]
    if '--session' in sys.argv:
        selected = [prior.SessionSleep(n) for n in prior.SessionSleep.__dict__ if n.startswith('test_')]
    if '--pending' in sys.argv:
        selected = [prior.PendingSession(n) for n in prior.PendingSession.__dict__ if n.startswith('test_')]
    if '--deadline' in sys.argv:
        selected = [prior.Deadline(n) for n in prior.Deadline.__dict__ if n.startswith('test_')]
    if '--regression' in sys.argv:
        selected = prior.baseline.cases()
    if '--temperature' in sys.argv:
        selected = [Drive(n) for n in bh.Temperature.__dict__ if n.startswith('test_')]
    if '--wake' in sys.argv:
        selected = [bh.bg.Diagnostic(n) for n in bh.bg.Diagnostic.__dict__ if n.startswith('test_')]
    if '--handover' in sys.argv:
        selected = [prior.Handover(n) for n in prior.Handover.__dict__ if n.startswith('test_')]
    if '--motor' in sys.argv:
        selected = [prior.baseline.Tests(n) for n in (
            'test_normal_modes_keep_original_waveforms_and_no_ramp',
            'test_two_laps_and_normal_launch_again_after_hold',
            'test_late_ramp_irq_does_not_change_active_pulse',
            'test_overnight_stop_mode_resumes_with_ramp_without_second_timer_launch',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_all_saver_transitions_in_all_styles_request_restart_without_live_change')]
    if '--part=1' in sys.argv:
        selected = selected[::2]
    if '--part=2' in sys.argv:
        selected = selected[1::2]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    raise SystemExit(not result.wasSuccessful())
