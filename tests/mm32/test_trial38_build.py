"""Faster minute advance retaining released-seconds start staggering."""
import unittest
import test_trial37_build as prior

class Tests(prior.Tests):
    artifact=prior.prior.prior.prior.prior.prior.ref.ROOT/'build/MM32SPIN05PF_FAST_STAGGERED_MINUTES_TRIAL38_20261008.axf'
    signature=0x4d503338
    defines=prior.Tests.defines+['-DFAST_STAGGER_MINUTES']
    minute_start_interval=8

    def test_nominal_fast_burst_finishes_within_half_second(self):
        self.running();self.put(22,704)
        self.setword('seconds_log',248,959);self.setword('seconds_log',251,892)
        self.setword('seconds_log',252,1);self.setword('seconds_log',253,16)
        self.setword('seconds_log',254,960);self.setword('rtc_pace',2,60)
        self.put(5,0);start=self.get(4)
        for _ in range(64):self.tick()
        self.assertEqual(self.get(13),6);self.assertEqual(self.get(22),705)
        self.assertGreater(self.get(12),5);self.assertEqual(self.get(3),0)
        self.assertLessEqual(self.word('minute_end')-start,64)

if __name__=='__main__':unittest.main()
