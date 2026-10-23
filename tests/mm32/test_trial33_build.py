"""Compiled startup bus recovery and gently disciplined seconds cadence."""
import struct
import unittest
from collections import Counter
import test_trial32_build as prior
from unicorn import UC_HOOK_MEM_WRITE

class Tests(prior.Tests):
    artifact=prior.ref.ROOT/'build/MM32SPIN05PF_SMOOTH_RTC_RECOVERY_TRIAL33_20261008.axf'
    signature=0x4d503333
    defines=prior.Tests.defines+['-DSMOOTH_SECONDS','-DRTC_STARTUP_RECOVERY']
    test_phase_debt_gets_complete_pulses_not_skipped_frames=None
    test_five_second_physical_lag_recovers_and_minutes_wait_for_12=None

    def test_startup_bus_recovers_interrupted_read_without_control_writes(self):
        self.put(1,1);self.tick();self.bus.force_busy=True
        def release(uc,access,a,size,v,user):
            if self.bus.clocks>=3:self.bus.force_busy=False
        hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,release)
        self.feed(b'+TIME:Thu Oct  8 10:56:56 2026 +0100 09:00\r\n')
        self.cpu.hook_del(hook)
        self.assertEqual(self.get(3),0);self.assertEqual(self.get(6),1)
        self.assertGreater(self.word('rtc_recovery',1),0)
        self.assertLessEqual(self.word('rtc_recovery',1),9)
        self.assertEqual(self.word('rtc_recovery',2),1)
        self.assertTrue(all(2<=r<=8 for r,b in self.bus.calendar_writes))
        self.assertEqual(self.bus.crh&255,0x44)

    def test_stuck_sda_stops_without_calendar_write(self):
        self.put(1,1);self.tick();self.bus.force_busy=True
        self.feed(b'+TIME:Thu Oct  8 10:56:56 2026 +0100 09:00\r\n')
        self.assertEqual((self.get(2),self.get(3)),(6,8))
        self.assertEqual(self.word('rtc_recovery',1),9)
        self.assertEqual(self.word('wifi_rtc',5),3)
        self.assertFalse(self.bus.calendar_writes);self.released()

    def test_rtc_left_transmitting_after_mcu_reset_finishes_read(self):
        self.put(1,1);self.tick()
        # RTC remains powered, stopped midway through transmitting a zero bit.
        self.bus.mode='tx';self.bus.bits=3;self.bus.index=0
        self.bus.snapshot=self.bus.data[:];self.bus.slave=0
        self.feed(b'+TIME:Thu Oct  8 10:56:56 2026 +0100 09:00\r\n')
        self.assertEqual(self.get(3),0);self.assertEqual(self.get(6),1)
        self.assertGreater(self.word('rtc_recovery',1),0)
        self.assertLessEqual(self.word('rtc_recovery',1),9)
        self.assertTrue(all(2<=r<=8 for r,b in self.bus.calendar_writes))

    def test_five_second_physical_lag_still_gates_minutes(self):
        self.running();self.put(5,55);self.put(22,705)
        self.rtc_time(23,45,55)
        self.setword('rtc_last',0,23*3600+45*60+55)
        self.setword('rtc_edge_tick',0,self.get(4))
        self.setword('rtc_pace',2,55);self.setword('seconds_log',248,880)
        self.setword('daily_log',3,self.word('daily_log',3)+86400)
        for elapsed in range(1,76):
            for _ in range(128):
                slip=80 if self.word('seconds_log',255)==0 else 0
                physical=self.word('seconds_log',248)+1-slip
                self.tick(int(891<=physical<=906))
                self.assertEqual(self.get(3),0,(elapsed,physical))
                if self.get(13):self.assertGreaterEqual(self.word('seconds_log',255),1)
            sod=23*3600+45*60+55+elapsed
            self.rtc_time(sod//3600,(sod//60)%60,sod%60)
            self.call('parallel_poll_once')
        self.assertGreaterEqual(self.word('seconds_log',255),2)
        self.assertEqual(self.get(13),12);self.assertEqual(self.get(22),707)
        self.assertEqual(self.get(31),0)

    def test_stuck_scl_is_never_forced_high(self):
        self.put(1,1);self.tick();self.bus.stuck_at=0
        self.feed(b'+TIME:Thu Oct  8 10:56:56 2026 +0100 09:00\r\n')
        self.assertEqual((self.get(2),self.get(3)),(6,8))
        self.assertEqual(self.word('wifi_rtc',5),7)
        self.assertEqual(self.word('rtc_recovery',1),0)
        self.assertFalse(self.bus.calendar_writes);self.released()

    def spacing(self,pattern=(128,),debt=0):
        self.running();self.put(22,705)
        self.rtc_time(23,45,10);self.put(5,10)
        self.setword('rtc_last',0,23*3600+45*60+10)
        self.setword('rtc_pace',2,10);self.setword('seconds_log',248,160-debt)
        self.setword('daily_log',3,self.word('daily_log',3)+86400)
        self.setword('rtc_edge_tick',0,self.get(4))
        starts=[];last=False
        for second in range(1,11):
            for _ in range(pattern[(second-1)%len(pattern)]):
                self.tick();active=bool(self.word('second_active'))
                if active and not last:starts.append(self.get(4))
                last=active
                self.assertEqual(self.get(3),0)
            self.rtc_time(23,45,10+second);self.call('parallel_poll_once')
        return Counter(b-a for a,b in zip(starts,starts[1:]))

    def test_nominal_edges_have_uniform_eight_tick_spacing(self):
        self.assertEqual(set(self.spacing()),{8})

    def test_poll_jitter_does_not_gate_individual_pulses(self):
        self.assertEqual(set(self.spacing((126,130))),{8})

    def test_five_second_debt_is_slewed_not_burst(self):
        spacing=self.spacing(debt=80)
        self.assertEqual(set(spacing),{7,8})
        self.assertGreaterEqual(spacing[8],7*spacing[7]-8)

if __name__=='__main__':unittest.main()
