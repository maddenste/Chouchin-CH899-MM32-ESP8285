"""Compiled AP recovery, error-6 only, based on Trial67."""
import unittest
import test_trial67_build as prior
from unicorn.arm_const import UC_ARM_REG_R0

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_AP_RECOVERY_TRIAL68_20261011.axf')
    signature=0x4d503638
    defines=prior.Tests.defines+['-DAP_RECOVERY']

    def fault6(self):
        self.running(); self.cpu.reg_write(UC_ARM_REG_R0,6); self.call('fail')
        self.assertEqual((self.get(2),self.get(3)),(6,6))

    def recover(self):
        self.pressed=3
        for _ in range(390): self.tick()
        self.call('parallel_poll_once')

    def test_ap_error6_both_buttons_opens_radio_without_movement(self):
        self.fault6(); before=(self.get(12),self.get(13))
        self.recover()
        self.assertEqual(self.word('ap_recovery'),1)
        self.assertTrue(self.output&16)
        self.assertEqual(self.get(28),4)
        self.assertEqual((self.get(12),self.get(13)),before)
        self.assertEqual(self.raw_reg(0x4002101c)&2,0)

    def test_ap_other_faults_never_accept_recovery(self):
        for code in (1,2,3,4,5,7,8,9):
            self.setUp(); self.put(3,code); self.put(2,6)
            self.recover()
            self.assertEqual(self.word('ap_recovery'),0)
            self.assertFalse(self.output&16)

    def test_ap_clean_ack_keeps_power_and_time_requests_reset(self):
        self.fault6(); self.recover()
        self.setword('minute_log',236,self.word('minute_log',236)+1)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('ap_recovery'),2)
        self.assertTrue(self.output&16)
        # Simulate the real parser publishing a valid fresh TIME.
        self.cpu.mem_write(self.symbols['uart_probe_time_event'],(2026).to_bytes(2,'little'))
        self.setword('uart_probe_good_time',0,self.word('uart_probe_good_time')+1)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('ap_recovery'),3)
        self.assertEqual(self.raw_reg(0xe000ed0c),0x05fa0004)

    def test_ap_setup_silence_expires_and_can_retry_after_release(self):
        self.fault6(); self.recover()
        self.setword('minute_log',236,self.word('minute_log',236)+1)
        self.call('parallel_poll_once')
        self.put(4,self.word('ap_recovery',6)+38399); self.call('parallel_poll_once')
        self.assertTrue(self.output&16)
        self.put(4,self.get(4)+1); self.call('parallel_poll_once')
        self.assertEqual(self.word('ap_recovery'),0)
        self.assertFalse(self.output&16); self.assertEqual(self.get(28),6)
        self.pressed=0; self.tick(); self.recover()
        self.assertEqual(self.word('ap_recovery'),1)

    def test_ap_normal_clean_keeps_power_for_five_minute_setup(self):
        self.running(); self.hold(3)
        self.setword('minute_log',236,1); self.call('parallel_poll_once')
        self.assertEqual(self.button(10),0)
        self.assertTrue(self.output&16)
        self.assertEqual(self.word('minute_log',217),1)
        self.assertEqual((self.word('minute_log',218)-self.get(4))&0xffffffff,38400)

    def test_ap_tick_extends_setup_and_bad_time_cannot_restart(self):
        self.fault6(); self.recover()
        self.setword('minute_log',236,self.word('minute_log',236)+1)
        self.call('parallel_poll_once')
        self.put(4,self.word('ap_recovery',6)+38000)
        self.setword('uart_probe_good_tick',0,self.word('uart_probe_good_tick')+1)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('ap_recovery',6),self.get(4))
        self.cpu.mem_write(self.symbols['uart_probe_time_event'],(1999).to_bytes(2,'little'))
        self.setword('uart_probe_good_time',0,self.word('uart_probe_good_time')+1)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('ap_recovery'),2)
        self.assertNotEqual(self.raw_reg(0xe000ed0c),0x05fa0004)

    def test_ap_fault6_single_buttons_and_rec_lockout_stay_safe(self):
        for mask in (1,2):
            self.setUp(); self.fault6(); self.pressed=mask
            for _ in range(500): self.tick()
            self.call('parallel_poll_once'); self.assertEqual(self.word('ap_recovery'),0)
        self.setUp(); self.fault6(); self.setword('minute_log',229,1)
        self.recover(); self.assertEqual(self.word('ap_recovery'),0)

    def test_ap_real_uart_clean_tick_and_time_recovery(self):
        self.fault6(); self.recover()
        self.feed(b'USER_OK\r\n')
        self.assertEqual(self.word('ap_recovery'),1)
        self.feed(b'CLEAN_OK\r\n')
        self.assertEqual(self.word('ap_recovery'),2)
        self.assertTrue(self.output&16)
        self.put(4,self.get(4)+100)
        self.feed(b'+TICK\r\n')
        self.assertEqual(self.word('ap_recovery',6),self.get(4))
        self.feed(b'+TIME:Sun Oct 11 12:30:00 2026 +0100 10:0031\r\n')
        self.assertEqual(self.word('ap_recovery'),3)
        self.assertEqual(self.raw_reg(0xe000ed0c),0x05fa0004)
        self.assertEqual((self.get(2),self.get(3)),(6,6))

    def test_ap_silence_wraparound(self):
        self.fault6(); self.put(4,0xfffff000); self.recover()
        self.feed(b'CLEAN_OK\r\n')
        start=self.word('ap_recovery',6)
        self.put(4,(start+38399)&0xffffffff); self.call('parallel_poll_once')
        self.assertTrue(self.output&16)
        self.put(4,(start+38400)&0xffffffff); self.call('parallel_poll_once')
        self.assertFalse(self.output&16)

    def test_ap_mset_led_and_sixty_second_minimum(self):
        self.running(); self.hold(2)
        time=f'{self.get(16):02}:{self.get(15):02}:{self.get(5):02}'.encode()
        self.feed(b'+TIME:Wed Oct  7 '+time+b' 2026 +0100 09:00\r\n')
        self.assertEqual(self.get(28),4)
        self.assertTrue(self.output&16)
        self.hold(0,7679)
        self.assertTrue(self.output&16)
        self.hold(0,1)
        self.assertFalse(self.output&16)
        self.assertEqual(self.get(28),2)

    def test_ap_fault_clean_transmits_exact_repeated_protocol(self):
        self.fault6()
        self.cpu.mem_write(0x40004408,(1).to_bytes(4,'little'))
        self.writes.clear(); before=(self.get(12),self.get(13))
        self.recover()
        for _ in range(530): self.tick(); self.call('parallel_poll_once')
        self.assertEqual(bytes(v for a,v in self.writes if a==0x40004400),b'CLEAN\n'*3)
        self.assertEqual((self.get(12),self.get(13)),before)

if __name__=='__main__': unittest.main()
