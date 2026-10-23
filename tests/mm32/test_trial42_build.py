"""Manual webpage lease on the compiled Trial41 baseline."""
import struct
import unittest
import test_trial41_build as prior
import test_reference_scan_build as ref


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_MANUAL_WEB_WAKE_TRIAL42_20261009.axf'
    signature = 0x4d503432
    defines = prior.Tests.defines + ['-DBUTTON_WEB_LEASE']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for offset, name in enumerate(('manual_web_active', 'manual_web_deadline', 'manual_web_tick_seen')):
            cls.symbols[name] = cls.symbols['minute_log'] + (217+offset)*4

    def poll_at(self, tick):
        self.put(4, tick)
        self.setword('rtc_edge_tick', 0, tick)
        self.setword('rtc_poll_tick', 0, tick)
        self.call('parallel_poll_once')

    def test_web_time_receipt_does_not_end_sixty_second_lease(self):
        self.running(); self.hold(2)
        start = self.get(4)
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log'), 3)
        self.assertTrue(self.output & 16)
        self.poll_at(start+7679)
        self.assertTrue(self.output & 16)
        self.poll_at(start+7680)
        self.assertFalse(self.output & 16)
        self.assertEqual((self.get(2), self.get(3)), (7, 0))

    def test_web_tick_extends_until_ten_seconds_after_last_heartbeat(self):
        self.running(); self.hold(2)
        start = self.get(4)
        self.setword('daily_log', 0, 3)
        self.poll_at(start+7552)
        self.feed(b'+TICK\r\n')
        self.poll_at(start+7680)
        self.assertTrue(self.output & 16)
        self.poll_at(start+8831)
        self.assertTrue(self.output & 16)
        self.poll_at(start+8832)
        self.assertFalse(self.output & 16)

    def test_web_short_early_tick_cannot_shorten_minimum(self):
        self.running(); self.hold(2)
        deadline = self.word('manual_web_deadline')
        self.feed(b'+TICK\r\n')
        self.assertEqual(self.word('manual_web_deadline'), deadline)

    def test_web_repeated_press_restarts_minimum_without_power_cycle(self):
        self.running(); self.hold(2); self.hold(0, 4)
        old = self.word('manual_web_deadline')
        self.hold(2)
        self.assertGreater(self.word('manual_web_deadline'), old)
        self.assertEqual(self.word('manual_web_deadline'), self.get(4)+7680)

    def test_web_automatic_wake_has_no_manual_lease(self):
        self.running(); self.due()
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('manual_web_active'), 0)
        self.assertFalse(self.output & 16)

    def test_web_rec_and_fault_override_lease(self):
        self.running(); self.hold(2); self.hold(0, 4); self.hold(1, 410)
        self.assertEqual(self.word('manual_web_active'), 0)
        self.assertFalse(self.output & 16)
        self.setUp(); self.running(); self.hold(2)
        self.call('Default_Handler')
        self.assertFalse(self.output & 16)

    def test_web_pending_correction_time_cannot_be_overwritten(self):
        self.running(); self.hold(2)
        self.feed(b'+TIME:Wed Oct  7 23:45:22 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log'), 7)
        count = self.word('uart_probe_good_time')
        self.feed(b'+TIME:Wed Oct  7 23:45:25 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('uart_probe_good_time'), count)
        self.assertEqual(self.word('uart_probe_last_second'), 22)
        ticks = self.word('uart_probe_good_tick')
        self.feed(b'+TICK\r\n')
        self.assertEqual(self.word('uart_probe_good_tick'), ticks+1)

    def test_web_malformed_tick_does_not_extend_lease(self):
        self.running(); self.hold(2)
        deadline = self.word('manual_web_deadline')
        self.poll_at(deadline-128)
        self.feed(b'+TICX\r\n')
        self.assertEqual(self.word('manual_web_deadline'), deadline)

    def test_web_lease_deadline_handles_tick_wrap(self):
        self.running()
        self.setword('manual_web_active', 0, 1)
        self.setword('manual_web_deadline', 0, 100)
        self.poll_at(0xfffffff0)
        self.assertTrue(self.output & 16 or self.word('manual_web_active'))
        self.poll_at(99)
        self.assertEqual(self.word('manual_web_active'), 1)
        self.poll_at(100)
        self.assertEqual(self.word('manual_web_active'), 0)


if __name__ == '__main__': unittest.main()
