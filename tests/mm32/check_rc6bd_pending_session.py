"""Deferred TIME during an open Wi-Fi session; compiled ARM, no hardware."""
import unittest
from pathlib import Path
from check_rc6bc_deadline_guard import baseline, Handover, Deadline
import sys

class PendingSession(baseline.Tests):
    artifact=Path(__file__).resolve().parents[2]/'firmware/mm32/build/MM32SPIN05PF_PENDING_SESSION_RC6BD_20261026.axf'
    signature=0x4d5052a1

    def waiting_with_deferred_time(self,style=3,stage=10):
        self.queue_correction(style=style,delta=0)
        self.put(2,stage);self.setword('daily_log',0,2);self.setword('daily_log',13,0)
        self.setword('minute_log',211,1)
        self.count=self.word('uart_probe_good_time')
        self.setword('daily_log',5,self.count)
        self.consume(f'+TIME:Thu Oct 22 14:20:05 2026 +0100 10:00 {style}0\r\n'.encode())
        self.assertEqual(self.word('uart_probe_good_time'),self.count)
        self.assertTrue(self.word('minute_log',155)&0x80000000)
        self.put(2,7)

    def test_waiting_session_promotes_catchup_record_all_modes(self):
        for style in range(4):
            with self.subTest(style=style):
                self.setUp();self.waiting_with_deferred_time(style)
                epoch=self.word('seconds_log',215);pair=self.pair()
                self.call('pending_time_poll')
                self.assertEqual(self.word('minute_log',155),0)
                self.assertEqual(self.word('uart_probe_good_time'),self.count+1)
                self.call('daily_poll')
                self.assertEqual(self.word('daily_log',0),3)
                self.assertEqual(self.word('minute_log',211),0)
                self.assertEqual(self.word('seconds_log',215),epoch)
                self.assertEqual(self.pair(),pair)
                self.assertEqual(self.get(3),0)

    def test_waiting_session_accepts_record_after_each_setting_stage(self):
        for stage in (1,4,10,11):
            self.setUp();self.waiting_with_deferred_time(stage=stage)
            self.call('pending_time_poll')
            self.assertEqual(self.word('minute_log',155),0)
            self.assertEqual(self.word('uart_probe_good_time'),self.count+1)

    def test_published_session_record_is_not_overwritten(self):
        self.waiting_with_deferred_time()
        self.setword('daily_log',5,self.count-1)
        pending=[self.word('minute_log',i) for i in range(153,157)]
        original=bytes(self.cpu.mem_read(self.symbols['uart_probe_time_event'],20))
        self.call('pending_time_poll')
        self.assertEqual([self.word('minute_log',i) for i in range(153,157)],pending)
        self.assertEqual(bytes(self.cpu.mem_read(self.symbols['uart_probe_time_event'],20)),original)
        self.assertEqual(self.word('uart_probe_good_time'),self.count)

    def test_active_correction_and_recovery_still_hold_mailbox(self):
        for owner,index,value in (('daily_log',0,7),('daily_log',13,1),('minute_log',204,1),('minute_log',190,1)):
            self.setUp();self.waiting_with_deferred_time()
            self.setword(owner,index,value)
            pending=[self.word('minute_log',i) for i in range(153,157)]
            self.call('pending_time_poll')
            self.assertEqual([self.word('minute_log',i) for i in range(153,157)],pending)
            self.assertEqual(self.word('uart_probe_good_time'),self.count)

if __name__=='__main__':
    for cls in (baseline.Tests,baseline.Buttons,baseline.General,baseline.RTCChecks,baseline.RecoveryChecks,Handover,Deadline):
        cls.artifact=PendingSession.artifact;cls.signature=PendingSession.signature
    selected=[PendingSession(n) for n in PendingSession.__dict__ if n.startswith('test_')]
    if '--handover' in sys.argv:selected=[Handover(n) for n in Handover.__dict__ if n.startswith('test_')]
    if '--deadline' in sys.argv:selected=[Deadline(n) for n in Deadline.__dict__ if n.startswith('test_')]
    if '--regression' in sys.argv:selected=baseline.cases()
    if '--motor' in sys.argv:
        selected=[baseline.Tests(n) for n in (
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
