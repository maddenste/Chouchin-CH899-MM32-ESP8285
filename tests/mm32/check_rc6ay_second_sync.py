"""Actual RC6AY ARM clock/RTC/UART checks, not physical signal simulation."""
import unittest
from pathlib import Path
from check_rc6ax_rtc_continuity import Tests as Prior, ButtonTests as ButtonPrior


class Tests(Prior):
    artifact = Path(__file__).parent / 'release_candidate_rc6ay/build/MM32SPIN05PF_SECOND_SYNC_RC6AY_20261023.axf'
    signature = 0x4d50529c

    def admit(self, delta=3600, style=3, second=5):
        source, due = self.queue_correction(style=style, delta=delta, second=second)
        self.origin = self.word('correction_time_tick')
        return source, due

    def reach(self, source, due):
        # Old tests jumped calendar words without elapsed monotonic time.
        # Model the same elapsed interval in both clocks for the new contract.
        self.put(4, (self.get(4) + (due - source) * 128) & 0xffffffff)
        self.setword('seconds_log', 227, due)
        self.call('daily_poll')

    def corrected(self, style=3, delta=3600, hour=19, minute=59):
        source,due=self.queue_correction(style=style,delta=delta,hour=hour,minute=minute)
        self.reach(source,due)
        self.assertEqual(self.word('wifi_rtc',15),1)
        self.assertEqual(self.word('seconds_log',223),1)
        self.assertEqual(self.word('seconds_log',226),2)
        return self.word('seconds_log',227)

    def test_forward_dst_keeps_received_phase_all_styles(self):
        for style in range(4):
            with self.subTest(style=style):
                self.setUp()
                source, due = self.admit(style=style)
                writes, hook = self.trace()
                self.reach(source, due)
                self.cpu.hook_del(hook)
                self.assertEqual(self.word('seconds_log', 227), due + 3600)
                self.assertEqual(self.word('rtc_edge_tick'),
                                 (self.origin + (due-source)*128) & 0xffffffff)
                self.assertEqual(self.word('wifi_rtc', 15), 1)
                self.assertEqual(self.get(3), 0)
                self.assertFalse([(a,v) for a,v in writes if a in
                    (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428)])

    def test_late_correction_ages_by_monotonic_ticks_not_old_rtc_seconds(self):
        source, due = self.admit()
        self.put(4, (self.origin + 55*128 + 37) & 0xffffffff)
        self.setword('seconds_log', 227, due + 2) # Old calendar intentionally skewed.
        self.call('daily_poll')
        self.assertEqual(self.word('seconds_log', 227), source + 3600 + 55)
        self.assertEqual((self.get(4)-self.word('rtc_edge_tick')) & 0xffffffff, 37)
        self.assertEqual(self.word('rtc_boundary'),0)
        self.assertEqual(self.word('minute_log',187),0)
        self.assertEqual(self.get(3), 0)

    def test_immutable_origin_survives_new_mailbox_time(self):
        source, due = self.admit()
        origin = self.origin
        self.consume(b'+TIME:Thu Oct 22 18:00:00 2026 +0100 10:00 30\r\n')
        self.assertTrue(self.word('minute_log',155) & 0x80000000)
        self.assertEqual(self.word('correction_time_tick'), origin)
        self.reach(source, due)
        self.assertEqual(self.word('seconds_log',227), due+3600)
        self.assertTrue(self.word('minute_log',155) & 0x80000000)
        self.assertEqual(self.get(3),0)

    def test_backward_dst_still_requests_native_rehome(self):
        source,due=self.admit(delta=-3600)
        self.reach(source,due)
        self.assertEqual(self.word('seconds_log',227),due-3600)
        self.assertEqual(self.word('minute_log',204),1)
        self.assertEqual(self.get(3),0)

    def test_deferred_promotion_retains_fractional_origin(self):
        self.admit()
        self.put(4,self.get(4)+37)
        self.consume(b'+TIME:Thu Oct 22 18:00:00 2026 +0100 10:00 30\r\n')
        origin=self.word('minute_log',156)
        self.put(4,(origin+2*128+47)&0xffffffff)
        self.setword('daily_log',0,1);self.setword('daily_log',13,0)
        self.setword('minute_log',190,0)
        self.put(2,7)
        self.call('pending_time_poll')
        self.assertEqual(self.word('published_time_tick'),(origin+2*128)&0xffffffff)
        self.assertEqual((self.get(4)-self.word('published_time_tick'))&0xffffffff,47)
        self.assertFalse(self.word('minute_log',155)&0x80000000)
        self.assertEqual(self.get(3),0)

    def test_matched_update_rephases_clock_without_motor_or_rtc_write(self):
        self.queue_correction(delta=0)
        self.put(4, 1000)
        self.setword('published_time_tick',0,987)
        self.setword('rtc_edge_tick',0,900)
        self.setword('daily_log',0,2)
        self.setword('daily_log',5,self.word('uart_probe_good_time')-1)
        before = self.word('wifi_rtc',14)
        writes, hook = self.trace()
        self.call('daily_poll')
        self.cpu.hook_del(hook)
        self.assertEqual(self.word('rtc_edge_tick'),987)
        self.assertEqual(self.word('wifi_rtc',14),before)
        self.assertEqual(self.get(3),0)
        self.assertFalse([(a,v) for a,v in writes if a in
            (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428)])

    def test_startup_time_uses_received_origin_and_does_not_reseed_from_rtc(self):
        self.held_fixture()
        self.put(2,1); self.put(6,0)
        self.put(4,1000)
        self.setword('rx_time_end_tick',0,1000)
        self.consume(b'+TIME:Thu Oct 22 12:34:00 2026 +0100 10:00 30\r\n')
        self.put(4,1037)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_edge_tick'),998)
        self.assertEqual((self.get(16),self.get(15),self.get(5)),(12,34,0))
        self.assertEqual(self.word('rtc_clock_seeded'),1)
        self.assertEqual(self.word('seconds_log',226),2)
        self.assertEqual(self.get(3),0)
        self.rtc_time(12,34,1)
        self.put(4,1041)
        self.call('rtc_pace_poll')
        self.assertEqual(self.word('rtc_edge_tick'),998)
        self.assertEqual(self.get(5),0)
        self.assertEqual(self.get(3),0)

    def test_repeated_ageing_keeps_fraction_and_tick_wrap(self):
        self.queue_correction(delta=0)
        for origin in (1000,0xfffffff0):
            with self.subTest(origin=origin):
                self.setUp(); self.queue_correction(delta=0)
                base=self.word('seconds_log',227)
                self.setword('published_time_tick',0,origin)
                for ticks in (37,127,128,165,256):
                    self.put(4,(origin+ticks)&0xffffffff)
                    self.setword('minute_log',208,self.word('uart_probe_good_time')-1)
                    self.setword('daily_log',0,1)
                    self.setword('seconds_log',227,base+ticks//128)
                    self.call('runtime_time_poll')
                    self.assertEqual(self.word('published_time_tick'),(origin+ticks//128*128)&0xffffffff)
                    self.assertEqual(self.word('rtc_edge_tick'),(origin+ticks//128*128)&0xffffffff)
                    self.assertEqual(self.get(3),0)


class Buttons(ButtonPrior):
    artifact=Tests.artifact
    signature=Tests.signature


if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names += ['test_rec_rehome_preserves_rtc_sampling_words',
              'test_first_postwrite_wrong_hour_rejected_all_modes',
              'test_transient_bad_read_recovers_without_reseed_or_phase_change',
              'test_first_advancing_read_is_rate_anchor_not_new_civil_phase',
              'test_three_wrong_reads_fault_without_adopting_wrong_hour',
              'test_startup_still_seeds_and_aligns_first_edge',
              'test_echo_exact_complete_record_only_after_settings_processed',
              'test_sleep_closes_lease_without_reply_or_motor_change',
              'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
              'test_bad_incomplete_and_non_time_lines_do_not_echo',
              'test_stop_modes_first_pulse_normal_then32_safe_updates',
              'test_boot_burst_counted_rejected_but_never_arms_recovery',
              'test_clean_time_cancels_pending_recovery_and_echoes',
              'test_idle_recovery_reconfigures_uart_not_motor_or_clocks',
              'test_recovery_defers_in_unsafe_or_busy_conditions']
    suite=unittest.TestSuite(Tests(n) for n in names)
    suite.addTest(Buttons('test_mset_wakes_during_each_correction_stage_without_motor_changes'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
