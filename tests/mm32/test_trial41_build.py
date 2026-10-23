"""Compiled Trial41 buttons + complete inherited Trial38 regressions."""
import struct
import unittest
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PRIMASK
import test_reference_scan_build as ref
import test_trial38_build as prior


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_BUTTONS_REBUILD_TRIAL41_20261009.axf'
    signature = 0x4d503431
    defines = prior.Tests.defines + ['-DBUTTON_ACTIONS', '-DBUTTON_REBUILD']

    def setUp(self):
        super().setUp()
        self.pressed = 0
        def inputs(cpu, access, address, size, value, user):
            if address == 0x48000408:
                v = struct.unpack('<I', cpu.mem_read(address, 4))[0]
                cpu.mem_write(address, struct.pack('<I', (v | 0xc00) & ~(self.pressed << 10)))
        self.cpu.hook_add(UC_HOOK_MEM_READ, inputs)
        def reset_bits(cpu, access, address, size, value, user):
            if address == 0x48000414:
                self.output &= ~value  # BRR, alongside inherited BSRR tracking.
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, reset_bits)

    def button(self, i):
        return self.word('minute_log', 220+i)

    def hold(self, mask, ticks=388, poll=True):
        self.pressed = mask
        for _ in range(ticks):
            self.tick()
            self.setword('rtc_edge_tick', 0, self.get(4))
            # Gesture tests inject the RTC edge themselves. Avoid redundant
            # bit-banged RTC polls; RTC servicing is tested separately below.
            self.setword('rtc_poll_tick', 0, self.get(4))
            if poll and (_ == ticks-1 or self.button(10)):
                self.call('parallel_poll_once')

    def test_button_clean_still_services_real_rtc_edges(self):
        self.running(); self.hold(3)
        edges = self.word('rtc_pace', 2)
        self.rtc_time(23, 45, 24)
        self.setword('rtc_poll_tick', 0, (self.get(4)-2) & 0xffffffff)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace', 2), edges+1)
        self.assertEqual(self.get(5), 24)
        self.assertEqual(self.button(10), 1)
        self.assertEqual(self.get(3), 0)

    def test_button_mset_works_before_startup_homing_completes(self):
        self.put(1, 1); self.tick()
        self.hold(2)
        self.assertEqual(self.button(17), 1)
        self.assertEqual(self.get(2), 1)
        self.assertTrue(self.output & 16)
        self.assertEqual(self.get(3), 0)

    def test_button_manual_sync_during_valid_time_homing(self):
        self.running(); self.put(2, 1); self.put(7, 0); self.put(8, 0)
        self.hold(2)
        self.assertEqual(self.button(17), 1)
        self.assertEqual(self.word('daily_log'), 2)
        self.assertEqual(self.get(2), 1)
        self.assertTrue(self.output & 16)

    def test_button_rec_finishes_runtime_burst_then_homes(self):
        self.running(); self.hold(1, 387)
        self.setword('request_pulses', 0, 3)
        self.setword('minute_active', 0, 1)
        self.setword('minute_end', 0, self.get(4)+4)
        self.setword('minute_due', 0, self.get(4)+8)
        self.hold(1, 1)
        self.assertEqual(self.button(9), 1)
        self.assertEqual(self.get(2), 7)
        before = self.get(13)
        self.hold(3, 40)
        self.assertEqual(self.get(13)-before, 3)
        self.assertEqual(self.get(2), 1)
        self.assertEqual(self.button(19), 0)
        self.assertFalse(self.output & 16)

    def test_button_rec_can_park_without_time_and_locks_everything(self):
        self.put(1, 1); self.tick(); self.hold(1)
        for _ in range(40000):
            high = 0
            if self.get(19) == 1:
                high = int(246 <= self.word('seconds_log', 5)+1 <= 262)
            elif self.get(19) == 2:
                high = int(self.word('minute_log', 5)+1 >= 13)
            self.tick(high)
            self.call('parallel_poll_once')
            if self.get(2) in (6, 12): break
        self.assertEqual((self.get(2), self.get(3)), (12, 0))
        self.released()
        self.hold(0, 4); self.hold(2); self.hold(3)
        self.assertEqual(self.get(2), 12)
        self.assertEqual(self.button(17)+self.button(19), 0)
        self.assertFalse(self.output & 16)

    def test_button_release_threshold_does_not_fire(self):
        self.running(); self.hold(2, 387); self.hold(0, 4)
        self.assertEqual(self.button(17), 0)

    def test_button_clean_exact_protocol_and_ack_while_motors_run(self):
        self.running(); self.hold(3)
        self.assertEqual(self.button(19), 1)
        self.assertEqual(self.get(2), 7)
        self.writes.clear()
        self.cpu.mem_write(0x40004408, struct.pack('<I', 1))
        self.hold(3, 530)
        sent = bytes(v for a, v in self.writes if a == 0x40004400)
        self.assertEqual(sent, b'CLEAN\nCLEAN\n')
        self.feed(b'CLEAN_OK\r\n')
        self.assertEqual(self.button(10), 0)
        self.assertEqual(self.button(15), 1)
        self.assertEqual(self.get(28), 2)
        self.assertEqual(self.get(2), 7)

    def test_button_clean_during_startup_resumes_user_acquisition(self):
        self.put(1, 1); self.tick(); self.hold(3)
        self.feed(b'+TIME:Thu Oct  8 12:26:59 2026 +0100 09:00\r\n')
        self.assertEqual(self.get(6), 0)
        self.feed(b'CLEAN_OK\r\n')
        self.assertEqual(self.button(15), 1)
        self.assertEqual(self.word('uart_probe_good_time'), 0)
        self.assertTrue(self.output & 16)
        self.assertEqual(self.get(2), 1)

    def test_button_clean_timeout_keeps_movement_running(self):
        self.running(); self.hold(3)
        self.setword('minute_log', 231, (self.get(4)-15360) & 0xffffffff)
        self.call('parallel_poll_once')
        self.assertEqual(self.button(15), 2)
        self.assertEqual((self.get(2), self.get(3)), (7, 0))

    def test_button_existing_daily_session_is_not_restarted(self):
        self.running(); self.due()
        start = self.word('daily_log', 4)
        self.hold(2)
        self.assertEqual(self.word('daily_log', 4), start)
        self.assertEqual(self.word('daily_log', 1), 1)

    def test_button_combined_before_threshold_and_no_repeat(self):
        self.running(); self.hold(2, 100); self.hold(3)
        self.assertEqual(self.button(17)+self.button(18), 0)
        self.assertEqual(self.button(19), 1)
        self.hold(3, 400)
        self.assertEqual(self.button(19), 1)

    def test_button_partial_release_cannot_become_rec(self):
        self.running(); self.hold(3, 200); self.hold(1, 450)
        self.assertEqual(self.button(18)+self.button(19), 0)

    def test_button_manual_user_exact_legacy_record(self):
        self.running(); self.hold(2)
        self.assertEqual(self.word('daily_log'), 2)
        self.writes.clear()
        self.put(4, self.get(4)+256)
        self.setword('rtc_edge_tick', 0, self.get(4))
        self.setword('rtc_poll_tick', 0, self.get(4))
        self.cpu.mem_write(0x40004408, struct.pack('<I', 1))
        for _ in range(5): self.call('parallel_poll_once')
        self.assertEqual(bytes(v for a, v in self.writes if a == 0x40004400), b'USER\n')
        self.assertEqual(self.word('daily_log', 1), 0)

    def test_button_mset_during_clean_cannot_queue_surprise_wake(self):
        self.running(); self.hold(3); self.hold(0, 4); self.hold(2)
        self.assertEqual(self.button(7), 0)
        self.feed(b'CLEAN_OK\r\n')
        self.call('parallel_poll_once')
        self.assertEqual(self.button(17), 0)
        self.assertFalse(self.output & 16)

    def test_button_rec_supersedes_clean_and_keeps_inputs_floating(self):
        self.running(); self.hold(3); self.hold(0, 4); self.hold(1)
        self.hold(1, 16)
        self.assertEqual(self.button(10), 0)
        self.assertEqual(self.button(9), 1)
        self.assertFalse(self.output & 16)
        crh = struct.unpack('<I', self.cpu.mem_read(0x48000404, 4))[0]
        self.assertEqual(crh & 0xff00, 0x4400)

    def test_button_reset_rearms_after_rec(self):
        self.running(); self.hold(1); self.hold(1, 16)
        self.assertEqual(self.button(9), 1)
        self.setUp(); self.put(1, 1); self.tick(); self.hold(2)
        self.assertEqual(self.button(9), 0)
        self.assertEqual(self.button(17), 1)

    def test_button_rec_lock_prevents_late_radio_enable_and_preserves_irq_mask(self):
        self.running(); self.setword('minute_log', 229, 1)
        for mask in (0, 1):
            self.cpu.reg_write(UC_ARM_REG_PRIMASK, mask)
            self.writes.clear()
            self.call('radio_on')
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK), mask)
            self.assertFalse(any(0x40004400 <= a < 0x40004440 for a, _ in self.writes))
            self.assertFalse(any(a == 0x48000410 and v & 16 for a, v in self.writes))
        self.cpu.reg_write(UC_ARM_REG_PRIMASK, 0)

    def test_button_mset_does_not_change_motor_trace(self):
        traces = []
        for mask in (0, 2):
            self.setUp(); self.running()
            self.put(22, 704)
            self.setword('seconds_log', 248, 959)
            self.setword('seconds_log', 251, 892)
            self.setword('seconds_log', 252, 1)
            self.setword('seconds_log', 253, 16)
            self.setword('seconds_log', 254, 960)
            self.setword('rtc_pace', 2, 60); self.put(5, 0)
            self.setword('minute_log', 223, mask)
            self.setword('minute_log', 221, mask)
            self.setword('minute_log', 222, 4)
            self.setword('minute_log', 224, mask)
            self.setword('minute_log', 225, (self.get(4)-383) & 0xffffffff)
            trace = []
            self.pressed = mask
            for _ in range(128):
                self.tick(); self.setword('rtc_edge_tick', 0, self.get(4))
                self.call('parallel_poll_once')
                trace.append((self.word('second_active'), self.word('minute_active'),
                              self.get(12), self.get(13), self.get(22)))
            traces.append(trace)
        self.assertEqual(traces[0], traces[1])


if __name__ == '__main__': unittest.main()
