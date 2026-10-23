"""Fixed-speed TIME correction: wait at physical 12, keep RTC calibration."""
import unittest
import test_trial47_build as prior
import test_reference_scan_build as ref


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_FIXED_SPEED_TIME_WAIT_TRIAL48_20261009.axf'
    signature = 0x4d503438
    defines = prior.Tests.defines + ['-DFIXED_SPEED_TIME_WAIT']

    def correction(self, h, m, s, delta, arrival_age=0):
        self.running()
        sod = h*3600+m*60+s
        self.put(16, h); self.put(15, m); self.put(5, s)
        self.put(22, (sod//60)%720)
        self.rtc_time(h, m, s); self.setword('rtc_last', 0, sod)
        self.setword('rtc_pace', 4, 1)
        self.setword('rtc_pace', 1, 63475)
        self.due()
        received = (sod+delta)%86400
        day = 7+(sod+delta)//86400
        weekday = {6: 'Tue', 7: 'Wed', 8: 'Thu'}[day]
        self.feed(f'+TIME:{weekday} Oct {day:2} {received//3600:02}:{received//60%60:02}:{received%60:02} 2026 +0100 09:00\r\n'.encode())
        self.assertEqual(self.word('daily_log', 0), 7)
        if arrival_age:
            sod += arrival_age
            self.rtc_time(sod//3600, sod//60%60, sod%60)
            self.setword('rtc_last', 0, sod)
            self.put(16, sod//3600); self.put(15, sod//60%60); self.put(5, sod%60)
            self.put(22, sod//60%720)
            self.rtc_poll()  # Refresh the decoded RTC snapshot used to age TIME.
        self.put(30, 1)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace', 4), 1)
        self.assertEqual(self.word('rtc_pace', 1), 63475)
        self.assertEqual(self.get(3), 0)
        return (sod+delta)%86400

    def elapsed_second(self, sod):
        for _ in range(128):
            p = self.word('seconds_log', 248)+1
            self.tick(int(891 <= p <= 906))
            self.assertEqual(self.get(3), 0)
        if sod >= 86400 and sod%86400 == 0:
            self.bus.data[5] += 1
        sod %= 86400
        self.rtc_time(sod//3600, sod//60%60, sod%60)
        self.rtc_poll()
        self.tick()

    def test_calibrated_small_offsets_have_no_extra_minute(self):
        for delta in [-30, -5, -2, -1, 1, 2, 5, 30]:
            with self.subTest(delta=delta):
                self.setUp()
                sod = self.correction(12, 27, 0, delta)
                wait = (-sod)%60
                self.tick()
                self.assertEqual(self.get(26), 0)
                for elapsed in range(1, wait+1):
                    self.elapsed_second(sod+elapsed)
                    self.assertEqual(self.get(26), int(elapsed==wait))
                self.assertEqual(self.word('daily_log', 13), 0)
                self.assertEqual(self.get(23), 0)  # No full-dial catch-up.
                for _ in range(80): self.tick()
                self.assertEqual(self.get(22), ((sod+wait)//60)%720)
                self.assertGreater(self.get(12), 0)

    def test_backward_two_minutes_waits_without_wrapping(self):
        sod = self.correction(12, 27, 0, -120)
        self.tick()
        for elapsed in range(1, 121):
            self.elapsed_second(sod+elapsed)
            self.assertEqual(self.get(26), int(elapsed==120))
            self.assertEqual(self.get(22), 27)
            self.assertEqual(self.get(23), 0)
        self.assertEqual(self.word('minute_log', 207), 0)

    def test_calendar_only_change_at_zero_releases_without_minute_wait(self):
        # Exactly one day behind, but hands already show the correct HH:MM:SS.
        self.running(); self.put(16, 12); self.put(15, 27); self.put(5, 0); self.put(22, 27)
        self.rtc_time(12, 27, 0); self.setword('rtc_last', 0, 12*3600+27*60)
        self.bus.data[5] = 8; self.bus.data[6] = 4
        self.setword('rtc_pace', 4, 1)
        self.due(); self.feed(b'+TIME:Wed Oct  7 12:27:00 2026 +0100 09:00\r\n')
        self.put(30, 1); self.call('parallel_poll_once'); self.tick()
        self.assertEqual(self.get(26), 1)
        self.assertEqual(self.get(22), 27)
        self.assertEqual(self.get(23), 0)

    def test_time_is_aged_until_physical_twelve(self):
        sod = self.correction(12, 26, 50, -1, arrival_age=10)
        self.assertEqual((self.get(16), self.get(15), self.get(5)), (12, 26, 59))
        self.elapsed_second(sod+1)
        self.assertEqual(self.get(26), 1)
        self.assertEqual(self.get(22), 27)

    def test_backward_one_second_at_midnight(self):
        sod = self.correction(0, 0, 0, -1)
        self.elapsed_second(sod+1)
        self.assertEqual((self.get(16), self.get(15), self.get(5)), (0, 0, 0))
        self.assertEqual(self.get(26), 1)
        self.assertEqual(self.get(22), 0)
        self.assertEqual(self.get(23), 0)

    def test_forward_one_second_crosses_date_without_waiting(self):
        self.correction(23, 59, 59, 1)
        self.tick()
        self.assertEqual(self.get(26), 1)
        for _ in range(80): self.tick()
        self.assertEqual((self.get(16), self.get(15), self.get(22)), (0, 0, 0))
        self.assertEqual(self.get(13), 6)
        self.assertEqual(self.get(23), 0)
        self.assertEqual(self.get(3), 0)

    def test_forward_correction_at_hour_boundary(self):
        sod = self.correction(12, 59, 0, 1)
        for elapsed in range(1, 60):
            self.elapsed_second(sod+elapsed)
            self.assertEqual(self.get(26), int(elapsed==59))
        for _ in range(80): self.tick()
        self.assertEqual((self.get(16), self.get(15), self.get(22)), (13, 0, 60))
        self.assertEqual(self.get(13), 6)
        self.assertEqual(self.get(23), 0)

    def test_other_arrival_phases_do_not_add_a_calibration_minute(self):
        for second, delta in [(59, -5), (30, -1), (30, 1)]:
            with self.subTest(second=second, delta=delta):
                self.setUp()
                sod = self.correction(12, 27, second, delta)
                wait = (-sod)%60
                for elapsed in range(1, wait+1):
                    self.elapsed_second(sod+elapsed)
                    self.assertEqual(self.get(26), int(elapsed==wait))
                self.assertEqual(self.get(23), 0)
                for _ in range(80): self.tick()
                self.assertEqual(self.get(22), (sod+wait)//60%720)


if __name__ == '__main__': unittest.main()
