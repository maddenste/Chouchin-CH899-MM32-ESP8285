"""Minute catch-up to current time and atomic calibrated 00 restart."""
import unittest
import test_trial34_build as prior

class Tests(prior.Tests):
    artifact=prior.prior.prior.ref.ROOT/'build/MM32SPIN05PF_SYNC_RESTART_TRIAL35_20261008.axf'
    signature=0x4d503335
    defines=prior.Tests.defines+['-DSYNC_RELEASE']

    def wait_state(self,second=54,position=4,calibrated=1):
        self.running();self.put(26,0);self.put(2,11)
        self.put(16,12);self.put(15,4);self.put(5,second);self.put(22,position)
        self.setword('daily_log',13,3);self.setword('rtc_pace',4,calibrated)
        self.setword('rtc_boundary',0,0)
        self.setword('minute_active',0,0);self.setword('catchup_pulses',0,0)

    def test_capture_wait_at_120454_releases_at_120500(self):
        self.wait_state()
        for _ in range(8):self.tick()
        self.assertEqual(self.get(2),11);self.assertEqual(self.get(26),0)
        self.assertEqual(self.get(22),4);self.assertEqual(self.get(13),0)
        self.put(15,5);self.put(5,0);self.setword('rtc_boundary',0,1)
        self.tick()
        self.assertEqual(self.get(2),7);self.assertEqual(self.get(26),1)
        self.assertEqual(self.word('daily_log',13),0)
        for _ in range(self.minute_settle_ticks):self.tick()
        self.assertEqual(self.get(22),5);self.assertEqual(self.get(13),6)
        self.assertGreater(self.get(12),0);self.assertEqual(self.get(3),0)

    def test_no_next_minute_advance_while_waiting(self):
        self.wait_state(second=23,position=4)
        self.put(2,10);self.tick()
        self.assertEqual(self.get(24),4);self.assertEqual(self.get(2),11)
        for _ in range(100):self.tick()
        self.assertEqual(self.get(22),4)
        self.assertEqual(self.get(23),0);self.assertEqual(self.get(26),0)

    def test_unready_calibration_cannot_enter_run_at_00(self):
        self.wait_state(second=0,position=4,calibrated=0)
        self.setword('rtc_boundary',0,1);self.tick()
        self.assertEqual(self.get(2),11);self.assertEqual(self.get(26),0)
        self.setword('rtc_pace',4,1)
        self.put(15,5);self.put(5,0);self.setword('rtc_boundary',0,1);self.tick()
        self.assertEqual(self.get(2),7);self.assertEqual(self.get(26),1)

    def test_seconds_cannot_start_while_minute_catchup_incomplete(self):
        self.wait_state(second=0,position=2)
        self.put(2,10);self.setword('rtc_boundary',0,1)
        self.tick()
        self.assertEqual(self.get(26),0);self.assertEqual(self.get(2),10)
        for _ in range(110):self.tick()
        self.assertEqual(self.get(22),4);self.assertEqual(self.get(2),11)
        self.assertEqual(self.get(26),0);self.assertEqual(self.get(23),12)

    def test_real_wifi_correction_catches_minutes_and_resumes_motion(self):
        self.running();self.due()
        self.feed(b'+TIME:Wed Oct  7 23:46:23 2026 +0100 09:00\r\n')
        self.put(30,1);self.call('parallel_poll_once')
        self.assertEqual(self.get(26),0);self.assertEqual(self.get(2),10)
        self.assertEqual(self.word('daily_log',8),1)
        for elapsed in range(1,41):
            for _ in range(128):
                p=self.word('seconds_log',248)+1
                self.tick(int(891<=p<=906))
                self.assertEqual(self.get(3),0)
                if elapsed<37:self.assertEqual(self.get(26),0)
            sod=23*3600+46*60+23+elapsed
            self.rtc_time(sod//3600,(sod//60)%60,sod%60)
            self.call('parallel_poll_once')
        self.assertEqual(self.get(2),7);self.assertEqual(self.get(26),1)
        self.assertEqual(self.word('daily_log',13),0)
        self.assertEqual(self.get(22),707)
        self.assertEqual(self.get(23),6);self.assertEqual(self.get(13),6)
        self.assertGreater(self.get(12),30)

if __name__=='__main__':unittest.main()
