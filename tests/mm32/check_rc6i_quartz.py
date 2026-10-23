"""Focused RC6I native checks. Not the full release suite or physical proof."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.analysis_deps'))
from test_rc6g_normal_engine import Tests as Base
from test_trial28_build import RTC
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R2, UC_ARM_REG_R3

class CounterRTC(RTC):
    """PCF flags are write-zero-to-clear, not ordinary writable RAM."""
    def write(self,address,value):
        before=self.data[1]
        n=len(self.calendar_writes)
        super().write(address,value)
        for reg,b in self.calendar_writes[n:]:
            if reg==1:
                self.data[1]=(b&~12)|(before&b&12)

class Tests(Base):
    artifact=Path(__file__).parent/'release_candidate_rc6i/build/MM32SPIN05PF_QUARTZ_REFERENCE_RC6I_20261021.axf'
    signature=0x4d505272
    def setUp(self):
        super().setUp()
        self.bus=CounterRTC()
    def call(self,name,*args):
        # Historical helper supports only R0/R1. New sampler has three args.
        for register,value in zip((UC_ARM_REG_R2,UC_ARM_REG_R3),args[2:]):
            self.cpu.reg_write(register,value)
        super().call(name,*args[:2])
    def q(self,i,value=None):
        if value is not None:self.setword('pulse_diag',i,value)
        return self.word('pulse_diag',i)
    def result(self,name,*args):
        self.call(name,*args)
        return self.cpu.reg_read(UC_ARM_REG_R0)
    def start_counter(self):
        self.tick()
        self.assertEqual(self.result('rtc_counter_start'),1)
        self.q(1,1)
    def test_counter_driver_preserves_calendar_alarm_clkout_and_pauses(self):
        self.tick(); old=self.bus.data[:]
        self.assertEqual(self.result('rtc_counter_start'),1)
        self.assertEqual(self.bus.data[14:16],[128,255])
        self.assertEqual(self.bus.data[:14],old[:14])
        self.assertEqual({r for r,b in self.bus.calendar_writes},{1,14,15})
        out=0x20000f80
        self.assertEqual(self.result('rtc_counter_read',out),1)
        self.assertEqual(self.bus.crh&255,0x44)
        self.assertEqual(self.result('rtc_counter_pause'),1)
        self.assertEqual(self.bus.data,old)
    def test_foreign_timer_interrupt_is_not_taken_over(self):
        self.tick(); self.bus.data[1]=1
        self.assertEqual(self.result('rtc_counter_start'),0)
        self.assertEqual(self.bus.calendar_writes,[])
        self.assertEqual(self.bus.crh&255,0x44)
    def test_rate_calibration_reload_wrap_and_motor_unchanged(self):
        self.mode_run(3); self.start_counter()
        old=(self.reg(0x34),self.reg(0x38),self.word('second_polarity'),self.word('seconds_log',215))
        clock=0xfff00000
        for i in range(134):
            self.call('quartz_sample',(200-i*64)%255,(clock+i*125000)&0xffffffff,20000)
        self.assertGreaterEqual(self.q(14),1)
        self.assertEqual(self.word('rtc_pace',1),62499)
        self.assertEqual(self.q(16),64000000)
        self.assertEqual(old,(self.reg(0x34),self.reg(0x38),self.word('second_polarity'),self.word('seconds_log',215)))
    def test_clock_rates_and_fractional_precision(self):
        for rate in (50000,62500,63108,75000):
            self.setUp(); self.start_counter()
            self.setword('rtc_pace',1,rate-1)
            for i in range(131):
                self.call('quartz_sample',(240-i*64)%255,i*rate*2,10000)
            self.assertEqual(self.q(16),rate*1024)
            self.assertEqual(self.word('rtc_pace',1),rate-1)
    def test_bad_reads_and_long_gap_fall_back_without_stopping_motor(self):
        self.mode_run(3); self.start_counter()
        before=self.word('rtc_pace',1)
        for _ in range(3):self.call('quartz_sample',100,0,200000)
        self.assertEqual(self.q(1),3)
        self.assertEqual(self.word('rtc_pace',1),before)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.bus.data[14],3)
        self.setUp(); self.start_counter()
        self.call('quartz_sample',100,0,10000)
        self.call('quartz_sample',36,500000,10000)
        self.assertEqual(self.q(12),1)
        self.assertEqual(self.q(11),0)
    def test_calendar_set_pauses_counter_and_reseeds(self):
        self.tick(); self.seed()
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.result('rtc_counter_start'),1);self.q(1,1)
        self.assertEqual(self.result('rtc_motion_set',self.symbols['uart_probe_time_event']),1)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('wifi_rtc',2),2)
        self.assertEqual(self.q(1),0)
        self.assertEqual(self.bus.data[14],3)
        # MCU SRAM reset while the external RTC keeps our timer running.
        self.bus.data[14:16]=[128,70]
        self.bus.data[1]=4
        self.q(20,0);self.q(1,0)
        self.assertEqual(self.result('rtc_motion_set',self.symbols['uart_probe_time_event']),1)
        self.assertEqual(self.bus.data[14],3)
        self.assertEqual(self.bus.data[1]&4,0)
    def test_poll_uses_actual_i2c_counter_and_tim2_without_touching_tim3(self):
        self.mode_run(3)
        self.call('quartz_poll')
        self.assertEqual(self.q(1),1)
        self.assertEqual(self.q(20),1)
        self.assertEqual(self.word_at(0x4000002c),0xffffffff)
        self.q(6,64);self.q(7,8128);self.q(8,0);self.q(9,15875000);self.q(11,1)
        self.bus.data[15]=255
        self.cpu.mem_write(0x40000024,(16000000).to_bytes(4,'little'))
        self.put(4,self.q(10))
        before=bytes(self.cpu.mem_read(0x40000400,0x44))
        self.call('quartz_poll')
        self.assertEqual(self.q(14),1)
        self.assertEqual(self.q(16),64000000)
        self.assertEqual(before,bytes(self.cpu.mem_read(0x40000400,0x44)))
    def word_at(self,address):
        return int.from_bytes(self.cpu.mem_read(address,4),'little')
    def test_shared_grid_four_modes(self):
        for mode in range(4):
            self.setUp();self.mode_run(mode)
            self.setword('request_pulses',0,6)
            self.edges=[];self.advance_timer(16*16000)
            sec=[at for at,a,v in self.edges if (a==0x48000010 and v==128) or (a==0x48000410 and v==1)]
            minutes=[at for at,a,v in self.edges if a==0x48000410 and v in (2,4)]
            sf=[at for at,a,v in self.edges if a==0x48000010 and v==1<<23]
            mf=[at for at,a,v in self.edges if a==0x48000410 and v==6<<16]
            self.assertEqual(len(minutes),6)
            for at in minutes:
                q=at-max(x for x in sec+[0] if x<at)
                self.assertIn(q,(3754,) if mode&2 else (3906,3907))
                self.assertIn(at+2*q,sf);self.assertIn(at+2*q,mf)
            self.assertEqual(self.get(3),0)

if __name__=='__main__':
    names=['test_counter_driver_preserves_calendar_alarm_clkout_and_pauses',
           'test_foreign_timer_interrupt_is_not_taken_over',
           'test_rate_calibration_reload_wrap_and_motor_unchanged',
           'test_clock_rates_and_fractional_precision',
           'test_bad_reads_and_long_gap_fall_back_without_stopping_motor',
           'test_calendar_set_pauses_counter_and_reseeds',
           'test_poll_uses_actual_i2c_counter_and_tim2_without_touching_tim3',
           'test_shared_grid_four_modes']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
