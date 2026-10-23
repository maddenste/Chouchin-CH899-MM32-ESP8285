"""Seconds-only GPIO mode01 trial; RC6E timing/diagnostic regressions."""
import unittest
from pathlib import Path
from test_rc6e_diag import Tests as RC6E
from unicorn import UC_HOOK_MEM_WRITE


class Tests(RC6E):
    artifact = RC6E.artifact.parent.parent.parent / 'release_candidate_rc6f/build/MM32SPIN05PF_GPIO_MODE01_RC6F_20261021.axf'
    signature = 0x4d50526f

    def setUp(self):
        super().setUp()
        # Monitor actual CPU writes in every inherited regression, including
        # REC/recovery/parking, not merely the shortcut running fixture.
        def gpio_mode(cpu, access, address, size, value, user):
            if address == 0x48000000:
                self.assertNotEqual((value >> 28) & 15, 2, 'PA7 restored old mode10')
            elif address == 0x48000400:
                self.assertNotEqual(value & 15, 2, 'PB0 restored old mode10')
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, gpio_mode,
                          begin=0x48000000, end=0x48000400)

    def seconds_mode(self):
        a = int.from_bytes(self.cpu.mem_read(0x48000000, 4), 'little')
        b = int.from_bytes(self.cpu.mem_read(0x48000400, 4), 'little')
        return (a >> 28) & 15, b & 15, (b >> 4) & 255

    def test_gpio_exact_source_scope(self):
        before = Path(__file__).parent / 'release_candidate_rc6e/src'
        after = Path(__file__).parent / 'release_candidate_rc6f/src'
        self.assertEqual({p.relative_to(before) for p in before.rglob('*') if p.is_file()},
                         {p.relative_to(after) for p in after.rglob('*') if p.is_file()})
        for p in after.rglob('*'):
            if not p.is_file(): continue
            rel = p.relative_to(after)
            old = (before / rel).read_bytes()
            new = p.read_bytes()
            if p.name in ('parallel_home_main.c', 'parallel_buttons_rebuild.h'):
                new = new.replace(b'A_CRL = (A_CRL & ~(15u << 28)) | (1u << 28);',
                                  b'A_CRL = (A_CRL & ~(15u << 28)) | (2u << 28);')
                new = new.replace(b'| 0x221u;', b'| 0x222u;')
                new = new.replace(b'GPIOB_CRL = (GPIOB_CRL & ~15u) | 1u;',
                                  b'GPIOB_CRL = (GPIOB_CRL & ~15u) | 2u;')
                new = new.replace(b'0x4d50526fu', b'0x4d50526eu')
                new = new.replace(b'RC6F trials seconds GPIO mode01; RC6E timing and telemetry are retained.',
                                  b'RC6E adds edge telemetry without changing RC6D movement settings.')
                # apply_patch may normalize line endings, not source semantics.
                self.assertEqual(new.replace(b'\r\n', b'\n'), old.replace(b'\r\n', b'\n'), str(rel))
            else:
                self.assertEqual(new, old, str(rel))

    def test_gpio_homing_catchup_shutdown_and_rec(self):
        self.tick()  # Real startup/homing GPIO configuration.
        self.assertEqual(self.seconds_mode(), (1, 1, 0x22))
        self.call('motors_off')
        self.assertEqual(self.seconds_mode(), (4, 4, 0x44))
        self.call('catchup_begin', self.get(4))
        self.assertEqual(self.seconds_mode(), (1, 1, 0x22))
        self.setUp()
        self.test_rec_drains_hardware_pulse_and_queued_minute()
        self.assertEqual(self.get(2), 1)
        self.assertEqual(self.seconds_mode(), (1, 1, 0x22))

    def test_gpio_waveform_and_other_gpio_match_rc6e_all_modes(self):
        RC6E.setUpClass()
        for mode in range(4):
            old = RC6E(); old.setUp(); self.setUp()
            histories = []
            for t in (old, self):
                history = []
                def gpio(cpu, access, address, size, value, user):
                    if address == 0x48000000 and (value >> 28) & 15 == 1:
                        value = (value & ~(15 << 28)) | (2 << 28)
                    if address == 0x48000400 and value & 15 == 1:
                        value = (value & ~15) | 2
                    history.append((address, value))
                hook = t.cpu.hook_add(UC_HOOK_MEM_WRITE, gpio,
                                      begin=0x48000000, end=0x480007ff)
                t.mode_run(mode)
                t.setword('request_pulses', 0, 6)
                t.call('fine_minutes_rise', t.counter)
                t.advance_timer(t.word('minute_log', 181) * 128)
                t.cpu.hook_del(hook)
                histories.append(history)
            self.assertEqual(self.edges, old.edges)
            self.assertEqual(histories[0], histories[1])
            self.assertEqual(self.seconds_mode()[:2], (1, 1))
            self.assertEqual(self.get(3), 0)


if __name__ == '__main__': unittest.main()
