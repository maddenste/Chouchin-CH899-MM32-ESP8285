"""Compiled passive reference audit; sensor mux and exact motor-edge regression."""
import struct
import unittest
from unicorn import UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1
import test_trial52_build as prior


class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_REFERENCE_AUDIT_TRIAL53_20261009.axf')
    signature=0x4d503533
    defines=prior.Tests.defines+['-DREFERENCE_AUDIT']

    def setUp(self):
        super().setUp()
        self.sensor_model=False
        self.minute_input=0
        self.seconds_input=0
        def read(cpu,access,address,size,value,user):
            if not self.sensor_model:return
            selected=self.output & ((1<<13)|(1<<15))
            high=self.minute_input if selected==1<<15 else self.seconds_input if selected==1<<13 else 0
            raw=struct.unpack('<I',cpu.mem_read(address,4))[0]
            cpu.mem_write(address,struct.pack('<I',(raw & ~(1<<14))|(high<<14)))
        self.cpu.hook_add(UC_HOOK_MEM_READ,read,begin=0x48000408,end=0x48000408)

    def tick(self,high=0):
        self.seconds_input=high
        super().tick(high)

    def call(self,name,*args):
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),args):
            self.cpu.reg_write(register,value)
        super().call(name)

    def mode_run(self,mode):
        super().mode_run(mode)
        # running() shortcuts homing; model the real runtime sensor ownership.
        self.output=(self.output & ~((1<<13)|(1<<15))) | (1<<13)
        self.setword('minute_log',195,1)

    def night_run(self,mode=0,hour=0,minute=0):
        super().night_run(mode,hour,minute)
        # Prior fixture disables both compare channels mid-first pulse. Real
        # parking drains that pulse before disabling its falling edge.
        self.setword('second_active',0,0)
        self.setword('second_highs',0,0)

    def a(self,index,value=None):
        if value is not None:self.setword('minute_log',160+index,value)
        return self.word('minute_log',160+index)

    def audit_start(self):
        self.put(16,11);self.put(15,30)
        self.call('audit_tick',100,7)
        self.assertEqual((self.a(0),self.a(1)),(1,1))

    def audit_low_markers(self):
        tick=100
        for marker in range(690,702):
            self.put(22,marker)
            self.cpu.mem_write(0x48000408,struct.pack('<I',0))
            for _ in range(3):
                tick+=8;self.call('audit_sample_minute',tick)
        self.assertEqual(self.a(10),12)
        return tick

    def test_audit_phase_and_wrap(self):
        reference=4320-getattr(self,'minute_offset',48)
        cases=[(reference+delta,status) for delta,status in ((-6,2),(0,2),(6,2),(-13,3),(18,3))]
        for coordinate,expected in cases+[(0,3)]:
            with self.subTest(coordinate=coordinate):
                self.setUp();self.audit_start();tick=self.audit_low_markers()
                self.put(22,coordinate//6);self.setword('minute_log',191,coordinate%6)
                self.cpu.mem_write(0x48000408,struct.pack('<I',1<<14))
                for i in range(3):self.call('audit_sample_minute',tick+8*(i+1))
                self.assertEqual(self.a(0),expected)
                self.put(15,6);self.put(16,12);self.call('audit_tick',tick+40,7)
                self.assertEqual(self.a(1),0)
                self.assertEqual(self.a(3 if expected==2 else 4),1)

    def test_audit_missing_insufficient_cancelled(self):
        self.audit_start();self.audit_low_markers()
        self.put(16,12);self.put(15,6);self.call('audit_tick',500,7)
        self.assertEqual((self.a(0),self.a(5)),(4,1))
        self.setUp();self.audit_start()
        self.put(16,12);self.put(15,6);self.call('audit_tick',500,7)
        self.assertEqual((self.a(0),self.a(6)),(5,1))
        self.setUp();self.audit_start();self.call('audit_tick',500,10)
        self.assertEqual((self.a(0),self.word('minute_log',199)),(6,1))
        self.call('audit_tick',501,7);self.assertEqual(self.a(1),0)

    def test_audit_glitch_and_stuck_high_not_pass(self):
        self.audit_start()
        self.cpu.mem_write(0x48000408,struct.pack('<I',1<<14))
        for tick in range(108,300,8):self.call('audit_sample_minute',tick)
        self.assertEqual(self.a(19),0)
        tick=self.audit_low_markers();self.put(22,712)
        self.cpu.mem_write(0x48000408,struct.pack('<I',1<<14));self.call('audit_sample_minute',tick+8)
        self.cpu.mem_write(0x48000408,struct.pack('<I',0));self.call('audit_sample_minute',tick+16)
        self.assertEqual(self.a(19),0)

    def test_audit_all_modes_preserve_edges_and_seconds_references(self):
        for mode in range(4):
            results=[]
            for enabled in (0,1):
                self.setUp();self.sensor_model=True;self.mode_run(mode)
                self.setword('minute_log',195,enabled);self.simulate(121)
                self.assertGreaterEqual(self.word('seconds_log',255),2,(mode,enabled))
                if enabled:self.assertGreater(self.a(7),0)
                motor=[(t,a,v) for t,a,v in self.edges if (a==0x48000010 and v in (128,1<<23)) or (a==0x48000410 and v in (1,2,4,1<<16,2<<16,4<<16))]
                results.append(motor)
            self.assertEqual(results[0],results[1],mode)

    def test_audit_parked_all_modes_minutes_continue(self):
        for mode in range(4):
            self.setUp();self.sensor_model=True;self.night_run(mode)
            self.night_simulate(61)
            self.assertEqual(self.get(22),1)
            self.assertGreater(self.a(7),0)
            self.assertEqual(self.word('minute_log',196),4)

    def test_audit_ram_addresses(self):
        self.assertEqual(self.symbols['minute_log']+160*4,0x20000494)
        self.assertEqual(self.symbols['minute_log']+195*4,0x20000520)

    def test_no_time_has_no_parking_or_daily_fallback(self):
        # Even if the PCF8563 retains an old clock, it is not a fresh ESP seed.
        self.rtc_time(0,0,0);self.tick()
        for _ in range(128):self.tick();self.call('parallel_poll_once')
        self.assertEqual(self.get(6),0)
        self.assertEqual(self.word('daily_log',12),0)
        self.assertEqual(self.word('daily_log',3),0)
        self.assertEqual(self.word('daily_log',1),0)
        self.assertEqual(self.word('minute_log',192),0)
        self.assertEqual(self.word('minute_log',193),0)

    def test_invalid_time_cannot_arm_settings_or_schedule(self):
        self.tick()
        for line in (self.message(b'01').replace(b'Oct  7',b'Feb 30'),
                     self.message(b'01',b'00:00:60'),
                     self.message(b'01').replace(b'09:17',b'24:17'),
                     self.message(b'03')):
            self.feed(line)
        self.assertEqual(self.get(6),0)
        self.assertEqual(self.word('daily_log',12),0)
        self.assertEqual(self.word('daily_log',3),0)
        self.assertEqual(self.word('minute_log',194),0)

    def test_first_time_controls_schedule_and_optional_parking(self):
        for suffix,parking in ((b'',0),(b'01',1),(b'12',2),(b'30',0)):
            self.setUp();self.tick();self.feed(self.message(suffix))
            self.assertEqual(self.get(6),1)
            self.assertEqual(self.word('daily_log',12),1)
            self.assertEqual((self.word('daily_log',10),self.word('daily_log',11)),(9,17))
            self.assertEqual(self.word('minute_log',192),parking)
            self.put(2,7);self.put(7,1);self.put(8,1);self.put(26,1)
            self.call('parallel_poll_once')
            now=self.now_stamp();today=now-now%86400
            self.assertEqual(self.word('daily_log',3),today+86400+9*3600+17*60)

    def test_power_cycle_discards_previous_time_settings(self):
        self.tick();self.feed(self.message(b'32'))
        self.assertEqual(self.word('minute_log',192),2)
        self.assertEqual(self.word('daily_log',12),1)
        self.setUp()
        self.assertEqual(self.get(6),0)
        self.assertEqual(self.word('daily_log',12),0)
        self.assertEqual(self.word('daily_log',3),0)
        self.assertEqual(self.word('minute_log',192),0)


if __name__=='__main__':unittest.main()
