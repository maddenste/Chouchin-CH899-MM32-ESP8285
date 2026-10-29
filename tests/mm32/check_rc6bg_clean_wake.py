"""Compiled RC6BG diagnostic removal and delayed scheduled-wake tests.

Peripheral/reset-register models only. Never connects to a clock.
"""
import sys
import unittest
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP
import check_rc6be_session_sleep as prior

IMAGE = Path(__file__).resolve().parents[2] / 'firmware/mm32/build/MM32SPIN05PF_CLEAN_WAKE_RC6BG_20261029.axf'
MAGIC = 0x52424631
COOKIE = 0xa95c73e1
CSR = 0x40021024


class Diagnostic(prior.SessionSleep):
    artifact = IMAGE
    signature = 0x4d5052a4

    def boot_to_main(self, flags, reason=0, cookie=None, magic=MAGIC):
        # Populate load-memory bytes as well as run-memory bytes for the
        # actual Reset_Handler's C data copy, rather than bypassing startup.
        with self.artifact.open('rb') as f:
            elf = ELFFile(f)
            for segment in elf.iter_segments():
                if segment['p_type'] == 'PT_LOAD' and 0x08000000 <= segment['p_paddr'] < 0x08008000:
                    self.cpu.mem_write(segment['p_paddr'], segment.data())
        self.setword('seconds_log', 80, magic)
        self.setword('seconds_log', 86, reason)
        self.setword('seconds_log', 87, reason ^ COOKIE if cookie is None else cookie)
        state = {'csr': flags, 'writes': []}
        def read(cpu, access, address, size, value, user):
            self.store(CSR, state['csr'])
        def write(cpu, access, address, size, value, user):
            state['writes'].append(value)
            if value & (1 << 24):
                state['csr'] &= 3  # RMVF removes reset flags, not LSI state.
        reads = self.cpu.hook_add(UC_HOOK_MEM_READ, read, begin=CSR, end=CSR + 3)
        writes = self.cpu.hook_add(UC_HOOK_MEM_WRITE, write, begin=CSR, end=CSR + 3)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x20001000)
        self.cpu.emu_start(self.symbols['Reset_Handler'] | 1, self.symbols['main'] & ~1, count=200000)
        self.cpu.hook_del(reads)
        self.cpu.hook_del(writes)
        return [self.word('seconds_log', i) for i in range(80, 88)], state

    def test_real_startup_does_not_access_reset_flags_or_retain_diagnostics(self):
        record, state = self.boot_to_main(0x0c000000, reason=1)
        self.assertEqual(record, [0] * 8)
        self.assertEqual(state['writes'], [])
        self.assertEqual(state['csr'], 0x0c000000)

    def wake_fixture(self, style=3, hour=10, minute=0, second=0):
        self.start_pwm(style)
        self.put(16, hour)
        self.put(15, minute)
        self.put(5, second)
        self.setword('minute_log', 192, 1)
        self.setword('minute_log', 211, 0)
        self.setword('minute_log', 203, 0)
        self.setword('minute_log', 204, 0)
        due = 846496800  # 28 October 2026,10:00.
        for index, value in ((0, 1), (3, due), (10, hour), (11, minute), (12, 1), (13, 0)):
            self.setword('daily_log', index, value)
        self.setword('seconds_log', 227, due)
        return due

    def test_scheduled_wake_waits_three_seconds_all_modes_without_motor_writes(self):
        for style in range(4):
            with self.subTest(style=style):
                self.setUp()
                due = self.wake_fixture(style)
                frozen = self.frozen()
                epoch = self.word('seconds_log', 215)
                writes, hook = self.trace()
                for elapsed in (-1, 0, 1, 2):
                    self.setword('seconds_log', 227, due + elapsed)
                    self.call('daily_poll')
                    self.assertEqual(self.word('minute_log', 211), 0)
                    self.assertEqual(self.word('daily_log', 1), 0)
                    self.assertEqual(self.word('daily_log', 0), 1)
                self.setword('seconds_log', 227, due + 3)
                self.call('daily_poll')
                self.cpu.hook_del(hook)
                self.assertEqual(self.word('minute_log', 211), 1)
                self.assertEqual(self.word('daily_log', 1), 1)
                self.assertEqual(self.word('daily_log', 14), due + 3)
                self.assertEqual([self.word('seconds_log', i) for i in range(80, 88)], [0] * 8)
                self.assertEqual(self.word('seconds_log', 215), epoch)
                self.assertEqual(self.frozen(), frozen)
                self.assertFalse([(a, v) for a, v in writes if
                                  0x40000400 <= a < 0x40000450 or
                                  0x40012c00 <= a < 0x40012c50 or
                                  0x40014000 <= a < 0x40014050 or a == 0xe000ed0c])
                self.assertEqual(self.get(3), 0)

    def test_manual_mset_bypasses_delay_at_due_marker(self):
        due = self.wake_fixture()
        self.setword('minute_log', 227, 1)  # Debounced manual action.
        epoch = self.word('seconds_log', 215)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('minute_log', 211), 1)
        self.assertEqual(self.word('minute_log', 217), 1)
        self.assertEqual(self.word('daily_log', 1), 0)
        self.assertEqual(self.word('daily_log', 14), due)
        self.assertEqual(self.word('seconds_log', 215), epoch)

    def test_late_poll_and_midnight_rollover_do_not_miss_wake(self):
        for delay in (3, 5, 62):
            for due in (846496800, 846547140):  #10:00 and23:59, including00:00:02.
                with self.subTest(delay=delay, due=due):
                    self.setUp()
                    self.wake_fixture()
                    self.setword('daily_log', 3, due)
                    self.setword('seconds_log', 227, due + delay)
                    self.call('daily_poll')
                    self.assertEqual(self.word('minute_log', 211), 1)
                    self.assertEqual(self.word('daily_log', 1), 1)
                    self.assertEqual(self.word('daily_log', 14), due + delay)

    def test_alignment_request_is_not_promoted_until_delayed_wake(self):
        due = self.wake_fixture()
        self.setword('minute_log', 203, 1)
        self.call('daily_poll')
        self.assertEqual(self.word('minute_log', 204), 0)
        self.setword('seconds_log', 227, due + 3)
        self.call('daily_poll')
        self.assertEqual(self.word('minute_log', 204), 1)
        self.assertEqual(self.word('minute_log', 211), 1)

    def test_rehome_clears_former_diagnostic_area(self):
        for recovery in (False, True):
            self.setUp()
            self.start_pwm()
            self.fixture_clock()
            record = [MAGIC, 0x0c000000, 0, 0, 846496800, 846496803, 0, 0]
            for i, value in enumerate(record):
                self.setword('seconds_log', 80 + i, value)
            self.setword('seconds_log', 79, 0x1234)
            self.setword('seconds_log', 88, 0x5678)
            self.advance_timer(10000)
            if recovery:
                self.setword('minute_log', 204, 1)
                self.setword('daily_log', 0, 1)
                self.setword('daily_log', 13, 0)
            else:
                self.setword('minute_log', 227, 2)
                self.setword('minute_log', 229, 1)
            for _ in range(64):
                self.tick()
                if self.get(2) == 1:
                    break
            self.assertEqual(self.get(2), 1)
            self.assertEqual([self.word('seconds_log', i) for i in range(80, 88)], [0] * 8)
            self.assertEqual(self.word('seconds_log', 79), 0)
            self.assertEqual(self.word('seconds_log', 88), 0)

    def test_settings_and_clean_restarts_need_no_diagnostic_cookie(self):
        self.start_pwm()
        self.setword('minute_log', 190, 2)
        self.setword('seconds_log', 59, 0)
        self.call('mode_restart_service', 16)
        self.assertEqual(self.raw(0xe000ed0c), 0x05fa0004)
        self.assertEqual([self.word('seconds_log', i) for i in (86, 87)], [0, 0])
        self.setUp()
        self.put(3, 6)
        self.put(2, 6)
        self.setword('ap_recovery', 0, 2)
        self.setword('ap_recovery', 7, 0)
        self.setword('uart_probe_good_time', 0, 1)
        self.cpu.mem_write(self.symbols['uart_probe_time_event'], (2026).to_bytes(2, 'little'))
        self.call('ap_recovery_poll')
        self.assertEqual(self.raw(0xe000ed0c), 0x05fa0004)
        self.assertEqual([self.word('seconds_log', i) for i in (86, 87)], [0, 0])


if __name__ == '__main__':
    for cls in (prior.SessionSleep, prior.PendingSession, prior.baseline.Tests,
                prior.baseline.Buttons, prior.baseline.General, prior.baseline.RTCChecks,
                prior.baseline.RecoveryChecks, prior.Handover, prior.Deadline):
        cls.artifact = IMAGE
        cls.signature = Diagnostic.signature
    selected = [Diagnostic(n) for n in Diagnostic.__dict__ if n.startswith('test_')]
    if '--session' in sys.argv:
        selected = [prior.SessionSleep(n) for n in prior.SessionSleep.__dict__ if n.startswith('test_')]
    if '--pending' in sys.argv:
        selected = [prior.PendingSession(n) for n in prior.PendingSession.__dict__ if n.startswith('test_')]
    if '--deadline' in sys.argv:
        selected = [prior.Deadline(n) for n in prior.Deadline.__dict__ if n.startswith('test_')]
    if '--handover' in sys.argv:
        selected = [prior.Handover(n) for n in prior.Handover.__dict__ if n.startswith('test_')]
    if '--regression' in sys.argv:
        selected = prior.baseline.cases()
    if '--motor' in sys.argv:
        selected = [prior.baseline.Tests(n) for n in (
            'test_normal_modes_keep_original_waveforms_and_no_ramp',
            'test_two_laps_and_normal_launch_again_after_hold',
            'test_late_ramp_irq_does_not_change_active_pulse',
            'test_overnight_stop_mode_resumes_with_ramp_without_second_timer_launch',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_always_parked_runtime_minute_width_is_valid_without_seconds_launch',
            'test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
            'test_saver_change_alone_finishes_one_safe_restart')]
    if '--part=1' in sys.argv:
        selected = selected[::2]
    if '--part=2' in sys.argv:
        selected = selected[1::2]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    raise SystemExit(not result.wasSuccessful())
