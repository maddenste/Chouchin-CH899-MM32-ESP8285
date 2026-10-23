"""RC6C counted laps, sensor safety and inherited RC6B release checks."""
import unittest
from test_rc6b_boundary import Tests as RC6B
from unicorn.arm_const import UC_ARM_REG_R0
from unicorn import UC_HOOK_MEM_WRITE


class Tests(RC6B):
    artifact = RC6B.artifact.parent.parent.parent / 'release_candidate_rc6c/build/MM32SPIN05PF_COUNTED_RC6C_20261021.axf'
    signature = 0x4d50526c

    def with_running_sensor(self, action):
        # The inherited lease-only test supplies no optical input for 60 s.
        # RC6C intentionally rejects that missing sensor by pulse 960 (rather
        # than the old 1100-pulse seek budget). Supply a normal running sensor
        # while retaining every original lease/sleep assertion.
        tick = self.tick

        def sensor_tick(high=0):
            if self.get(2) == 7 and self.get(26):
                pulse = self.word('seconds_log', 248) + 1
                high = int(889 <= pulse <= 904)
            tick(high)

        self.tick = sensor_tick
        try:
            action()
        finally:
            self.tick = tick

    def test_window_manual_lease_and_time_keeps_cpu_awake(self):
        self.with_running_sensor(super().test_window_manual_lease_and_time_keeps_cpu_awake)

    def test_ap_mset_led_and_sixty_second_minimum(self):
        self.with_running_sensor(super().test_ap_mset_led_and_sixty_second_minimum)

    def test_boundary_error9_reproduction_recovers(self):
        # Same injected delayed reference as RC6B: it is now diagnostic only,
        # so it cannot delay the counted mode-0 lap or the mode-3 handover.
        transition = self.late_handover(0, 3, 1001)
        # The old sweep minute's final powered pulse must still drain first.
        self.assertGreaterEqual(transition, 60 - 1 / 128)
        self.assertLess(transition, 60 + 1 / 8)

    def test_counted_sensor_offsets_do_not_change_lap_length(self):
        for target in (950, 959, 960, 961, 976, 1006):
            with self.subTest(target=target):
                self.setUp()
                self.call('parallel_seconds_runtime_begin')
                anchor = target - self.seconds_offset - 1
                for pulse in range(1, 961):
                    self.call('parallel_seconds_runtime_done', 6 if anchor <= pulse <= anchor + 15 else 0)
                    self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), int(pulse == 960))
                self.assertEqual(self.word('seconds_log', 254), target)
                self.assertEqual(self.word('seconds_log', 248), 960)
                self.assertEqual(self.word('seconds_log', 255), 1)

    def test_counted_bad_sensor_stops_without_extra_seek_pulses(self):
        cases = {
            'missing': lambda p: 0,
            'stuck_high': lambda p: 6,
            'too_short': lambda p: 6 if 889 <= p <= 890 else 0,
            'too_wide': lambda p: 6 if 889 <= p <= 930 else 0,
            'late_unfinished': lambda p: 6 if p >= 950 else 0,
            'second_edge': lambda p: 6 if 889 <= p <= 904 or p == 940 else 0,
        }
        for name, sensor in cases.items():
            with self.subTest(name=name):
                self.setUp()
                self.call('parallel_seconds_runtime_begin')
                for pulse in range(1, 961):
                    self.call('parallel_seconds_runtime_done', sensor(pulse))
                    result = self.cpu.reg_read(UC_ARM_REG_R0)
                    if result:
                        self.assertEqual(result, 2)
                        break
                else:
                    self.fail('Bad sensor accepted a lap')
                self.assertLessEqual(pulse, 960)
                self.assertEqual(self.word('seconds_log', 255), 0)

    def counted_trace(self, mode, targets, duration=125, missing=False):
        self.setUp()
        self.mode_run(mode)
        completions = []
        previous = self.word('seconds_log', 255)
        resets = []

        def write(cpu, access, address, size, value, user):
            if address in (0x40000400, 0x40000414, 0x40000428):
                resets.append((address, value))

        hook = self.cpu.hook_add(UC_HOOK_MEM_WRITE, write, begin=0x40000400, end=0x40000440)
        for elapsed in range(1, duration * 128 + 1):
            if elapsed % 128 == 0:
                sod = 23 * 3600 + 45 * 60 + elapsed // 128
                self.rtc_time(sod // 3600, sod // 60 % 60, sod % 60)
                self.rtc_poll()
            target = targets[self.word('seconds_log', 255) % len(targets)]
            anchor = target - self.seconds_offset - 1
            pulse = self.word('seconds_log', 248) + 1
            self.tick(0 if missing else int(anchor <= pulse <= anchor + 15))
            self.assertLessEqual(self.word('seconds_log', 248), 960)
            if self.word('seconds_log', 255) != previous:
                # Continuous modes clear the sensor scratch immediately at
                # completion; the audit retains the completed observation.
                measured = (960 + self.word('minute_log', 198)) & 0xffffffff
                completions.append((self.get(12), measured))
                previous = self.word('seconds_log', 255)
            if missing and self.get(3):
                break
            self.assertEqual(self.get(3), 0, (mode, targets, elapsed))
        self.cpu.hook_del(hook)
        starts = [(time, address, value) for time, address, value in self.edges
                  if (address == 0x48000410 and value == 1)
                  or (address == 0x48000010 and value == 128)]
        return completions, starts, resets

    def test_counted_all_modes_preserve_polarity_and_electrical_cadence(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                completions, starts, resets = self.counted_trace(mode, (959, 961, 960))
                self.assertEqual(completions[:2], [(960, 959), (1920, 961)])
                self.assertEqual(resets, [])
                polarities = [(a, v) for time, a, v in starts]
                self.assertTrue(all(a != b for a, b in zip(polarities, polarities[1:])))
                self.assertEqual(polarities[0], polarities[960])
                self.assertEqual(polarities[0], polarities[1920])
                for lap in (starts[:960], starts[960:1920]):
                    gaps = [b[0] - a[0] for a, b in zip(lap, lap[1:])]
                    self.assertLessEqual(max(gaps) - min(gaps), 1)
                if not mode & 2:
                    # Continuous modes have no special gap at lap boundaries.
                    gaps = [b[0] - a[0] for a, b in zip(starts, starts[1:])]
                    self.assertLessEqual(max(gaps) - min(gaps), 1)

    def test_counted_missing_sensor_faults_after_complete_960th_pulse(self):
        completions, starts, resets = self.counted_trace(3, (960,), duration=61, missing=True)
        self.assertEqual(completions, [])
        self.assertEqual(len(starts), 960)
        self.assertEqual(self.get(12), 960)
        self.assertEqual((self.get(2), self.get(3)), (6, 5))
        self.assertEqual(self.word('second_active'), 0)
        self.assertEqual(self.reg(0x0c), 0)

    def test_counted_alignment_observation_stays_separate_from_motion(self):
        for target, status in ((959, 2), (960, 2), (961, 2), (980, 3)):
            self.setUp()
            self.setword('seconds_log', 254, target)
            self.call('audit_seconds_reference')
            self.assertEqual(self.word('minute_log', 196), status)
            self.assertEqual(self.word('minute_log', 203), 0)
            self.assertEqual(self.word('seconds_log', 248), 0)
        self.a(1, 1)
        self.call('audit_seconds_reference')
        self.assertEqual(self.word('minute_log', 203), 2)
        self.assertEqual(self.word('seconds_log', 248), 0)

    def test_counted_overrun_cannot_complete_a_second_lap(self):
        self.call('parallel_seconds_runtime_begin')
        for pulse in range(1, 961):
            self.call('parallel_seconds_runtime_done', 6 if 890 <= pulse <= 905 else 0)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 1)
        self.assertEqual(self.word('seconds_log', 255), 1)
        self.call('parallel_seconds_runtime_done', 0)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 2)
        self.assertEqual(self.word('seconds_log', 255), 1)


if __name__ == '__main__':
    unittest.main()
