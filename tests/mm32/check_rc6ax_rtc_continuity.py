"""RC6AX actual ARM/RTC/timer-model checks; no physical RTC/motor emulation."""
import unittest
from pathlib import Path
from check_rc6aw_time_handoff import Tests as Prior, ButtonTests as ButtonPrior


class Tests(Prior):
    artifact = Path(__file__).parent / 'release_candidate_rc6ax/build/MM32SPIN05PF_RTC_CONTINUITY_RC6AX_20261023.axf'
    signature = 0x4d50529b

    def corrected(self, style=3, delta=3600, hour=19, minute=59):
        _, due = self.queue_correction(style=style, delta=delta, hour=hour, minute=minute)
        self.setword('seconds_log', 227, due)
        self.call('daily_poll')
        self.assertEqual(self.word('wifi_rtc', 15), 1)
        self.assertEqual(self.word('seconds_log', 223), 1)
        self.assertEqual(self.word('seconds_log', 226), 2)
        return self.word('seconds_log', 227)

    def sample(self):
        self.put(4, self.get(4) + 4)  # Respect normal calendar read cadence.
        self.call('rtc_pace_poll')

    def test_rec_rehome_preserves_rtc_sampling_words(self):
        self.start_pwm()
        self.fixture_clock()
        before = [self.word('seconds_log', i) for i in range(221, 228)]
        self.assertGreater(before[-1], 0)
        self.advance_timer(10000)
        self.setword('minute_log', 227, 2)
        self.setword('minute_log', 229, 1)
        for _ in range(32):
            self.tick()
            if self.get(2) == 1:
                break
        self.assertEqual(self.get(2), 1)
        self.assertEqual(self.get(3), 0)
        self.assertEqual(self.word('seconds_log', 218), 0)
        self.assertEqual([self.word('seconds_log', i) for i in range(221, 228)], before)

    def test_catchup_completion_clears_owner_without_reparking_seconds(self):
        _, due = self.queue_correction()
        self.setword('seconds_log', 227, due)
        self.call('daily_poll')
        corrected = self.result('rtc_motion_stamp')
        writes, hook = self.trace()
        for elapsed in range(3200):
            if elapsed and elapsed % 128 == 0:
                sod = (corrected + elapsed // 128) % 86400
                self.rtc_time(sod // 3600, sod // 60 % 60, sod % 60)
            # Model the normal main loop, not a single poll per second.
            # Runtime rebaselining must observe a baseline and then an edge
            # inside the existing 1.5-second RTC sampling window.
            if elapsed % 4 == 0:
                self.rtc_poll()
            self.tick()
            self.advance_timer(3906)
            self.assertEqual(self.get(3), 0, (elapsed, self.get(3)))
            if self.get(2) == 7:
                break
        self.cpu.hook_del(hook)
        self.assertEqual(self.get(2), 7)
        self.assertEqual(self.get(26), 1)
        self.assertEqual(self.word('daily_log', 13), 0)
        self.assertEqual(self.word('minute_log', 151), 0)
        self.assertGreater(sum(bool(e[2]) for e in self.pad_edges), 100)
        self.assertFalse([(a, v) for a, v in writes if a in
            (0x40000400, 0x40000408, 0x40000414, 0x40000424, 0x40000428)])

    def test_backward_recovery_completes_sensor_homing(self):
        _, due = self.queue_correction(delta=-3600)
        self.setword('seconds_log', 227, due)
        self.call('daily_poll')
        corrected = self.result('rtc_motion_stamp')
        schedule = self.word('daily_log', 3)
        for elapsed in range(1, 6500):
            if elapsed % 128 == 0:
                sod = (corrected + elapsed // 128) % 86400
                self.rtc_time(sod // 3600, sod // 60 % 60, sod % 60)
            if elapsed % 4 == 0:
                self.rtc_poll()
            if self.get(19) == 2:
                high = int(self.get(20) + int(bool(self.word('minute_active'))) >= 73)
            else:
                high = int(246 <= self.word('seconds_log', 5) + 1 <= 262)
            self.tick(high)
            self.assertEqual(self.get(3), 0, (elapsed, self.get(3)))
            if self.word('minute_log', 204) == 0 and self.get(7) and self.get(8):
                break
        self.assertEqual((self.get(7), self.get(8)), (1, 1))
        self.assertEqual(self.word('minute_log', 204), 0)
        self.assertEqual(self.word('daily_log', 3), schedule)
        self.assertEqual(self.word('minute_log', 229), 0)

    def test_first_postwrite_wrong_hour_rejected_all_modes(self):
        for style in range(4):
            for hour in (20, 22):
                with self.subTest(style=style, hour=hour):
                    self.setUp()
                    expected = self.corrected(style)
                    self.rtc_time(hour, 0, 0)
                    writes, hook = self.trace()
                    edge = self.word('rtc_edge_tick')
                    self.sample()
                    self.cpu.hook_del(hook)
                    self.assertEqual(self.word('seconds_log', 227), expected)
                    self.assertEqual(self.get(16), 21)
                    self.assertEqual(self.word('rtc_edge_tick'), edge)
                    self.assertEqual(self.word('rtc_pace', 9), 1)
                    self.assertEqual(self.word('rtc_pace', 11), 4)
                    self.assertEqual(self.get(3), 0)
                    self.assertFalse([(a, v) for a, v in writes if
                        0x40000400 <= a <= 0x40000450 or 0x40012c00 <= a <= 0x40012c50])

    def test_transient_bad_read_recovers_without_reseed_or_phase_change(self):
        expected = self.corrected()
        edge = self.word('rtc_edge_tick')
        self.rtc_time(22, 0, 0)
        self.sample()
        self.rtc_time(21, 0, 0)
        self.sample()
        self.assertEqual(self.word('seconds_log', 227), expected)
        self.assertEqual(self.word('seconds_log', 223), 3)
        self.assertEqual(self.word('seconds_log', 226), 2)
        self.assertEqual(self.word('rtc_pace', 9), 0)
        self.assertEqual(self.word('rtc_edge_tick'), edge)
        self.assertEqual(self.get(3), 0)

    def test_first_advancing_read_is_rate_anchor_not_new_civil_phase(self):
        for skew in (-2, -1, 0, 1, 2):
            with self.subTest(skew=skew):
                self.setUp()
                expected = self.corrected(hour=19, minute=58)
                # Corrected time 20:59:00, avoiding midnight in negative skew.
                self.rtc_time(20, 58 if skew < 0 else 59, 60 + skew if skew < 0 else skew)
                self.sample()
                self.assertEqual(self.word('seconds_log', 223), 3)
                self.put(4, self.get(4) + 128)
                # Model one elapsed civil tick; rtc_window_tick is inlined.
                self.setword('seconds_log', 227, expected + 1)
                self.setword('rtc_edge_tick', 0, self.word('rtc_edge_tick') + 128)
                self.put(5, 1)
                projected = self.word('seconds_log', 227)
                edge = self.word('rtc_edge_tick')
                second = skew + 1
                self.rtc_time(20, 58 if second < 0 else 59, 60 + second if second < 0 else second)
                self.call('rtc_pace_poll')
                self.assertEqual(self.word('seconds_log', 227), projected)
                self.assertEqual(projected, expected + 1)
                self.assertEqual(self.word('rtc_edge_tick'), edge)
                self.assertEqual(self.word('seconds_log', 226), 1)
                self.assertEqual(self.get(3), 0)

    def test_three_wrong_reads_fault_without_adopting_wrong_hour(self):
        expected = self.corrected()
        self.rtc_time(22, 0, 0)
        for _ in range(3):
            self.sample()
        self.assertEqual(self.word('seconds_log', 227), expected)
        self.assertEqual(self.get(16), 21)
        self.assertEqual(self.get(3), 9)

    def test_startup_still_seeds_and_aligns_first_edge(self):
        self.held_fixture()
        self.put(6, 1)
        self.setword('rtc_clock_seeded', 0, 0)
        self.setword('seconds_log', 223, 0)
        self.rtc_time(12, 34, 55)
        self.call('rtc_pace_poll')
        self.assertEqual((self.get(16), self.get(15), self.get(5)), (12, 34, 55))
        self.assertEqual(self.word('seconds_log', 226), 0)
        self.put(4, self.get(4) + 128)
        self.rtc_time(12, 34, 56)
        self.call('rtc_pace_poll')
        self.assertEqual(self.word('seconds_log', 226), 1)
        self.assertEqual(self.get(5), 56)
        self.assertEqual(self.get(3), 0)


class ButtonTests(ButtonPrior):
    artifact = Tests.artifact
    signature = Tests.signature


if __name__ == '__main__':
    import sys
    if '--focused' in sys.argv:
        names = [n for n in Tests.__dict__ if n.startswith('test_')]
    else:
        names = [n for n in Tests.__dict__ if n.startswith('test_')]
        names += [n for n in Prior.__dict__ if n.startswith('test_') and n not in names]
        names += ['test_echo_exact_complete_record_only_after_settings_processed',
                  'test_sleep_closes_lease_without_reply_or_motor_change',
                  'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
                  'test_bad_incomplete_and_non_time_lines_do_not_echo',
                  'test_stop_modes_first_pulse_normal_then32_safe_updates',
                  'test_daily_correction_resumes_all_styles_without_rebuilding_timer']
    suite = unittest.TestSuite(Tests(n) for n in names)
    if '--focused' not in sys.argv:
        suite.addTest(ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
