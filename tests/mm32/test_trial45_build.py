"""Continuous subsequent seconds laps during initial minute catch-up."""
import unittest
import test_trial44_build as prior
import test_reference_scan_build as ref


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_CONTINUOUS_SECONDS_TRIAL45_20261009.axf'
    signature = 0x4d503435
    defines = prior.Tests.defines + ['-DCONTINUOUS_CATCHUP_SECONDS']

    def near_reference(self, stage=10, second=0):
        self.running(); self.put(2, stage); self.put(22, 600)
        self.put(5, second); self.setword('rtc_pace', 4, 1)
        self.setword('rtc_pace', 2, 60)
        for i, v in ((248,959),(251,892),(252,1),(253,16),(254,960)):
            self.setword('seconds_log', i, v)

    def test_return_just_after_00_does_not_wait_another_minute(self):
        self.near_reference(); self.setword('rtc_boundary', 0, 1)
        # The :00 edge is consumed before the last pulse reaches physical 12.
        for _ in range(128): self.hold(0, 1, poll=False)
        self.assertEqual(self.get(3), 0)
        self.assertEqual(self.get(2), 10)
        self.assertGreater(self.get(12), 12)
        self.assertEqual(self.word('seconds_log', 255), 1)
        self.assertEqual(self.get(30), 0)

    def test_catchup_retains_normal_phase_tolerance_and_correction_hold(self):
        for second in (0, 1, 8, 9, 59):
            self.setUp(); self.near_reference(second=second)
            for _ in range(24): self.hold(0, 1, poll=False)
            self.assertEqual(self.get(30), int(second>8))
            self.assertEqual(self.get(12)>1, second<=8)
        for correction in (1, 2):
            self.setUp(); self.near_reference()
            self.setword('daily_log', 13, correction)
            for _ in range(24): self.hold(0, 1, poll=False)
            self.assertEqual(self.get(12), int(correction==1))
            self.assertEqual(self.get(30), int(correction==1))

    def test_three_full_laps_during_minute_catchup_have_no_minute_parking(self):
        self.running(); self.put(2, 10); self.put(22, 0)
        self.put(5, 0); self.setword('rtc_pace', 4, 1)
        self.setword('rtc_pace', 2, 0)
        self.setword('rtc_release_edge', 0, 0)
        self.call('parallel_seconds_runtime_begin')
        start = self.get(4); last_active = False; rise = None
        widths = []; intervals = []; parked_ticks = 0
        parked_streak = max_parked_streak = 0
        for elapsed in range(1, 128*181+1):
            # Advance the RTC model at 128Hz; inject a fresh :00 edge once/minute.
            self.put(5, (elapsed//128)%60)
            self.setword('rtc_pace', 2, elapsed//128)
            self.setword('rtc_edge_tick', 0, start+(elapsed//128)*128)
            self.setword('rtc_boundary', 0, int(elapsed%(128*60)==0))
            p = self.word('seconds_log', 248)+1
            self.tick(int(891<=p<=906))
            self.assertEqual(self.get(3), 0)
            active = bool(self.word('second_active'))
            if active and not last_active:
                if rise is not None: intervals.append(self.get(4)-rise)
                rise = self.get(4)
            if last_active and not active: widths.append(self.get(4)-rise)
            last_active = active
            parked_ticks += bool(self.get(30))
            parked_streak = parked_streak+1 if self.get(30) else 0
            max_parked_streak = max(max_parked_streak, parked_streak)
        self.assertEqual(self.get(2), 10)  # Minutes still setting time.
        self.assertGreaterEqual(self.word('seconds_log', 255), 3)
        self.assertGreater(self.get(23), 0)
        self.assertTrue(widths and all(w==6 for w in widths))
        self.assertTrue(intervals and all(7<=w<=9 for w in intervals))
        # Reaching 12 one tick BEFORE :00 may legitimately wait that tick.
        # The following pulse-start interval still must be at most nine ticks.
        self.assertLessEqual(parked_ticks, 3)
        self.assertLessEqual(max_parked_streak, 2)


if __name__ == '__main__': unittest.main()
