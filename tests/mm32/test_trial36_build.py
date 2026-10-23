"""One minute ahead after an authorized backward correction must wait."""
import unittest
import test_trial35_build as prior

class Tests(prior.Tests):
    artifact=prior.prior.prior.prior.ref.ROOT/'build/MM32SPIN05PF_WAIT_AHEAD_TRIAL36_20261008.axf'
    signature=0x4d503336
    defines=prior.Tests.defines+['-DWAIT_AHEAD_MINUTE']

    def test_one_minute_ahead_waits_without_any_motor_pulses(self):
        for hour,minute,position in [(12,26,27),(12,59,60),(23,59,0)]:
            with self.subTest(hour=hour,minute=minute):
                self.setUp();self.wait_state(second=59,position=position)
                self.put(16,hour);self.put(15,minute);self.put(2,10)
                for _ in range(128):self.tick()
                self.assertEqual(self.get(2),11);self.assertEqual(self.get(26),0)
                self.assertEqual(self.get(22),position)
                self.assertEqual(self.get(23),0);self.assertEqual(self.get(13),0)
                self.assertEqual(self.word('minute_active'),0)
                now=(hour*60+minute+1)%1440
                self.put(16,now//60);self.put(15,now%60);self.put(5,0)
                self.setword('rtc_boundary',0,1);self.tick()
                self.assertEqual(self.get(2),7);self.assertEqual(self.get(26),1)
                for _ in range(55):self.tick()
                self.assertEqual(self.get(22),position);self.assertEqual(self.get(13),0)
                self.assertGreater(self.get(12),0);self.assertEqual(self.get(3),0)

    def test_actual_one_second_backward_wifi_update_does_not_wrap_minutes(self):
        self.running();self.put(16,12);self.put(15,27);self.put(5,0);self.put(22,27)
        self.rtc_time(12,27,0);self.setword('rtc_last',0,12*3600+27*60)
        self.bus.data[5]=8;self.bus.data[6]=4
        self.due();self.feed(b'+TIME:Thu Oct  8 12:26:59 2026 +0100 09:00\r\n')
        self.put(30,1);self.call('parallel_poll_once')
        self.assertEqual(self.get(2),10);self.assertEqual(self.get(15),26)
        for elapsed in range(1,64):
            for _ in range(128):
                self.tick()
                self.assertEqual(self.get(3),0)
                self.assertEqual(self.get(23),0)
            sod=12*3600+26*60+59+elapsed
            self.rtc_time(sod//3600,(sod//60)%60,sod%60)
            self.call('parallel_poll_once')
        # First 00 is too soon to calibrate. Hold at27, then at12:28:00
        # move one minute concurrently with seconds, never a 719-minute lap.
        self.assertEqual(self.get(2),7);self.assertEqual(self.get(26),1)
        self.assertEqual(self.get(22),28);self.assertEqual(self.get(13),6)
        self.assertGreater(self.get(12),10)

if __name__=='__main__':unittest.main()
