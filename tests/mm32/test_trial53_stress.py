"""Additional compiled Trial53 scenarios; firmware stays unchanged.

Runs against the existing AXF. Known-bug tests assert the desired behavior,
not the broken behavior, and are deliberately allowed to fail.
"""
import struct
import unittest
import random

from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_READ
import test_trial53_build as prior


class StressTests(prior.Tests):
    @classmethod
    def setUpClass(cls):
        with cls.artifact.open('rb') as stream:
            elf = ELFFile(stream)
            cls.loads = [(s['p_vaddr'], s.data(), s['p_memsz'])
                         for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
            cls.symbols = {s.name: s['st_value']
                           for s in elf.get_section_by_name('.symtab').iter_symbols()}
            cls.ram_end = max(s['sh_addr'] + s['sh_size'] for s in elf.iter_sections()
                              if s['sh_flags'] & 2 and 0x20000000 <= s['sh_addr'] < 0x20001000)
        cls.symbols['scan_log'] = cls.symbols['parallel_log']

    def test_stress_all_mode_changes_near_start_middle_end(self):
        for old in range(4):
            for new in range(4):
                if old == new:
                    continue
                for phase in (1, 30, 59):
                    with self.subTest(old=old, new=new, phase=phase):
                        self.setUp()
                        self.mode_run(old)
                        # Firmware receives a genuine RAM request at the chosen
                        # second; old partial minute markers must finish first.
                        self.simulate(61, [(phase, new)])
                        self.assertEqual(self.word('minute_log', 189), new)
                        self.assertEqual((self.get(22), self.word('minute_log', 191)), (706, 0))
                        self.assertEqual(self.get(13), 6)
                        self.assertEqual(self.word('minute_log', 190), 0)

    def test_stress_mode_change_cancel_all_modes(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp()
                self.mode_run(mode)
                self.simulate(61, [(9, (mode+1) % 4), (30, (mode+2) % 4), (59, mode)])
                self.assertEqual(self.word('minute_log', 189), mode)
                self.assertEqual((self.get(22), self.word('minute_log', 191)), (706, 0))
                self.assertEqual(self.get(13), 6)

    def test_stress_invalid_year_must_not_stop_valid_clock(self):
        for year in (1999, 2100, 9999):
            with self.subTest(year=year):
                self.setUp()
                self.mode_run(0)
                self.due()
                self.feed(self.message(b'00').replace(b'2026', str(year).encode()))
                self.assertEqual((self.get(2), self.get(3)), (7, 0))

    def test_stress_saved_wake_time_survives_pending_correction(self):
        self.mode_run(0)
        self.hold(2)
        self.feed(self.message(b'00', b'11:45:01'))
        self.assertEqual(self.word('daily_log', 0), 7)
        self.wire(self.message(b'00', b'11:45:02').replace(b'09:17', b'10:23'))
        self.put(30, 1)
        self.call('parallel_poll_once')
        self.assertEqual(self.get(3), 0)
        self.assertEqual((self.word('daily_log', 10), self.word('daily_log', 11)), (10, 23))

    def test_stress_overlapping_startup_time_is_coherent(self):
        self.put(1, 1)
        self.tick()
        first = self.message(b'00', b'11:45:00')
        second = self.message(b'32', b'11:45:09').replace(b'09:17', b'10:23')
        for byte in first[:-1]:
            self.cpu.mem_write(0x40004408, struct.pack('<I', 2))
            self.cpu.mem_write(0x40004404, struct.pack('<I', byte))
            self.call('parallel_poll_once')
        incoming = iter(second)
        state = {'calls': 0, 'sent': 0}

        def receive(cpu, access, address, size, value, user):
            if address == 0x40004408:
                state['calls'] += 1
                if state['calls'] > 1 and state['calls'] % 4 == 0:
                    byte = next(incoming, None)
                    if byte is not None:
                        state['sent'] += 1
                        cpu.mem_write(0x40004404, struct.pack('<I', byte))
                        cpu.mem_write(address, struct.pack('<I', 2))

        handle = self.cpu.hook_add(UC_HOOK_MEM_READ, receive)
        try:
            self.cpu.mem_write(0x40004408, struct.pack('<I', 2))
            self.cpu.mem_write(0x40004404, struct.pack('<I', 10))
            self.call('parallel_poll_once')
        finally:
            self.cpu.hook_del(handle)
        self.assertEqual(state['sent'], len(second))
        decode = lambda value: (value >> 4) * 10 + (value & 15)
        rtc = tuple(decode(self.bus.data[i]) for i in (4, 3, 2))
        self.assertEqual((self.get(16), self.get(15), self.get(5)), rtc)

    def test_stress_partial_release_is_safe_and_full_release_rearms_rec(self):
        self.put(1, 1)
        self.tick()
        self.hold(3, 128, poll=False)
        self.hold(1, 512, poll=False)
        # Documented gesture protection: partial release of a combined hold
        # cannot become REC. Fully release before accepting a new gesture.
        self.assertEqual(self.button(9), 0)
        self.hold(0, 4, poll=False)
        self.hold(1, 388, poll=False)
        self.assertEqual(self.button(9), 1)

    def test_stress_catchup_keeps_gap_over_tick_rollover(self):
        self.mode_run(0)
        self.put(2, 10)
        self.put(26, 0)
        self.put(22, 700)
        self.put(15, 45)
        self.put(16, 11)
        self.put(4, 0xfffffffa)
        self.put(25, 0xfffffff0)
        self.setword('rtc_edge_tick', 0, 0xfffffffa)
        self.setword('minute_due', 0, 2)
        self.setword('minute_end', 0, 0xfffffffe)
        self.setword('minute_active', 0, 1)
        for _ in range(4):
            self.tick()
        self.assertEqual(self.get(23), 1)
        self.assertEqual(self.word('minute_active', 0), 0)

    def test_stress_random_uart_noise_preserves_valid_state(self):
        self.mode_run(1)
        self.due()
        rng = random.Random(530010)
        before = (self.word('uart_probe_good_time'), self.word('minute_log', 194),
                  self.word('daily_log', 10), self.word('daily_log', 11))
        for case in range(256):
            length = rng.randrange(0, 121)
            noise = bytes(rng.randrange(0, 256) for _ in range(length)) + b'\r\n'
            self.wire(noise)
            self.assertEqual((self.get(2), self.get(3)), (7, 0), case)
            after = (self.word('uart_probe_good_time'), self.word('minute_log', 194),
                     self.word('daily_log', 10), self.word('daily_log', 11))
            self.assertEqual(after, before, case)

    def test_stress_supported_calendar_boundaries_remain_valid(self):
        for date, time in ((b'Sat Jan  1', b'00:00:00 2000'),
                           (b'Tue Feb 29', b'12:00:00 2000'),
                           (b'Thu Dec 31', b'12:00:00 2099')):
            with self.subTest(date=date, time=time):
                self.setUp()
                self.put(1, 1)
                self.tick()
                line = b'+TIME:' + date + b' ' + time + b' +0100 09:17\r\n'
                self.feed(line)
                self.assertEqual(self.get(6), 1)
                # Shortcut mechanical acquisition, not RTC/calendar decoding.
                self.put(2, 7)
                self.put(7, 1)
                self.put(8, 1)
                self.put(26, 1)
                self.put(22, (self.get(16)*60 + self.get(15)) % 720)
                self.call('parallel_poll_once')
                self.assertEqual((self.get(2), self.get(3)), (7, 0))


def load_tests(loader, tests, pattern):
    # Do not repeat all inherited regressions in the stress worker. The full
    # Trial53 suite is run separately, including its original build checks.
    return unittest.TestSuite(StressTests(name) for name in sorted(StressTests.__dict__)
                              if name.startswith('test_stress_'))


if __name__ == '__main__':
    unittest.main()
