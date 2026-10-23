"""Compiled Trial43: independent acquisition, power-gated LEDs, silence cap."""
import struct
import unittest
import test_trial42_build as prior
import test_reference_scan_build as ref


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_INDEPENDENT_HOME_LED_WAKE_TRIAL43_20261009.axf'
    signature = 0x4d503433
    defines = prior.Tests.defines + ['-DTRIAL43']

    def test_timeout_leds_off_and_motion_continues(self):
        self.running(); self.due()
        start = self.get(4)
        self.poll_at(start+38399)
        self.assertEqual(self.word('daily_log'), 2)
        self.assertTrue(self.output & 16)
        self.poll_at(start+38400)
        self.assertEqual(self.word('daily_log'), 5)
        self.assertEqual((self.get(2), self.get(3), self.get(28)), (7, 0, 0))
        self.assertFalse(self.output & 16)

    def test_tick_refreshes_silence_deadline_but_bad_line_does_not(self):
        self.running(); self.due(); start = self.get(4)
        self.poll_at(start+38000); self.feed(b'+TICK\r\n')
        self.poll_at(start+38400)
        self.assertEqual(self.word('daily_log'), 2)
        self.feed(b'+TICX\r\n')
        self.poll_at(start+76399)
        self.assertTrue(self.output & 16)
        self.poll_at(start+76400)
        self.assertFalse(self.output & 16)
        self.assertEqual(self.get(28), 0)

    def test_startup_silent_timeout_is_five_minutes(self):
        self.put(1, 1); self.tick()
        self.put(2, 4); self.put(7, 1); self.put(8, 1)
        self.put(4, 38398); self.tick()
        self.assertEqual(self.get(3), 0)
        self.tick()
        self.assertEqual((self.get(2), self.get(3), self.get(28)), (6, 6, 0))
        self.assertFalse(self.output & 16)

    def test_manual_red_stays_until_actual_off_then_blue(self):
        self.running(); self.hold(2); start = self.get(4)
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.get(28), 4)
        self.assertTrue(self.output & 16)
        for _ in range(256):
            self.hold(2, 1)
            self.assertEqual(self.get(28), 4)
            self.assertTrue(self.output & 8)  # Blue inactive.
        self.poll_at(start+7680)
        self.assertFalse(self.output & 16)
        self.assertEqual(self.get(28), 2)
        self.assertEqual(self.get(29), start+7680)

    def test_startup_time_and_powerdown_start_blue(self):
        self.put(1, 1); self.tick(); self.seed()
        self.assertFalse(self.output & 16)
        self.assertEqual(self.get(28), 2)

    def test_button_clean_exact_protocol_and_ack_while_motors_run(self):
        # CLEAN is not a valid TIME and must not show time-success blue.
        self.running(); self.hold(3)
        self.writes.clear()
        self.cpu.mem_write(0x40004408, struct.pack('<I', 1))
        self.hold(3, 530)
        self.assertEqual(bytes(v for a, v in self.writes if a == 0x40004400),
                         b'CLEAN\nCLEAN\n')
        self.feed(b'CLEAN_OK\r\n')
        self.assertEqual((self.button(10), self.button(15), self.get(28)), (0, 1, 0))
        self.assertEqual(self.get(2), 7)

    def test_startup_releases_seconds_before_minute_setting_finishes(self):
        self.running(); self.put(26, 0); self.put(2, 10)
        self.put(22, 600); self.setword('rtc_pace', 4, 1)
        self.put(5, 0); self.setword('rtc_boundary', 0, 1)
        self.tick()
        self.assertEqual((self.get(26), self.get(2)), (1, 10))
        self.assertEqual(self.get(3), 0)
        for _ in range(100): self.hold(0, 1, poll=False)
        self.assertGreater(self.get(12), 10)
        self.assertGreater(self.get(23), 0)

    def test_startup_cannot_release_before_minute_homed_or_without_new_00(self):
        self.running(); self.put(26, 0); self.put(2, 10); self.put(22, 600)
        self.put(7, 0); self.setword('rtc_pace', 4, 1)
        self.setword('rtc_boundary', 0, 1); self.tick()
        self.assertEqual(self.get(26), 0)
        self.put(7, 1); self.tick()
        self.assertEqual(self.get(26), 0)

    def independent_home(self, minute_entry, seconds_entry):
        self.put(1, 1); self.tick(); self.seed()
        self.put(16, 0); self.put(15, 2)
        first = None
        for _ in range(12000):
            high = 0
            if self.get(19)==1:
                high = int(seconds_entry <= self.word('seconds_log',5)+1 <= seconds_entry+16)
            elif self.get(19)==2:
                high = int(self.word('minute_log',5)+1 >= minute_entry)
            self.setword('rtc_edge_tick', 0, self.get(4))
            self.tick(high)
            if first is None and (self.get(7) or self.get(8)):
                first = (self.get(7), self.get(8), self.get(21))
            if first and first[1] and not self.get(7):
                self.assertEqual(self.get(21), first[2])
            if self.get(7) and not self.get(8) and self.get(23):
                self.assertEqual(self.get(2), 1)
            if self.get(2) in (10,11,6): break
        self.assertEqual(self.get(3), 0)
        self.assertEqual((self.get(7), self.get(8)), (1, 1))
        return first

    def test_real_minutes_first_sets_time_while_seconds_still_homing(self):
        first = self.independent_home(13, 900)
        self.assertEqual(first[:2], (1, 0))
        self.assertGreater(self.get(23), 0)
        self.assertEqual(self.get(22), 2)

    def test_real_seconds_first_parks_until_minutes_finish_homing(self):
        first = self.independent_home(130, 246)
        self.assertEqual(first[:2], (0, 1))
        self.assertEqual(self.get(26), 0)


if __name__ == '__main__': unittest.main()
