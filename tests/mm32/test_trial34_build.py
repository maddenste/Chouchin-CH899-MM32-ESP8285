"""Full bounded RTC recovery, using wired-AND SDA START/STOP detection."""
import unittest
import test_trial33_build as prior

class Tests(prior.Tests):
    artifact=prior.prior.ref.ROOT/'build/MM32SPIN05PF_RTC_BUS_RECOVERY_TRIAL34_20261008.axf'
    signature=0x4d503334
    defines=prior.Tests.defines+['-DRTC_FULL_RECOVERY']

    def interrupted(self,byte,bits,high=False):
        self.setUp();self.put(1,1);self.tick()
        self.bus.mode='tx';self.bus.bits=bits;self.bus.index=0
        # Vary an alarm byte, not Control_status_1: 0xaa/0xff there would
        # deliberately trip the stopped/test-mode safeguard after recovery.
        self.bus.pointer=9
        self.bus.data[9]=byte;self.bus.snapshot=self.bus.data[:]
        self.bus.slave=(byte>>(7-bits))&1
        if high:self.bus.odr|=256
        else:self.bus.odr&=~256
        self.feed(b'+TIME:Thu Oct  8 11:44:46 2026 +0100 09:00\r\n')
        self.assertEqual((self.get(3),self.get(6)),(0,1),(byte,bits,high))
        self.assertEqual(self.word('rtc_recovery',1),9)
        self.assertEqual(self.word('rtc_recovery',2),1)
        self.assertEqual(self.word('rtc_recovery',3),768)
        self.assertEqual(len(self.bus.calendar_writes),7)
        self.assertTrue(all(2<=r<=8 for r,b in self.bus.calendar_writes))
        self.assertEqual(self.bus.crh&255,0x44)

    def test_interrupted_read_alternating_bits_at_every_bit_and_clock_level(self):
        for byte in [0x00,0x08,0x10,0x55,0xaa,0xff]:
            for bits in range(8):
                for high in [False,True]:
                    with self.subTest(byte=byte,bits=bits,high=high):
                        self.interrupted(byte,bits,high)

    def test_slave_low_cannot_see_a_false_stop(self):
        b=self.bus;b.mode='tx';b.bits=3;b.slave=0;b.odr=256
        b.crh=(b.crh&~255)|0x66
        stops=b.stops
        b.write(0x48000410,512)
        self.assertEqual(b.stops,stops)
        self.assertEqual(b.mode,'tx');self.assertEqual(b.slave,0)
        starts=b.starts
        b.write(0x48000410,512<<16)
        self.assertEqual(b.starts,starts)
        self.assertEqual(b.mode,'tx');self.assertEqual(b.slave,0)

if __name__=='__main__':unittest.main()
