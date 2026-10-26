"""End Wi-Fi acquisition after safe TIME retention, independently of hands."""
import sys,unittest
from pathlib import Path
from check_rc6bd_pending_session import PendingSession,baseline,Handover,Deadline

class SessionSleep(PendingSession):
    artifact=Path(__file__).resolve().parents[2]/'firmware/mm32/build/MM32SPIN05PF_SESSION_SLEEP_RC6BE_20261026.axf'
    signature=0x4d5052a2

    def busy(self,style=3,stage=10):
        self.queue_correction(style=style,delta=0)
        self.put(2,stage)
        self.setword('daily_log',0,2);self.setword('daily_log',13,0)
        self.setword('daily_log',4,self.get(4))
        self.setword('minute_log',211,1);self.setword('minute_log',212,0)
        self.setword('minute_log',217,0)
        self.count=self.word('uart_probe_good_time')
        self.setword('daily_log',5,self.count)
        # Direct parser fixtures must supply the current RX-end timestamp,
        # just as the real receive IRQ does for this new session's record.
        self.setword('rx_time_end_tick',0,self.get(4))
        self.consume(f'+TIME:Thu Oct 22 14:20:05 2026 +0100 10:00 {style}0\r\n'.encode())
        self.assertTrue(self.word('minute_log',155)&0x80000000)

    def test_retained_time_closes_acquisition_before_hand_setting_all_modes(self):
        for style in range(4):
            for stage in (1,4,10,11):
                with self.subTest(style=style,stage=stage):
                    self.setUp();self.busy(style,stage)
                    pending=[self.word('minute_log',i) for i in range(153,157)]
                    frozen=self.frozen();epoch=self.word('seconds_log',215)
                    writes,hook=self.trace();self.call('daily_poll');self.cpu.hook_del(hook)
                    self.assertEqual(self.word('daily_log',0),3)
                    self.assertEqual(self.word('minute_log',211),0)
                    self.assertEqual(self.get(2),stage)
                    self.assertEqual([self.word('minute_log',i) for i in range(153,157)],pending)
                    self.assertEqual(self.word('uart_probe_good_time'),self.count)
                    self.assertEqual(self.frozen(),frozen)
                    self.assertEqual(self.word('seconds_log',215),epoch)
                    self.assertFalse([(a,v) for a,v in writes if 0x40000400<=a<0x40000450 or 0x40014000<=a<0x40014050])
                    self.assertEqual(self.get(28),2) # blue after power-down, not after hand completion
                    self.assertEqual(self.get(3),0)

    def test_record_survives_power_down_and_is_aged_after_catchup(self):
        self.busy();self.call('daily_poll')
        self.assertEqual(self.word('minute_log',211),0)
        stamp=self.word('seconds_log',227);origin=self.word('minute_log',156)
        self.put(4,(origin+15*128+47)&0xffffffff);self.put(2,7)
        self.setword('seconds_log',227,stamp+15)
        self.call('pending_time_poll')
        self.assertEqual(self.word('minute_log',155),0)
        self.assertEqual(self.word('uart_probe_good_time'),self.count+1)
        self.assertEqual(self.result('rtc_event_stamp',self.symbols['uart_probe_time_event']),stamp+15)
        self.assertEqual(self.word('published_time_tick'),(origin+15*128)&0xffffffff)
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.get(3),0)

    def test_mset_access_window_expires_without_waiting_for_hands(self):
        self.busy();self.setword('minute_log',217,1)
        self.setword('minute_log',218,self.get(4)+10)
        self.setword('minute_log',219,self.word('uart_probe_good_tick'))
        self.call('daily_poll')
        self.assertEqual(self.word('daily_log',0),3)
        self.assertEqual(self.word('minute_log',211),1)
        self.put(4,self.get(4)+11);self.call('parallel_poll_once')
        self.assertEqual(self.word('minute_log',217),0)
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.get(2),10)
        self.assertTrue(self.word('minute_log',155)&0x80000000)

    def test_active_webpage_still_retains_radio_lease(self):
        self.busy();self.setword('minute_log',217,1)
        self.setword('minute_log',218,self.get(4)+10)
        self.setword('minute_log',219,self.word('uart_probe_good_tick'))
        self.call('daily_poll');self.put(4,self.get(4)+11)
        self.consume(b'+TICK\r\n');self.call('parallel_poll_once')
        self.assertEqual(self.word('minute_log',217),1)
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(self.word('daily_log',0),3)
        self.assertEqual(self.get(2),10)

    def test_stale_mailbox_cannot_complete_a_new_acquisition(self):
        self.busy();self.setword('daily_log',4,self.get(4)+128)
        self.call('daily_poll')
        self.assertEqual(self.word('daily_log',0),2)
        self.assertEqual(self.word('minute_log',211),1)
        self.assertTrue(self.word('minute_log',155)&0x80000000)
        self.setword('daily_log',4,self.get(4));self.setword('minute_log',212,0)
        self.call('daily_poll')
        self.assertEqual(self.word('daily_log',0),2)
        self.assertEqual(self.word('minute_log',211),1)

    def test_active_correction_is_not_ended_by_retained_time(self):
        for state,phase in ((7,1),(2,3)):
            self.setUp();self.busy();self.setword('daily_log',0,state);self.setword('daily_log',13,phase)
            self.setword('minute_log',150,123456);self.setword('minute_log',186,0)
            pending=[self.word('minute_log',i) for i in range(153,157)]
            self.call('daily_poll')
            self.assertEqual(self.word('daily_log',0),state)
            self.assertEqual(self.word('daily_log',13),phase)
            self.assertEqual(self.word('minute_log',150),123456)
            self.assertEqual([self.word('minute_log',i) for i in range(153,157)],pending)
            self.assertEqual(self.word('minute_log',211),1)

    def test_session_freshness_check_handles_tick_wrap(self):
        self.busy();self.put(4,3)
        self.setword('daily_log',4,0xfffffff8)
        self.setword('minute_log',156,0xfffffffa)
        self.call('daily_poll')
        self.assertEqual(self.word('daily_log',0),3)
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.word('minute_log',156),0xfffffffa)

    def test_rec_and_clean_ownership_are_not_ended_by_retained_time(self):
        for owner in (229,230):
            self.setUp();self.busy();self.setword('minute_log',owner,1)
            self.call('daily_poll')
            self.assertEqual(self.word('daily_log',0),2)
            self.assertEqual(self.word('minute_log',211),1)
            self.assertTrue(self.word('minute_log',155)&0x80000000)

if __name__=='__main__':
    for cls in (PendingSession,baseline.Tests,baseline.Buttons,baseline.General,baseline.RTCChecks,baseline.RecoveryChecks,Handover,Deadline):
        cls.artifact=SessionSleep.artifact;cls.signature=SessionSleep.signature
    selected=[SessionSleep(n) for n in SessionSleep.__dict__ if n.startswith('test_')]
    if '--pending' in sys.argv:selected=[PendingSession(n) for n in PendingSession.__dict__ if n.startswith('test_')]
    if '--handover' in sys.argv:selected=[Handover(n) for n in Handover.__dict__ if n.startswith('test_')]
    if '--deadline' in sys.argv:selected=[Deadline(n) for n in Deadline.__dict__ if n.startswith('test_')]
    if '--regression' in sys.argv:selected=baseline.cases()
    if '--motor' in sys.argv:selected=[baseline.Tests(n) for n in (
        'test_normal_modes_keep_original_waveforms_and_no_ramp',
        'test_two_laps_and_normal_launch_again_after_hold',
        'test_late_ramp_irq_does_not_change_active_pulse',
        'test_overnight_stop_mode_resumes_with_ramp_without_second_timer_launch',
        'test_always_parked_never_launches_seconds_during_catchup_all_styles',
        'test_always_parked_runtime_minute_width_is_valid_without_seconds_launch',
        'test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
        'test_saver_change_alone_finishes_one_safe_restart')]
    if '--part=1' in sys.argv:selected=selected[::2]
    if '--part=2' in sys.argv:selected=selected[1::2]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    raise SystemExit(not result.wasSuccessful())
