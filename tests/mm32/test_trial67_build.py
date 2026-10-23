"""Latched fault-only red+blue code display."""
import unittest
import struct
from unicorn.arm_const import UC_ARM_REG_R0
import test_trial66_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_FAULT_LED_CODES_TRIAL67_20261010.axf')
    signature=0x4d503637
    defines=prior.Tests.defines+['-DFAULT_LED_CODES']

    def raw_reg(self,address):
        return struct.unpack('<I',self.cpu.mem_read(address,4))[0]

    def led_on(self):
        red=not bool(self.a_output&(1<<15))
        blue=not bool(self.bus.odr&(1<<3))
        self.assertEqual(red,blue)
        return red

    def test_fault_led_all_codes_exact_count_and_ten_second_gap(self):
        for code in range(1,10):
            with self.subTest(code=code):
                self.setUp(); self.put(3,code)
                self.cpu.reg_write(UC_ARM_REG_R0,0); self.call('parallel_leds_fault_start')
                end=(code-1)*64+8; starts=[]; last=False
                for tick in range(end+1281):
                    self.cpu.reg_write(UC_ARM_REG_R0,tick); self.call('parallel_leds_tick')
                    on=self.led_on()
                    if on and not last: starts.append(tick)
                    if end<=tick<end+1280: self.assertFalse(on)
                    last=on
                self.assertEqual(starts,[64*i for i in range(code)]+[end+1280])

    def test_fault_led_shutdown_only_indicator_runs(self):
        self.mode_run(0)
        self.cpu.reg_write(UC_ARM_REG_R0,5); self.call('fail')
        self.assertEqual((self.get(2),self.get(3)),(6,5))
        self.assertEqual(self.raw_reg(0xe000e010)&7,7)
        self.assertEqual(self.raw_reg(0x4002101c)&2,0)
        self.assertEqual(self.word('minute_log',211),0)
        before=(self.get(12),self.get(13),self.word('rtc_pace',5),
                self.word('seconds_log',227),self.word('minute_log',220))
        for _ in range(128): self.tick(); self.call('parallel_poll_once')
        after=(self.get(12),self.get(13),self.word('rtc_pace',5),
               self.word('seconds_log',227),self.word('minute_log',220))
        self.assertEqual(before,after)
        self.assertEqual(self.get(2),6)

    def test_fault_led_tick_wrap(self):
        self.put(3,4)
        start=0xfffffff0
        self.cpu.reg_write(UC_ARM_REG_R0,start); self.call('parallel_leds_fault_start')
        for elapsed in (0,7,8,63,64,71,72,192,199,200,1479,1480):
            self.cpu.reg_write(UC_ARM_REG_R0,(start+elapsed)&0xffffffff)
            self.call('parallel_leds_tick')
            self.assertEqual(self.led_on(),elapsed in (0,7,64,71,192,199,1480))

    def test_fault_parks_at_015030_and_disables_wake_sources(self):
        self.mode_run(0)
        self.advance_timer((self.reg(0x38)-self.counter)&65535)
        self.setword('seconds_log',248,320); self.put(22,100)
        self.cpu.reg_write(UC_ARM_REG_R0,9); self.call('fail')
        self.assertEqual(self.get(2),14)
        for _ in range(40000):
            self.tick()
            if self.get(2)==6: break
        self.assertEqual((self.get(2),self.get(3)),(6,9))
        self.assertEqual((self.word('release_state',8),self.word('release_state',9)),(0,0))
        self.assertEqual(self.get(28),6)
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.raw_reg(0x4002101c)&2,0)

if __name__=='__main__': unittest.main()
