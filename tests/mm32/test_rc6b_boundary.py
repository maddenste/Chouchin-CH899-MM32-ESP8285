"""RC6B boundary recovery plus inherited RC6A release checks."""
import unittest
from test_rc6a_cleanup import Tests as RC6A


class Tests(RC6A):
    artifact = RC6A.artifact.parent.parent.parent / 'release_candidate_rc6b/build/MM32SPIN05PF_BOUNDARY_RC6B_20261021.axf'
    signature = 0x4d50526b

    def test_reject_exact_live_rollover_then_recover(self):
        self.window_seed()
        base = self.word('seconds_log', 227) // 86400 * 86400
        stamp = 20 * 3600 + 12 * 60 + 59
        self.setword('seconds_log', 227, base + stamp)
        self.setword('rtc_last', 0, stamp)
        # Keep physical/civil coordinates coherent when the RTC-only fixture
        # jumps from 11:45 to 20:12:59. Rejection assertions are unchanged.
        self.put(16, 20)
        self.put(15, 12)
        self.put(5, 59)
        self.put(22, stamp // 60 % 720)
        for _ in range(128):
            self.tick()
        reload = self.word('rtc_pace', 1)
        self.sample(20, 13, 59)
        self.assertEqual((self.get(3), self.word('rtc_pace', 9)), (0, 1))
        self.assertEqual(self.word('rtc_last', 0), stamp)
        self.assertEqual(self.word('rtc_pace', 1), reload)
        self.sample(20, 13, 0)
        self.assertEqual((self.get(3), self.word('rtc_pace', 9)), (0, 0))
        self.assertEqual(self.word('seconds_log', 223), 2)

    def test_window_midnight_uses_real_calendar_rollover(self):
        self.window_seed()
        stamp = self.word('seconds_log', 227) // 86400 * 86400 + 86399
        self.setword('seconds_log', 227, stamp)
        self.setword('rtc_last', 0, 86399)
        self.put(16, 23)
        self.put(15, 59)
        self.put(5, 59)
        # The inherited calendar-only fixture jumps from 11:45 to 23:59
        # without moving its minute coordinate. All-mode consistency checks
        # now run while seconds move, so seed a coherent 23:59 hand too.
        self.put(22, 719)
        self.rtc_time(23, 59, 59)
        for _ in range(128):
            self.tick()
        old = self.bus.data[5]
        day = (old >> 4) * 10 + (old & 15) + 1
        self.bus.data[5] = (day // 10) * 16 + day % 10
        self.rtc_time(0, 0, 0)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('seconds_log', 227), stamp + 1)
        self.assertEqual((self.get(16), self.get(15), self.get(5), self.get(3)), (0, 0, 0, 0))

    def late_handover(self, old, new, target, duration=185):
        self.setUp()
        self.mode_run(old)
        transitions = []
        previous = self.word('minute_log', 189)
        for elapsed in range(1, duration * 128 + 1):
            if elapsed % 128 == 0:
                seconds = elapsed // 128
                if seconds == 25:
                    self.setword('minute_log', 188, new)
                sod = 23 * 3600 + 45 * 60 + seconds
                self.rtc_time(sod // 3600, sod // 60 % 60, sod % 60)
                self.rtc_poll()
            pulse = self.word('seconds_log', 248) + 1
            active = self.word('minute_log', 189)
            # Qualification takes two high samples; target includes that
            # one-pulse qualification delay plus the post-detection offset.
            anchor = (target if active == old else 960) - self.seconds_offset - 1
            self.tick(int(anchor <= pulse <= anchor + 15))
            # A seconds lap must never suppress the minute's :00 advance.
            if elapsed in (121 * 128, 181 * 128):
                self.assertEqual(self.get(22), 705 + elapsed // (60 * 128))
            if self.word('minute_log', 189) != previous:
                transitions.append(elapsed / 128)
                previous = self.word('minute_log', 189)
            self.assertEqual(self.get(3), 0, (old, new, target, elapsed / 128))
        self.assertEqual(self.word('minute_log', 189), new)
        self.assertEqual(self.get(22), 708)
        self.assertEqual(len(transitions), 1)
        return transitions[0]

    def test_boundary_error9_reproduction_recovers(self):
        self.assertAlmostEqual(self.late_handover(0, 3, 1001), 62.546875)

    def test_boundary_late_handover_matrix(self):
        for old in (0, 1):
            for new in (2, 3):
                for target in (960, 976, 992, 1006):
                    with self.subTest(old=old, new=new, target=target):
                        self.late_handover(old, new, target)

    def test_boundary_grace_is_bounded_across_tick_wrap(self):
        self.mode_run(3)
        self.put(4, 0xffffff80)
        self.setword('rtc_edge_tick', 0, 0xffffff80)
        self.setword('seconds_log', 221, (0xffffff80 + 992) & 0xffffffff)
        self.setword('seconds_log', 223, 2)
        self.setword('seconds_log', 224, 0xffffff80)
        self.setword('release_state', 5, 0xffffff80)
        self.setword('minute_log', 187, 1)
        for _ in range(384):
            self.tick()
        self.assertEqual(self.word('minute_log', 187), 1)
        self.tick()
        self.assertEqual(self.word('minute_log', 187), 0)
        self.assertEqual(self.get(3), 0)

    def test_boundary_real_two_minute_mismatch_still_faults(self):
        self.mode_run(3)
        self.put(22, (self.get(22) - 2) % 720)
        self.tick()
        self.assertEqual(self.get(3), 9)

    def test_boundary_late_reference_without_mode_change_recovers(self):
        for mode in (2, 3):
            with self.subTest(mode=mode):
                self.setUp()
                self.mode_run(mode)
                first_reference = self.word('seconds_log', 255)
                longest_park = parked = 0
                for elapsed in range(1, 185 * 128 + 1):
                    if elapsed % 128 == 0:
                        sod = 23 * 3600 + 45 * 60 + elapsed // 128
                        self.rtc_time(sod // 3600, sod // 60 % 60, sod % 60)
                        self.rtc_poll()
                    target = 1006 if self.word('seconds_log', 255) == first_reference else 960
                    anchor = target - self.seconds_offset - 1
                    pulse = self.word('seconds_log', 248) + 1
                    self.tick(int(anchor <= pulse <= anchor + 15))
                    self.assertEqual(self.get(3), 0, (mode, elapsed))
                    parked = parked + 1 if self.get(30) else 0
                    longest_park = max(longest_park, parked)
                self.assertLess(longest_park, 4 * 128)
                self.assertEqual(self.get(22), 708)


if __name__ == '__main__':
    unittest.main()
