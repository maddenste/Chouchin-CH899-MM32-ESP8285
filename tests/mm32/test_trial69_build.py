"""Startup correction grace: retain receipt age, deadline only in runtime."""
import unittest
from datetime import datetime,timedelta
import test_trial68_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_STARTUP_CORRECTION_TRIAL69_20261011.axf')
    signature=0x4d503639
    defines=prior.Tests.defines+['-DCORRECTION_STARTUP_GRACE']

    def pending(self,mode=3,delta=1):
        self.mode_run(mode); self.due()
        stamp=self.word('seconds_log',227)
        received=datetime(2000,1,1)+timedelta(seconds=stamp+delta)
        self.feed(('+TIME:'+received.strftime('%a %b %d %H:%M:%S %Y')+f' +0100 10:00{mode}0\r\n').encode())
        self.assertEqual(self.word('daily_log'),7)
        self.assertEqual(self.word('daily_log',6)-self.word('daily_log',7),delta)
        return self.word('daily_log',7)

    def age(self,base,seconds):
        self.setword('seconds_log',227,base+seconds)
        self.call('daily_poll')

    def test_grace_captured_failure_first_runtime_lap(self):
        base=self.pending()
        self.put(2,1); self.age(base,45)
        self.assertEqual(self.word('correction_runtime_started'),0)
        self.put(2,7); self.put(30,0)
        self.setword('seconds_log',248,496)
        self.age(base,71)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('daily_log'),7)
        self.assertEqual(self.word('correction_runtime_stamp'),base+71)

    def test_grace_all_modes_long_acquisition_and_catchup(self):
        for mode in range(4):
            self.setUp(); base=self.pending(mode)
            for stage,age in ((1,71),(4,120),(10,300),(11,310)):
                self.put(2,stage); self.age(base,age)
                self.assertEqual(self.get(3),0)
                self.assertEqual(self.word('correction_runtime_started'),0)
            self.put(2,7); self.put(30,0); self.age(base,311)
            self.age(base,380)
            self.assertEqual(self.get(3),0)
            self.assertEqual(self.word('daily_log',7),base)

    def test_grace_ages_original_time_after_long_homing(self):
        base=self.pending(); self.put(2,1); self.age(base,300)
        self.put(2,7); self.put(30,1)
        self.age(base,315)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('daily_log',8),1)
        sod=(base+316)%86400
        self.assertEqual((self.get(16),self.get(15),self.get(5)),(sod//3600,sod//60%60,sod%60))
        self.assertEqual(self.word('daily_log',7),base)

    def test_grace_normal_runtime_still_times_out_at_71_seconds(self):
        base=self.pending(); self.put(30,0)
        self.age(base,70); self.assertEqual(self.get(3),0)
        self.age(base,71); self.assertEqual((self.get(2),self.get(3)),(6,5))

    def test_grace_offsets_after_homing_advance_without_changing_delta(self):
        for delta in (-30,-5,-1,1,5,30):
            self.setUp(); base=self.pending(delta=delta)
            self.put(2,1); self.age(base,300)
            self.put(2,7); self.put(30,0); self.age(base,310)
            self.put(30,1); self.age(base,330)
            sod=(base+330+delta)%86400
            self.assertEqual(self.get(3),0)
            self.assertEqual((self.get(16),self.get(15),self.get(5)),(sod//3600,sod//60%60,sod%60))
            self.assertEqual(self.word('daily_log',8),1)

if __name__=='__main__': unittest.main()
