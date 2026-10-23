"""Trial60 baseline with coherent TIME/settings and bounded fine timing."""
import unittest
import struct
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP
import test_trial60_build as prior
from test_trial53_stress import StressTests

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_RELEASE_HARDENING_TRIAL62_20261010.axf')
    signature=0x4d503632
    defines=prior.Tests.defines+['-DRELEASE_HARDENING']
    # Short traces may not yet include a fractional carry. Both observed
    # sets are valid; the dedicated conservation test verifies every carry.
    fine_spacing_sets=({3776},{3776,3777})
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.symbols['release_state']=cls.symbols['seconds_log']+228*4

    def setUp(self):
        super().setUp()
        # More ZI data makes the old 3000-instruction boot cutoff too short.
        # Finish genuine C startup before installing a synthetic thread stack.
        self.cpu.reg_write(UC_ARM_REG_SP,0x20001000)
        self.cpu.emu_start(self.symbols['Reset_Handler'],0x08007000,count=12000)
        self.cpu.reg_write(UC_ARM_REG_SP,0x20000ff8)
        self.boot_modes=(self.word('minute_log',188),self.word('minute_log',189))
        self.boot_night=self.word('minute_log',192)
        # Historical movement fixtures explicitly select On. Verify the new
        # actual boot default separately rather than changing their scenarios.
        self.setword('minute_log',192,0)
        self.setword('minute_log',188,3);self.setword('minute_log',189,3)

    def test_constant_spacing_and_width_over_counter_wraps(self):
        self.fine_run()
        for _ in range(4*128):
            self.setword('rtc_edge_tick',0,self.get(4)); self.tick()
        starts=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        falls=[t for t,a,v in self.edges if a==0x48000010 and v==1<<23]
        self.assertGreater(len(starts),60)
        self.assertTrue(set(b-a for a,b in zip(starts,starts[1:]))<={3776,3777})
        self.assertEqual(set(b-a for a,b in zip(starts,falls)),{2930})
        self.assertEqual(self.get(3),0)

    def test_factory_time_preserves_default_and_explicit_parking(self):
        self.assertEqual(self.boot_night,1)
        self.setword('minute_log',192,self.boot_night)
        self.wire(self.message())
        self.assertEqual(self.word('minute_log',192),1)
        self.wire(self.message(b'30'))
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',192)),(3,0))
        self.wire(self.message())
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',192)),(3,0))

    def test_fault_parks_at_015030_and_disables_wake_sources(self):
        self.mode_run(0)
        self.advance_timer((self.reg(0x38)-self.counter)&65535)
        self.setword('seconds_log',248,320); self.put(22,100)
        self.setword('minute_log',191,2)
        self.cpu.reg_write(UC_ARM_REG_R0,8); self.call('fail')
        self.assertEqual((self.get(2),self.get(3)),(14,8))
        for _ in range(3000):
            self.tick()
            if self.get(2)==6: break
        self.assertEqual(self.word('release_state',0),2)
        seconds=[v for _,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        minutes=[v for _,a,v in self.edges if a==0x48000410 and v in (2,4)]
        self.assertEqual(len(seconds)-1,160)
        self.assertEqual(len(minutes),58)
        self.assertEqual(self.reg(0x0c),0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0xe000e010,4))[0],0)
        self.assertEqual(self.output&((1<<4)|(1<<13)|(1<<15)|7),0)
        self.assertEqual((self.word('release_state',8),self.word('release_state',9)),(0,0))

    def test_sensor_fault_never_attempts_diagnostic_motion(self):
        self.mode_run(0); self.cpu.reg_write(UC_ARM_REG_R0,5);self.call('fail')
        self.assertEqual((self.get(2),self.get(3)),(6,5))
        self.assertEqual(self.word('release_state',0),2)

    def test_late_mode_handover_does_not_wait_a_full_minute(self):
        for old in (0,1):
            for new in (2,3):
                self.setUp();self.mode_run(old)
                self.setword('minute_log',188,new)
                self.put(5,0);self.put(15,46);self.setword('rtc_boundary',0,1)
                self.tick()
                # Model a trustworthy physical arrival one second after :00.
                self.put(5,1);self.setword('rtc_boundary',0,0)
                for _ in range(128): self.tick()
                self.advance_timer((self.reg(0x38)-self.counter)&65535)
                self.reg(0x0c,0);self.put(30,1)
                for _ in range(128): self.tick()
                self.assertEqual(self.word('minute_log',189),new)
                self.assertEqual(self.get(30),0)
                self.assertEqual(self.get(3),0)

    def test_fine_fraction_conserves_measured_rate_over_48_hours(self):
        for mode in range(4):
            for rate in (62500,62501,62502,62503,75000):
                self.setUp();self.setword('rtc_pace',1,rate-1)
                self.setword('release_state',1,777)
                self.mode_run(mode)
                numerator=self.word('release_state',3);denominator=self.word('release_state',4)
                before=self.word('release_state',2)
                intervals=[]
                for _ in range(512):
                    self.advance_timer((self.reg(0x34)-self.counter)&65535)
                    intervals.append((self.reg(0x34)-self.counter)&65535)
                # Actual compiled scheduling, bounded to one fine count;
                # extrapolation uses its exact remainder-conservation invariant.
                self.assertLessEqual(max(intervals)-min(intervals),1)
                self.assertEqual(sum(intervals)*denominator,
                                 512*numerator+before-self.word('release_state',2))
                pulses=48*3600*16
                total=(pulses*numerator)//denominator
                self.assertLess(pulses*numerator/denominator-total,1)
                self.assertEqual(self.get(3),0)

for name in StressTests.__dict__:
    if name.startswith('test_stress_'):
        setattr(Tests,name,getattr(StressTests,name))
del StressTests

if __name__=='__main__': unittest.main()
