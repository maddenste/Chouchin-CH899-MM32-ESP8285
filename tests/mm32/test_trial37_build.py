"""Stagger runtime minute switching without altering second-hand cadence."""
import unittest
import test_trial36_build as prior

class Tests(prior.Tests):
    artifact=prior.prior.prior.prior.prior.ref.ROOT/'build/MM32SPIN05PF_STAGGERED_MINUTES_TRIAL37_20261008.axf'
    signature=0x4d503337
    defines=prior.Tests.defines+['-DSTAGGER_MINUTES']
    minute_settle_ticks=120
    minute_gate_ticks=120
    minute_start_interval=16

    def test_minute_pulses_staggered_with_uninterrupted_seconds(self):
        self.running();self.put(22,704)
        self.setword('seconds_log',248,959);self.setword('seconds_log',251,892)
        self.setword('seconds_log',252,1);self.setword('seconds_log',253,16)
        self.setword('seconds_log',254,960);self.setword('rtc_pace',2,60)
        self.put(5,0)
        last_s=last_m=False;ss=[];ms=[];mw=[];sw=[];previous_end=None
        for _ in range(150):
            self.tick()
            tick=self.get(4);s=bool(self.word('second_active'));m=bool(self.word('minute_active'))
            if last_s and not s:
                sw.append(tick-ss[-1]);previous_end=tick
            if s and not last_s:
                ss.append(tick)
                self.assertFalse(m and not last_m,'simultaneous motor starts')
            if m and not last_m:
                ms.append(tick)
                self.assertFalse(s,'minute starts during seconds drive')
                self.assertIsNotNone(previous_end)
                self.assertLess(tick-previous_end,3)
            if last_m and not m:mw.append(tick-ms[-1])
            last_s,last_m=s,m
        self.assertEqual(len(ms),6);self.assertEqual(mw,[4]*6)
        self.assertTrue(all(b-a>=self.minute_start_interval for a,b in zip(ms,ms[1:])))
        self.assertTrue(all(w==6 for w in sw))
        self.assertTrue(all(b-a in (7,8,9) for a,b in zip(ss,ss[1:])))
        self.assertEqual(self.get(13),6);self.assertEqual(self.get(22),705)
        self.assertEqual(self.get(3),0)

if __name__=='__main__':unittest.main()
