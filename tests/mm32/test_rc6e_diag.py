"""RC6E diagnostic accuracy, unmodified waveform, and RC6D regressions."""
import unittest
from test_rc6d_fixed import Tests as RC6D
from unicorn import UC_HOOK_CODE


class Tests(RC6D):
    artifact = RC6D.artifact.parent.parent.parent / 'release_candidate_rc6e/build/MM32SPIN05PF_EDGE_DIAG_RC6E_20261021.axf'
    signature = 0x4d50526e

    def test_release_defaults_and_no_profiler(self):
        # This is explicitly a diagnostic build, not the profiler-free release.
        # Keep default-policy and no-unrelated-idle-write assertions; account
        # for its separately placed, bounded 160-byte diagnostic block.
        self.assertEqual(self.boot_modes, (0, 0))
        self.assertEqual(self.boot_night, 1)
        self.assertEqual(self.symbols['pulse_diag'], 0x20000c40)
        self.assertLessEqual(self.ram_end, 0x20000ce0)
        before = [self.word('seconds_log', i) for i in range(214, 221)]
        self.idle()
        self.assertEqual(before, [self.word('seconds_log', i) for i in range(214, 221)])

    def test_diag_fixed_address_reset_and_freeze(self):
        self.assertEqual(self.symbols['pulse_diag'], 0x20000c40)
        self.mode_run(3)
        self.advance_timer(self.word('minute_log', 181) * 20)
        self.assertEqual(self.word('pulse_diag', 1), 0x45444745)
        self.assertGreater(self.word('pulse_diag', 2), 1)
        self.assertEqual(self.word('pulse_diag', 13), 0)
        self.assertEqual(self.word('pulse_diag', 14), 0)
        self.setword('pulse_diag', 0, 2)
        before = bytes(self.cpu.mem_read(0x20000c40, 160))
        self.advance_timer(self.word('minute_log', 181) * 10)
        self.assertEqual(bytes(self.cpu.mem_read(0x20000c40, 160)), before)
        self.setword('pulse_diag', 0, 0)
        self.advance_timer(self.word('minute_log', 181))
        self.assertEqual(self.word('pulse_diag', 0), 1)
        self.assertLessEqual(self.word('pulse_diag', 2), 2)

    def test_guard_overrun_cannot_silently_delay_motor(self):
        super().test_guard_overrun_cannot_silently_delay_motor()
        self.assertEqual(self.word('pulse_diag', 23), 150)

    def test_diag_raw_sensor_counts_distinguish_subthreshold_highs(self):
        self.mode_run(3)
        for highs in (0, 2, 6):
            self.setword('second_highs', 0, highs)
            self.advance_timer((self.reg(0x38) - self.counter) & 65535)
            self.advance_timer((self.reg(0x34) - self.counter) & 65535)
        self.assertEqual(self.word('pulse_diag', 25), 2)
        self.assertEqual(self.word('pulse_diag', 26), 6)
        self.assertEqual(self.word('pulse_diag', 27), 1)

    def test_diag_detects_injected_rise_delay_and_catchup(self):
        self.mode_run(3)
        self.advance_timer(self.word('minute_log', 181) * 3)
        self.reg(0x0c, 0)  # Model IRQ service delayed, not a physical capture.
        delta = (self.reg(0x34) - self.counter) & 65535
        self.advance_timer(delta + 63)
        self.reg(0x0c, 2)
        self.sr = 2
        self.call('TIM3_Handler')
        self.assertEqual(self.word('pulse_diag', 11), 63)
        self.assertEqual(self.word('pulse_diag', 13), 63)
        self.assertEqual(self.word('pulse_diag', 15), 1)
        self.advance_timer(self.word('minute_log', 181) * 2)
        self.assertGreaterEqual(self.word('pulse_diag', 15), 2)
        self.assertGreaterEqual(self.word('pulse_diag', 14), 63)
        self.assertEqual(self.get(3), 0)

    def test_diag_detects_injected_fall_delay(self):
        self.mode_run(3)
        self.reg(0x0c, 0)
        delta = (self.reg(0x38) - self.counter) & 65535
        self.advance_timer(delta + 31)
        self.reg(0x0c, 4)
        self.sr = 4
        self.call('TIM3_Handler')
        self.assertEqual(self.word('pulse_diag', 12), 31)
        self.assertEqual(self.word('pulse_diag', 14), 31)
        self.assertEqual(self.word('pulse_diag', 16), 1)
        self.assertEqual(self.get(3), 0)

    def test_diag_waveform_matches_rc6d_all_modes(self):
        RC6D.setUpClass()
        for mode in range(4):
            baseline = RC6D(); baseline.setUp(); self.setUp()
            for t in (baseline, self):
                t.mode_run(mode)
                t.setword('request_pulses', 0, 6)
                t.call('fine_minutes_rise', t.counter)
                t.advance_timer(t.word('minute_log', 181) * 128)
            self.assertEqual(self.edges, baseline.edges)
            self.assertEqual(self.get(3), 0)

    def test_diag_wrap_and_epoch_exclude_false_gaps(self):
        self.mode_run(3)
        self.advance_timer(self.word('minute_log', 181) * 40)
        self.assertEqual(self.word('pulse_diag', 13), 0)
        self.assertEqual(self.word('pulse_diag', 14), 0)
        self.setword('seconds_log', 248, 0)  # A parked/new-lap start.
        self.counter = (self.counter + 20000) & 65535
        self.call('fine_seconds_rise', self.counter)
        self.assertEqual(self.word('pulse_diag', 13), 0)

    def test_cleanup_seconds_rise_uses_fewer_instructions(self):
        # RC6E deliberately adds measurement: replace the cleanup-only speed
        # claim with an explicit bounded instruction-overhead check.
        RC6D.setUpClass()
        totals = []
        for cls in (RC6D, type(self)):
            t = cls(); t.setUp(); t.mode_run(3)
            t.advance_timer((t.reg(0x38) - t.counter) & 65535)
            count = [0]
            def code(cpu, address, size, user): count[0] += 1
            hook = t.cpu.hook_add(UC_HOOK_CODE, code)
            t.cpu.ctl_remove_cache(0x08000000, 0x08008000)
            t.advance_timer((t.reg(0x34) - t.counter) & 65535)
            t.cpu.hook_del(hook); totals.append(count[0])
        print('RC6D/RC6E rise-handler instruction totals:', totals, flush=True)
        self.assertLess(totals[1] - totals[0], 400)


if __name__ == '__main__': unittest.main()
