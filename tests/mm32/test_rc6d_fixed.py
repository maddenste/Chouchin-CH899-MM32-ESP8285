"""Fixed HC32-like Stop2Go cadence; retained continuous-mode accuracy/safety."""
import unittest
from test_rc6c_counted import Tests as RC6C


class Tests(RC6C):
    artifact = RC6C.artifact.parent.parent.parent / 'release_candidate_rc6d/build/MM32SPIN05PF_FIXED_CADENCE_RC6D_20261021.axf'
    signature = 0x4d50526d
    fine_spacing_sets = ({3754},)

    @staticmethod
    def fixed_interval(rate, residue=0):
        return (((rate * 1024 + residue) * 123) + (1 << 20)) >> 21

    def test_cleanup_control_addresses_and_interval_cache(self):
        self.assertEqual(self.symbols['minute_log'] + 188 * 4, 0x20000534)
        self.assertEqual(self.symbols['minute_log'] + 189 * 4, 0x20000538)
        for mode in range(4):
            for rate in (50000, 62500, 63108, 75000):
                self.setUp()
                self.setword('rtc_pace', 1, rate - 1)
                self.setword('release_state', 1, 1023)
                self.mode_run(mode)
                if mode & 2:
                    self.assertEqual(self.word('seconds_log', 216), self.fixed_interval(rate, 1023))
                    self.assertEqual(self.word('seconds_log', 217), 0)
                else:
                    n, d = self.word('release_state', 3), self.word('release_state', 4)
                    self.assertEqual(self.word('seconds_log', 216), n // d)
                    self.assertEqual(self.word('seconds_log', 217), n % d)

    def test_cleanup_exact_rc6_rise_fall_sequence(self):
        # Stop2Go timing is intentionally different. Continuous electrical
        # waveforms must remain byte-for-byte equivalent to the RC6 baseline.
        from test_rc6_motor_guard import Tests as RC6
        RC6.setUpClass()
        for mode in (0, 1):
            for rate in (62500, 63108):
                baseline = RC6()
                baseline.setUp()
                self.setUp()
                for t in (baseline, self):
                    t.setword('rtc_pace', 1, rate - 1)
                    t.setword('release_state', 1, 230)
                    t.mode_run(mode)
                    t.setword('request_pulses', 0, 6)
                    t.call('fine_minutes_rise', t.counter)
                    t.advance_timer(t.word('minute_log', 181) * 128)
                self.assertEqual(self.edges, baseline.edges)
                self.assertEqual(self.get(3), 0)

    def test_constant_spacing_and_width_over_counter_wraps(self):
        self.fine_run()
        for _ in range(512):
            self.setword('rtc_edge_tick', 0, self.get(4))
            self.tick()
        rises = [t for t, a, v in self.edges if (a == 0x48000410 and v == 1) or (a == 0x48000010 and v == 128)]
        falls = [t for t, a, v in self.edges if a == 0x48000010 and v == 1 << 23]
        self.assertGreater(len(rises), 60)
        self.assertEqual(set(b - a for a, b in zip(rises, rises[1:])), {3754})
        self.assertEqual(set(b - a for a, b in zip(rises, falls)), {2816})
        self.assertEqual(self.get(3), 0)

    def test_calibration_updates_only_at_new_lap(self):
        self.fine_run()
        self.setword('rtc_pace', 1, 63475)
        for _ in range(64):
            self.tick()
        self.assertEqual(self.word('minute_log', 181), self.fixed_interval(62500))
        self.advance_timer((self.reg(0x38) - self.counter) & 65535)
        self.reg(0x0c, 0)
        self.put(30, 1)
        self.put(5, 0)
        self.setword('rtc_boundary', 0, 1)
        self.tick()
        self.assertEqual(self.word('minute_log', 181), self.fixed_interval(63476))

    def test_release_catchup_uniform_while_seconds_run_all_modes(self):
        # Retain the original minute catch-up assertions; only the deliberately
        # changed Stop2Go seconds cadence has a different expected constant.
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp()
                self.startup_release_fixture()
                self.wire(f'+TIME:Wed Oct  7 23:45:00 2026 +0100 10:00 {mode}0\r\n'.encode())
                self.put(2, 10)
                self.put(22, 600)
                self.setword('rtc_boundary', 0, 1)
                self.tick()
                self.edges.clear()
                self.hold(0, 512)
                self.assertEqual((self.get(2), self.get(3)), (10, 0))
                hz = 62500 if mode & 2 else 250000
                rises = [s for s, a, v in self.edges if a == 0x48000410 and v in (2, 4)]
                falls = [s for s, a, v in self.edges if a == 0x48000410 and v == 6 << 16]
                seconds = [s for s, a, v in self.edges if (a == 0x48000410 and v == 1) or (a == 0x48000010 and v == 128)]
                self.assertGreater(len(rises), 60)
                falls = [s for s in falls if s > rises[0]]
                self.assertGreaterEqual(min(len(rises), len(falls)), 60)
                self.assertTrue(all(abs((b - a) / hz - .0625) < .00002 for a, b in zip(rises, rises[1:])))
                self.assertTrue(all(abs((b - a) / hz - .03125) < .00002 for a, b in zip(rises, falls)))
                ideal = (3754,) if mode & 2 else (15625,)
                self.assertTrue(all(b - a in ideal for a, b in zip(seconds, seconds[1:])))

    def test_fine_fraction_conserves_measured_rate_over_48_hours(self):
        # Retain exact fractional conservation for continuous modes. Stop2Go
        # deliberately rounds once and waits for :00 rather than accumulating
        # that error through an unbroken 48-hour movement stream.
        for mode in range(4):
            for rate in (62500, 62501, 62502, 62503, 75000):
                self.setUp()
                self.setword('rtc_pace', 1, rate - 1)
                self.setword('release_state', 1, 777)
                self.mode_run(mode)
                n, d = self.word('release_state', 3), self.word('release_state', 4)
                before = self.word('release_state', 2)
                intervals = []
                for _ in range(512):
                    self.advance_timer((self.reg(0x34) - self.counter) & 65535)
                    intervals.append((self.reg(0x34) - self.counter) & 65535)
                if mode & 2:
                    self.assertEqual(set(intervals), {self.fixed_interval(rate, 777)})
                    self.assertEqual(self.word('release_state', 2), before)
                    exact = (rate * 1024 + 777) * 123 / (1 << 21)
                    self.assertLessEqual(abs(intervals[0] - exact), .5)
                else:
                    self.assertLessEqual(max(intervals) - min(intervals), 1)
                    self.assertEqual(sum(intervals) * d, 512 * n + before - self.word('release_state', 2))
                    pulses = 48 * 3600 * 16
                    total = pulses * n // d
                    self.assertLess(pulses * n / d - total, 1)
                self.assertEqual(self.get(3), 0)

    def test_three_real_laps_minute_and_seconds_launch_together(self):
        self.fine_run()
        start = self.get(4)
        parks = []
        releases = []
        last = self.word('seconds_log', 255)
        was_parked = False
        for elapsed in range(1, 181 * 128 + 1):
            if elapsed % 128 == 0:
                sod = 11 * 3600 + 45 * 60 + elapsed // 128
                self.rtc_time(sod // 3600, sod // 60 % 60, sod % 60)
                self.rtc_poll()
            p = self.word('seconds_log', 248) + 1
            self.tick(int(891 <= p <= 906))
            self.assertEqual(self.get(3), 0)
            if self.word('seconds_log', 255) != last:
                last = self.word('seconds_log', 255)
                parks.append(self.get(4) - start)
            parked = bool(self.get(30))
            if was_parked and not parked:
                releases.append(self.get(4) - start)
            was_parked = parked
        self.assertEqual(len(parks), 3)
        active = (959 * 3754 + 2816) / 62500
        self.assertTrue(all(abs(p - (active + 60 * i) * 128) <= 2 for i, p in enumerate(parks)), parks)
        self.assertEqual(len(releases), 3)
        self.assertTrue(all(abs(p - (60 + 60 * i) * 128) <= 2 for i, p in enumerate(releases)), releases)
        self.assertEqual((self.get(13), self.get(22)), (18, 708))
        starts = [t for t, a, v in self.edges if (a == 0x48000410 and v == 1) or (a == 0x48000010 and v == 128)]
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertTrue(all(g == 3754 or g > 100000 for g in gaps), set(gaps))
        # Every ordinary :00 release still starts both hands at the same count.
        minute_starts = [t for t, a, v in self.edges if a == 0x48000410 and v in (2, 4)]
        self.assertEqual(len(minute_starts), 18)
        self.assertEqual(minute_starts[::6], [starts[960 * i] for i in (1, 2, 3)])

    def test_fixed_full_precision_rounding_and_nominal_lap(self):
        for mode in (2, 3):
            for rate in (50000, 62500, 63108, 75000):
                for residue in (0, 1, 777, 1023):
                    self.setUp()
                    self.setword('rtc_pace', 1, rate - 1)
                    self.setword('release_state', 1, residue)
                    self.mode_run(mode)
                    self.assertEqual(self.word('minute_log', 181), self.fixed_interval(rate, residue))
                    self.assertEqual(self.word('seconds_log', 217), 0)
        self.assertAlmostEqual(self.fixed_interval(62500) * 960 / 62500, 57.66144)

    def test_fixed_rtc_update_cannot_alternate_current_lap(self):
        for mode in (2, 3):
            self.setUp()
            self.mode_run(mode)
            expected = self.word('minute_log', 181)
            self.setword('rtc_pace', 1, 63475)
            for _ in range(512):
                self.advance_timer((self.reg(0x34) - self.counter) & 65535)
                self.assertEqual((self.reg(0x34) - self.counter) & 65535, expected)
            self.assertEqual(self.get(3), 0)


if __name__ == '__main__':
    unittest.main()
