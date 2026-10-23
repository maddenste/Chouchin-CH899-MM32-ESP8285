"""Three consecutive RTC rejects, using the compiled I2C reader."""
import unittest
import test_trial65_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_RTC_THREE_BAD_TRIAL66_20261010.axf')
    signature=0x4d503636
    defines=prior.Tests.defines+['-DRTC_THREE_BAD']

    def sample(self,h,m,s):
        for _ in range(4): self.tick()
        self.rtc_time(h,m,s); self.call('parallel_poll_once')

    def test_window_calendar_jump_is_rejected(self):
        self.window_seed()
        for count in range(1,4):
            self.sample(11,46,0)
            self.assertEqual(self.word('rtc_pace',9),count)
            self.assertEqual(self.get(3),9 if count==3 else 0)

    def test_window_frozen_rtc_is_bounded(self):
        self.window_seed()
        for count in range(1,4):
            for _ in range(194): self.tick()
            self.call('parallel_poll_once')
            self.assertEqual(self.word('rtc_pace',9),count)
            self.assertEqual(self.get(3),9 if count==3 else 0)
            if count==1:
                self.sample(11,45,0) # duplicates must not erase timeout streak
                self.assertEqual(self.word('rtc_pace',9),count)

    def test_reject_exact_live_rollover_then_recover(self):
        self.window_seed()
        base=self.word('seconds_log',227)//86400*86400
        self.setword('seconds_log',227,base+20*3600+12*60+59)
        self.setword('rtc_last',0,20*3600+12*60+59)
        for _ in range(128): self.tick()
        reload=self.word('rtc_pace',1)
        self.sample(20,13,59)
        self.assertEqual((self.get(3),self.word('rtc_pace',9)),(0,1))
        self.assertEqual(self.word('rtc_last',0),20*3600+12*60+59)
        self.assertEqual(self.word('rtc_pace',1),reload)
        self.sample(20,13,0)
        self.assertEqual((self.get(3),self.word('rtc_pace',9)),(0,0))
        self.assertEqual(self.word('seconds_log',223),2)

    def test_reject_two_then_good_resets_streak(self):
        self.window_seed()
        for _ in range(2): self.sample(11,46,0)
        self.sample(11,45,0)
        self.assertEqual(self.word('rtc_pace',9),0)
        for count in range(1,3):
            self.sample(11,46,0)
            self.assertEqual((self.get(3),self.word('rtc_pace',9)),(0,count))

    def test_reject_three_bus_failures(self):
        self.window_seed(); self.bus.ack=False
        for count in range(1,4):
            self.sample(11,45,0)
            self.assertEqual(self.word('rtc_pace',9),count)
            self.assertEqual(self.get(3),8 if count==3 else 0)

    def test_reject_mixed_faults_are_consecutive(self):
        self.window_seed(); self.sample(11,46,0)
        self.bus.ack=False; self.sample(11,45,0)
        self.bus.ack=True; self.sample(11,46,0)
        self.assertEqual((self.get(3),self.word('rtc_pace',9)),(9,3))

    def test_reject_frozen_then_valid_edge_recovers(self):
        self.window_seed()
        for _ in range(194): self.tick()
        self.call('parallel_poll_once')
        self.sample(11,45,1) # re-establish baseline after expired window
        self.sample(11,45,2)
        self.assertEqual((self.get(3),self.word('rtc_pace',9)),(0,0))

    def test_reject_invalid_calendar_three_times(self):
        self.window_seed(); self.bus.data[5]=0
        for count in range(1,4):
            self.sample(11,45,0)
            self.assertEqual(self.word('rtc_pace',9),count)
            self.assertEqual(self.get(3),8 if count==3 else 0)

    def test_reject_counter_survives_button_systick_updates(self):
        self.window_seed(); self.sample(11,46,0)
        for _ in range(16): self.tick()
        self.assertEqual(self.word('rtc_pace',9),1)
        self.assertEqual(self.word('rtc_pace',10),1)
        self.assertEqual(self.word('minute_log',220),0) # raw buttons

if __name__=='__main__': unittest.main()
