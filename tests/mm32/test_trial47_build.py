"""Compiled Trial47: bounded RTC read retries and three-second grace."""
import unittest
import test_trial46_build as prior
import test_reference_scan_build as ref


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_RTC_READ_RETRY_TRIAL47_20261009.axf'
    signature = 0x4d503437
    defines = prior.Tests.defines + ['-DRTC_READ_GRACE']

    def rtc_poll(self):
        self.setword('rtc_poll_tick', 0, (self.get(4)-2) & 0xffffffff)
        self.call('parallel_poll_once')

    def assert_rtc_fault(self,code):
        parking='-DRELEASE_HARDENING' in self.defines and self.get(7) and self.get(8)
        self.assertEqual((self.get(2),self.get(3)),(14 if parking else 6,code))
        if parking:
            self.assertEqual(self.word('release_state',0),1)
        else:
            self.released()

    def test_rtc_loss_stops_motors(self):
        self.running()
        good = self.word('minute_log', 214)
        self.bus.ack = False
        self.rtc_poll()
        self.assertEqual(self.get(3), 0)
        self.assertEqual(self.word('rtc_pace', 6), 3)
        self.assertEqual(self.word('minute_log', 216), 4)
        self.put(4, good+384)
        self.rtc_poll()
        self.assert_rtc_fault(8)

    def test_invalid_sixty_retries_into_valid_rollover(self):
        self.running()
        self.rtc_time(23, 45, 59)
        self.setword('rtc_last', 0, 23*3600+45*60+59)
        self.put(5, 59)
        self.bus.calendar_snapshots = [{2: 0x60}, {2: 0, 3: 0x46}]
        self.rtc_poll()
        self.assertEqual((self.get(3), self.get(5), self.get(15)), (0, 0, 46))
        self.assertEqual(self.word('minute_log', 216), 12)
        self.assertEqual(self.word('minute_log', 209), 1)
        self.assertEqual(self.word('rtc_pace', 6), 1)
        self.assertEqual(self.word('rtc_pace', 10), 1)

    def test_invalid_batch_preserves_time_and_motor_pulses(self):
        self.running()
        pulses = self.get(12)
        self.rtc_time(23, 45, 60)
        for _ in range(96):
            self.tick()
            if self.get(4) % 32 == 0:
                self.rtc_poll()
            self.assertEqual(self.get(3), 0)
            self.assertEqual(self.get(5), 23)
        self.assertGreater(self.get(12), pulses)
        self.assertGreater(self.word('minute_log', 215), 0)
        self.rtc_time(23, 45, 24)
        self.rtc_poll()
        self.assertEqual((self.get(3), self.get(5)), (0, 24))
        self.assertEqual(self.word('minute_log', 215), 0)
        self.assertEqual(self.word('minute_log', 209), 1)

    def test_persistent_invalid_sixty_stops_at_three_seconds(self):
        self.running()
        good = self.word('minute_log', 214)
        self.rtc_time(23, 45, 60)
        self.rtc_poll()
        self.put(4, good+383)
        self.rtc_poll()
        self.assertEqual(self.get(3), 0)
        self.put(4, good+384)
        self.rtc_poll()
        self.assert_rtc_fault(8)

    def test_missing_ack_recovers_without_calendar_write(self):
        self.running()
        writes = self.bus.calendar_writes[:]
        self.bus.ack = False
        self.rtc_poll()
        self.bus.ack = True
        self.tick(); self.tick()
        self.rtc_poll()
        self.assertEqual(self.get(3), 0)
        self.assertEqual(self.word('minute_log', 209), 1)
        self.assertEqual(self.bus.calendar_writes, writes)
        self.assertEqual(self.bus.crh & 255, 0x44)

    def test_recovered_two_second_gap_preserves_pacing(self):
        self.running()
        good = self.word('minute_log', 214)
        edges = self.word('rtc_pace', 2)
        reload = self.word('rtc_pace', 1)
        self.bus.ack = False; self.rtc_poll()
        self.put(4, good+256)
        self.bus.ack = True; self.rtc_time(23, 45, 25)
        self.rtc_poll()
        self.assertEqual(self.get(3), 0)
        self.assertEqual(self.word('rtc_pace', 2), edges+2)
        self.assertEqual(self.word('rtc_pace', 1), reload)
        self.assertEqual(self.word('rtc_pace', 3), 0)

    def test_valid_large_jump_is_not_hidden_by_read_grace(self):
        self.running()
        self.bus.ack = False; self.rtc_poll()
        self.bus.ack = True; self.rtc_time(23, 46, 23)
        self.rtc_poll()
        self.assert_rtc_fault(9)

    def test_gap_across_midnight_recovers(self):
        self.running()
        self.rtc_time(23, 59, 59)
        self.setword('rtc_last', 0, 86399)
        self.bus.ack = False; self.rtc_poll()
        self.put(4, self.word('minute_log', 214)+256)
        self.bus.ack = True; self.rtc_time(0, 0, 1)
        self.rtc_poll()
        self.assertEqual((self.get(3), self.get(5), self.get(15), self.get(16)), (0, 1, 0, 0))

    def test_daily_deadline_does_not_use_rejected_raw_calendar(self):
        self.running()
        self.setword('daily_log', 3, 1)
        attempts = self.word('daily_log', 1)
        self.rtc_time(23, 45, 60); self.rtc_poll()
        self.assertEqual(self.word('daily_log', 1), attempts)
        self.assertEqual(self.word('daily_log', 0), 1)
        self.rtc_time(23, 45, 23); self.rtc_poll()
        self.assertEqual(self.word('daily_log', 1), attempts+1)
        self.assertEqual(self.word('daily_log', 0), 2)

    def test_rejection_reasons_are_distinct_and_never_used_as_time(self):
        for raw, reason in [(0x6a, 11), (0x80, 10), (0x60, 12)]:
            self.setUp(); self.running()
            self.bus.data[2] = raw
            self.rtc_poll()
            self.assertEqual(self.word('minute_log', 216), reason)
            self.assertEqual(self.get(5), 23)
            self.assertEqual(self.get(3), 0)

    def test_edge_watchdog_allows_bounded_read_grace_only(self):
        self.running()
        good = self.word('minute_log', 214)
        self.setword('rtc_edge_tick', 0, (good-383) & 0xffffffff)
        self.bus.ack = False; self.rtc_poll()
        for _ in range(383):
            self.tick()
            self.assertEqual(self.get(3), 0)
        self.tick()
        self.assert_rtc_fault(8)

    def test_vl_or_stopped_rtc_is_not_used_for_pacing(self):
        for control, seconds, reason in [(8, 0x80, 10), (0x20, 0x23, 9)]:
            self.setUp(); self.running()
            good = self.word('minute_log', 214)
            self.bus.data[0] = control; self.bus.data[2] = seconds
            self.rtc_poll()
            self.assertEqual(self.get(3), 0)
            self.assertEqual(self.get(5), 23)
            self.assertEqual(self.word('minute_log', 216), reason)
            self.put(4, good+384); self.rtc_poll()
            self.assert_rtc_fault(8)


if __name__ == '__main__': unittest.main()
