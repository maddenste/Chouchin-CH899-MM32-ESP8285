"""Actual RC6AZ ARM plus timer/RTC models; no physical motor simulation."""
import datetime as dt
import unittest
from unicorn import UC_HOOK_CODE
from pathlib import Path
from check_rc6ay_second_sync import Tests as Prior, Buttons as PriorButtons


class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6az/build/MM32SPIN05PF_IMMEDIATE_SET_RC6AZ_20261023.axf'
    signature=0x4d50529d
    urgent_word=160

    def moving_update(self,style=3,delta=-3600,dst=False,minute_powered=False):
        self.start_pwm(style)
        self.advance_timer(self.word('minute_log',181)*45)
        self.assertEqual(self.word('seconds_log',69),0)
        self.setword('seconds_log',219,self.bt_count)
        self.setword('seconds_log',53,self.get(4))
        self.setword('seconds_log',231,self.bt_count)
        self.setword('seconds_log',232,self.get(4))
        self.put(16,14);self.put(15,20);self.put(5,35)
        self.put(22,140)
        self.bus.data[5:9]=[0x22,4,0x10,0x26]
        self.rtc_time(14,20,35)
        target=dt.datetime(2026,10,22,14,20,35)+dt.timedelta(seconds=delta)
        self.setword('minute_log',211,1)
        wire=(target.strftime('+TIME:%a %b %d %H:%M:%S %Y')+
              f' +0100 10:00 {style}0'+(' DST' if dst else '')+'\r\n').encode()
        self.consume(wire)
        source=self.result('rtc_event_stamp',self.symbols['uart_probe_time_event'])-delta
        self.setword('seconds_log',227,source)
        self.setword('rtc_clock_seeded',0,1)
        self.setword('rtc_edge_tick',0,self.get(4))
        self.setword('daily_log',0,2);self.setword('daily_log',12,1)
        self.setword('daily_log',5,self.word('uart_probe_good_time')-1)
        if minute_powered:
            self.setword('request_pulses',0,3)
            self.setword('seconds_log',230,1) # pwm_min_phase: queued minute pulse.
            self.store(0x40014034,(self.mt_count+16)&65535)
            self.store(0x4001400c,2)
            self.advance_timer(16)
            self.assertEqual(self.word('minute_active'),1)
        self.call('daily_poll')
        return source

    def finish_immediate(self):
        start=self.get(4)
        before=len(self.bus.calendar_writes)
        saw_drain=False
        for _ in range(96):
            if self.word('minute_log',self.urgent_word)==1:
                self.assertEqual(len(self.bus.calendar_writes),before)
            self.tick()
            if self.word('minute_log',self.urgent_word)==2:
                saw_drain=True
                self.assertFalse(any(self.pad))
                self.assertEqual(self.word('minute_active'),0)
            self.assertEqual(self.get(3),0)
            self.call('daily_poll')
            if self.word('minute_log',204)==1:
                break
        self.assertTrue(saw_drain)
        self.assertLess(self.get(4)-start,96)
        self.assertEqual(self.word('minute_log',204),1)
        self.assertEqual(self.word('wifi_rtc',15),1)
        self.assertEqual(self.word('minute_log',self.urgent_word),0)
        if self.word('minute_log',155)&0x80000000:
            pending=[self.word('minute_log',i) for i in range(153,157)]
            self.call('pending_time_poll')
            self.assertEqual([self.word('minute_log',i) for i in range(153,157)],pending)
        self.tick()
        self.assertEqual(self.get(2),1)
        self.assertEqual(self.word('minute_log',204),3)
        self.assertEqual(self.get(3),0)

    def test_large_manual_updates_do_not_wait_for_zero_all_styles(self):
        for style in range(4):
            for delta in (-3600,3600):
                with self.subTest(style=style,delta=delta):
                    self.setUp();source=self.moving_update(style,delta)
                    self.assertEqual(self.word('minute_log',self.urgent_word),1)
                    self.assertEqual(self.get(30),0)
                    self.assertEqual(self.get(5),35)
                    self.finish_immediate()
                    self.assertEqual(self.word('seconds_log',227),source+delta)
                    self.assertEqual(self.get(5),35)
                    self.assertEqual(self.word('minute_log',189),style)

    def test_powered_minute_finishes_and_queued_pulses_are_cancelled(self):
        self.moving_update(minute_powered=True)
        before=self.get(13)
        self.finish_immediate()
        self.assertEqual(self.get(13),before+1)
        self.assertEqual(self.word('request_pulses'),0)

    def test_dst_and_small_changes_do_not_enter_immediate_drain(self):
        for delta,dst in ((-3600,True),(3600,True),(-60,False),(60,False)):
            with self.subTest(delta=delta,dst=dst):
                self.setUp();source=self.moving_update(delta=delta,dst=dst)
                self.assertEqual(self.word('minute_log',self.urgent_word),0)
                self.assertEqual(self.word('minute_log',150),source+25)
                before=len(self.bus.calendar_writes)
                self.tick();self.call('daily_poll')
                self.assertEqual(len(self.bus.calendar_writes),before)
                self.assertEqual(self.get(2),7)
                self.assertEqual(self.get(3),0)

    def test_rec_keeps_priority_over_immediate_correction(self):
        self.moving_update()
        self.setword('minute_log',229,1)
        self.setword('minute_log',227,2)
        before=len(self.bus.calendar_writes)
        for _ in range(32):
            self.tick()
            if self.get(2)==1:break
        self.assertEqual(self.get(2),1)
        self.assertEqual(self.word('minute_log',self.urgent_word),0)
        self.assertEqual(len(self.bus.calendar_writes),before)
        self.assertEqual(self.get(3),0)

    def test_new_time_during_drain_remains_pending_after_rehome(self):
        self.moving_update()
        origin=self.word('correction_time_tick')
        self.consume(b'+TIME:Thu Oct 22 16:00:00 2026 +0100 10:00 30\r\nSLEEP\r\n')
        self.assertTrue(self.word('minute_log',155)&0x80000000)
        self.assertEqual(self.word('correction_time_tick'),origin)
        self.finish_immediate()
        self.assertTrue(self.word('minute_log',155)&0x80000000)

    def test_button_or_restart_during_i2c_is_not_overridden(self):
        for word in (229,230,190):
            with self.subTest(owner_word=word):
                self.setUp();self.moving_update()
                for _ in range(32):
                    self.tick()
                    if self.word('minute_log',self.urgent_word)==2:break
                self.assertEqual(self.word('minute_log',self.urgent_word),2)
                injected=[]
                def take_ownership(cpu,address,size,user):
                    injected.append(address)
                    self.setword('minute_log',word,1)
                    if word==229:
                        self.put(2,1)
                        self.setword('daily_log',0,0)
                        self.setword('daily_log',13,0)
                        self.setword('minute_log',self.urgent_word,0)
                address=self.symbols['rtc_motion_set']&~1
                hook=self.cpu.hook_add(UC_HOOK_CODE,take_ownership,begin=address,end=address)
                self.cpu.ctl_remove_cache(0x08000000,0x08008000)
                self.call('daily_poll')
                self.cpu.hook_del(hook)
                self.assertTrue(injected,'Ownership injection hook must execute')
                self.assertNotEqual(self.word('minute_log',204),1)
                self.assertEqual(self.word('minute_log',word),1)
                self.assertEqual(self.word('wifi_rtc',15),1)
                self.assertEqual(self.get(3),0)

    def test_time_between_correction_and_rehome_stays_in_mailbox(self):
        self.moving_update()
        for _ in range(32):
            self.tick()
            if self.word('minute_log',self.urgent_word)==2:break
        self.call('daily_poll')
        self.assertEqual(self.word('minute_log',204),1)
        count=self.word('uart_probe_good_time')
        self.consume(b'+TIME:Thu Oct 22 16:00:00 2026 +0100 10:00 30\r\n')
        self.assertEqual(self.word('uart_probe_good_time'),count)
        self.assertTrue(self.word('minute_log',155)&0x80000000)
        self.call('parallel_poll_once')
        self.assertTrue(self.word('minute_log',155)&0x80000000)
        self.assertEqual(self.word('minute_log',204),1)
        self.tick()
        self.assertEqual(self.get(2),1)
        self.assertTrue(self.word('minute_log',155)&0x80000000)


class Buttons(PriorButtons):
    artifact=Tests.artifact
    signature=Tests.signature


if __name__=='__main__':
    import sys
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names += [n for n in Prior.__dict__ if n.startswith('test_')]
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
    cases=[Tests(n) for n in names]
    cases.append(Buttons('test_mset_wakes_during_each_correction_stage_without_motor_changes'))
    if '--part=1' in sys.argv:cases=cases[::2]
    if '--part=2' in sys.argv:cases=cases[1::2]
    suite=unittest.TestSuite(cases)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
