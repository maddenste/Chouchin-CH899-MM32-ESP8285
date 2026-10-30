"""Compiled hold-only temperature compensation checks; no hardware access."""
import sys
import unittest
from pathlib import Path
import check_rc6bg_clean_wake as bg

IMAGE = Path(__file__).resolve().parents[2] / 'firmware/mm32/build/MM32SPIN05PF_TEMPERATURE_TRIAL_RC6BH_20261029.axf'

class Temperature(bg.Diagnostic):
    artifact = IMAGE
    signature = 0x4d5052a5

    def reference(self, cycles, state=1, updates=4, rejects=0):
        for index, value in ((1,state), (14,updates), (13,rejects), (16,cycles)):
            self.setword('pulse_diag', index, value)

    def target(self, cycles, old):
        period = (cycles * 123 + 131072) // 262144
        return min(old + old // 100, max(old - old // 100, period))

    def test_warming_and_cooling_change_only_the_next_held_lap(self):
        for style, cycles in ((2,63724800), (3,64275200)):
            with self.subTest(style=style, cycles=cycles):
                self.setUp(); self.held_fixture(style)
                old = self.word('seconds_log',56)
                self.reference(cycles)
                expected = self.target(cycles,old)
                before = self.pair(); epoch = self.word('seconds_log',215)
                writes, hook = self.trace()
                self.put(30,0); self.call('parallel_seconds_runtime_begin')
                self.call('pwm_resume_lap')
                self.assertEqual(self.pair(),before)
                self.assertEqual(self.reg(0x20),0)
                self.assertEqual(self.word('seconds_log',56),expected)
                self.assertEqual(self.word('seconds_log',57),2*((expected*3+4)//8))
                self.assertEqual(self.word('seconds_log',55),1)
                edge_start = len(self.pad_edges)
                self.settle_release()
                normal = (expected*128+61)//123
                self.assertEqual(self.pair(),(normal,2*((normal*3+4)//8)))
                self.advance_timer(normal*1020)
                self.cpu.hook_del(hook)
                rises = [e for e in self.pad_edges[edge_start:] if e[2]]
                falls = [e for e in self.pad_edges[edge_start:] if not e[2]]
                self.assertEqual((len(rises),len(falls)),(960,960))
                self.assertEqual(self.dma_writes[-1][1],960)
                # Blank internal cycles may advance the observer until the
                # ordinary CPU poll stops it; they deliver no motor pulses.
                self.assertEqual({b[0]-a[0] for a,b in zip(rises[-101:],rises[-100:])},{expected})
                self.assertEqual({b[0]-a[0] for a,b in zip(rises[-100:],falls[-100:])},{2*((expected*3+4)//8)})
                self.assertTrue(all(a[1]!=b[1] for a,b in zip(rises,rises[1:])))
                self.assertFalse(self.overlaps)
                self.assertEqual(self.word('seconds_log',215),epoch)
                self.assertEqual(self.reg(0)&1,1)
                self.assertEqual(self.reg(0x20),0)
                self.assertFalse([(a,v) for a,v in writes if a in (
                    0x40000400,0x40000408,0x40000414,0x40000418,
                    0x4000041c,0x40000424,0x40000428)])
                self.assertEqual(self.get(3),0)

    def test_rate_change_during_movement_cannot_change_target_or_timer(self):
        self.start_pwm(3)
        self.reference(63724800)
        before = [self.word('seconds_log',i) for i in (55,56,57,66)]
        pair = self.pair(); writes,hook = self.trace()
        self.call('pwm_refresh_stop_rate')
        self.cpu.hook_del(hook)
        self.assertEqual([self.word('seconds_log',i) for i in (55,56,57,66)],before)
        self.assertEqual(self.pair(),pair)
        self.assertFalse([(a,v) for a,v in writes if 0x40000000 <= a < 0x50000000])

    def test_unqualified_or_out_of_range_reference_keeps_previous_pair(self):
        self.held_fixture(3)
        before = [self.word('seconds_log',i) for i in (55,56,57,66)]
        for state,updates,rejects,cycles in (
            (0,4,0,63724800),(3,4,0,63724800),(1,0,0,63724800),
            (1,4,1,63724800),(1,4,0,0),(1,4,0,0xffffffff)):
            self.reference(cycles,state,updates,rejects)
            self.call('pwm_refresh_stop_rate')
            self.assertEqual([self.word('seconds_log',i) for i in (55,56,57,66)],before)
        self.assertEqual(self.get(3),0)

    def test_large_valid_drift_is_bounded_to_one_percent(self):
        for cycles in (50000*1024,75000*1024):
            self.setUp();self.held_fixture(3)
            old = self.word('seconds_log',56)
            self.reference(cycles)
            self.put(30,0);self.call('parallel_seconds_runtime_begin')
            self.call('pwm_resume_lap');self.settle_release()
            new = self.word('seconds_log',56)
            self.assertEqual(abs(new-old),old//100)
            self.assertEqual(self.get(3),0)
            self.assertEqual(self.reg(0x20),0x110)

    def test_two_count_deadband_avoids_reference_noise(self):
        self.held_fixture(3)
        old = self.word('seconds_log',56)
        for delta in (-2,-1,0,1,2):
            cycles = ((old+delta)*262144+61)//123
            self.reference(cycles)
            self.call('pwm_refresh_stop_rate')
            self.assertEqual(self.word('seconds_log',56),old)
            self.assertEqual(self.word('seconds_log',55),0)

    def test_new_reference_after_request_waits_for_a_later_lap(self):
        self.held_fixture(3);self.reference(63724800)
        self.put(30,0);self.call('parallel_seconds_runtime_begin')
        self.call('pwm_resume_lap')
        fixed = self.word('seconds_log',56)
        self.reference(64275200)
        self.call('pwm_refresh_stop_rate');self.settle_release()
        self.assertEqual(self.word('seconds_log',56),fixed)
        self.assertEqual(self.word('seconds_log',55),1)
        self.assertEqual(self.get(3),0)

if __name__ == '__main__':
    prior = bg.prior
    for cls in (bg.Diagnostic, prior.SessionSleep, prior.PendingSession,
                prior.baseline.Tests, prior.baseline.Buttons,
                prior.baseline.General, prior.baseline.RTCChecks,
                prior.baseline.RecoveryChecks, prior.Handover, prior.Deadline):
        cls.artifact = IMAGE
        cls.signature = Temperature.signature
    selected = [Temperature(n) for n in Temperature.__dict__ if n.startswith('test_')]
    if '--wake' in sys.argv:
        selected = [bg.Diagnostic(n) for n in bg.Diagnostic.__dict__ if n.startswith('test_')]
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
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    raise SystemExit(not result.wasSuccessful())
