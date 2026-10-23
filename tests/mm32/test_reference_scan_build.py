"""Compile/emulate the bounded MM32 reference-crossing diagnostic."""
import struct
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / '.analysis_deps'))
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_MCLASS, UC_MODE_THUMB, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR

COMPILER = Path('C:/Users/Steve/AppData/Local/Keil_v5/ARM/ARMCLANG/bin/armclang.exe')
AXF = ROOT / 'build/MM32SPIN05PF_REFERENCE_TRIAL02_20261007.axf'
HEX = AXF.with_suffix('.hex')


class ReferenceScanTests(unittest.TestCase):
    artifact = AXF
    cycles = 8
    signature = 0x4D523032
    reference_start = 709
    interval = 128
    extra_defines = []

    @classmethod
    def setUpClass(cls):
        subprocess.run([str(COMPILER), '--target=arm-arm-none-eabi', '-mcpu=cortex-m0',
            '-mthumb', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
            '-DMM32_REFERENCE_SCAN', f'-DMAX_CYCLES={cls.cycles}',
            f'-DREFERENCE_SIGNATURE={hex(cls.signature)}u', '-Wl,--scatter=mm32spin05.sct',
            f'-DSCAN_INTERVAL_TICKS={cls.interval}',
            *cls.extra_defines,
            '-Wl,--entry=Reset_Handler', 'startup.c', 'reference_scan_main.c',
            'motor_scan_probe.c', '-o', str(cls.artifact)], cwd=ROOT / 'target',
            check=True, capture_output=True, text=True)
        subprocess.run([str(COMPILER.with_name('fromelf.exe')), '--i32',
                        f'--output={cls.artifact.with_suffix(".hex")}', str(cls.artifact)], check=True, capture_output=True)
        with cls.artifact.open('rb') as handle:
            elf = ELFFile(handle)
            cls.loads = [(s['p_vaddr'], s.data(), s['p_memsz']) for s in
                         elf.iter_segments() if s['p_type'] == 'PT_LOAD']
            cls.symbols = {s.name: s['st_value'] for s in
                          elf.get_section_by_name('.symtab').iter_symbols()}
        print(cls.artifact.stem, 'scan_log:', hex(cls.symbols['scan_log']))

    def setUp(self):
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for addr, size in ((0x08000000, 0x10000), (0x20000000, 0x1000),
                           (0xE000E000, 0x1000), (0x40021000, 0x1000),
                           (0x48000000, 0x1000)):
            self.cpu.mem_map(addr, size)
        for addr, data, _ in self.loads:
            if data: self.cpu.mem_write(addr, data)
        self.writes = []
        self.output = 0
        def record(cpu, access, addr, size, value, user):
            self.writes.append((addr, value))
            if addr == 0x48000410:
                self.output = (self.output | (value & 65535)) & ~(value >> 16)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, record)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x20001000)
        self.cpu.emu_start(self.symbols['Reset_Handler'], 0x08007000, count=3000)

    def get(self, index):
        return struct.unpack('<I', self.cpu.mem_read(self.symbols['scan_log'] + index*4, 4))[0]

    def put(self, index, value):
        self.cpu.mem_write(self.symbols['scan_log'] + index*4, struct.pack('<I', value))

    def tick(self, high=0):
        self.cpu.mem_write(0x48000408, struct.pack('<I', high << 14))
        sentinel=getattr(self, 'return_sentinel', 0x08007000)
        self.cpu.reg_write(UC_ARM_REG_LR, sentinel|1)
        self.cpu.emu_start(self.symbols['SysTick_Handler'], sentinel,
                           count=getattr(self, 'irq_instruction_budget', 2000))
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP), 0x20000FF8)

    def arm(self):
        self.put(1, 1)
        self.tick()
        self.assertEqual(self.get(2), 1)

    def advance(self, high=0):
        count = self.get(5)
        for _ in range(200):
            self.tick(high)
            if self.get(5) == count + 1 and self.get(2) != 3:
                return
        self.fail('request failed to finish')

    def released(self):
        self.assertEqual(self.output & ((1 << 13) | (1 << 15) | 7), 0)
        crl = struct.unpack('<I', self.cpu.mem_read(0x48000400, 4))[0]
        crh = struct.unpack('<I', self.cpu.mem_read(0x48000404, 4))[0]
        self.assertEqual(crl & 0xFFF, 0x444)
        self.assertEqual(crh & ((15 << 20) | (15 << 28)), (4 << 20) | (4 << 28))

    def test_vectors_size_boot_and_idle(self):
        image = next(data for addr, data, _ in self.loads if addr == 0x08000000)
        self.assertEqual(struct.unpack_from('<I', image, 0)[0], 0x20001000)
        self.assertEqual(struct.unpack_from('<I', image, 60)[0], self.symbols['SysTick_Handler'])
        for addr, _, size in self.loads:
            self.assertTrue(0x08000000 <= addr and addr+size <= 0x08008000 or
                            0x20000000 <= addr and addr+size <= 0x20001000)
        self.assertEqual(self.get(0), self.signature)
        for _ in range(128): self.tick()
        self.assertFalse(any(0x48000000 <= a < 0x48001000 for a, _ in self.writes))

    def test_checkpoint_and_full_720_request_bound(self):
        self.arm()
        for _ in range(10): self.advance()
        self.assertEqual((self.get(1), self.get(2), self.get(5)), (0, 4, 10))
        self.released()
        for _ in range(128): self.tick()
        self.assertEqual(self.get(5), 10)
        self.put(1, 2)
        self.tick()
        self.assertEqual(self.get(2), 1)
        for step in range(11, 721):
            self.advance(int(self.reference_start <= step <= self.reference_start+2))
        self.assertEqual((self.get(1), self.get(2), self.get(3), self.get(5)), (0, 5, 0, 720))
        samples = self.cycles//2 + 32
        self.assertEqual(self.get(6), 720*samples)
        self.assertEqual((self.get(7), self.get(8), self.get(11), self.get(12)),
                         (3*samples, 2, self.reference_start, self.reference_start+2))
        self.released()
        snapshot = bytes(self.cpu.mem_read(self.symbols['scan_log'] + 20, 40))
        for _ in range(128): self.tick(1)
        self.assertEqual(bytes(self.cpu.mem_read(self.symbols['scan_log'] + 20, 40)), snapshot)
        self.put(1, 1)
        self.tick()
        self.assertEqual((self.get(2), self.get(3)), (6, 1))

    def test_powered_tail_sample_context_and_release(self):
        self.arm()
        for _ in range(self.interval-1+4*self.cycles): self.tick()
        self.assertEqual(self.get(2), 3)
        self.assertEqual(self.output & ((1 << 13) | (1 << 15)), 1 << 15)
        self.assertEqual(self.get(13), 32)
        for _ in range(32):
            self.assertEqual(self.output & ((1 << 13) | (1 << 15)), 1 << 15)
            self.tick(1)
        self.assertEqual((self.get(7), self.get(8), self.get(11)), (32, 1, 1))
        self.assertEqual(self.get(2), 1)
        self.released()

    def test_high_or_noisy_signal_never_changes_configured_cycle_drive(self):
        self.arm()
        for n in range(self.interval-1+4*self.cycles): self.tick(n & 1)
        self.assertEqual((self.get(5), self.get(2), self.get(3)), (1, 3, 0))
        addr = self.symbols['motor_scan_cycle']
        self.assertEqual(struct.unpack('<I', self.cpu.mem_read(addr, 4))[0], self.cycles)
        for n in range(32): self.tick(n & 1)
        self.assertGreater(self.get(8), 2)
        self.assertEqual(self.get(3), 0)

    def test_disable_during_motor_and_tail_releases_and_blocks_rearm(self):
        for ticks in (self.interval, self.interval+4*self.cycles):
            self.setUp()
            self.arm()
            for _ in range(ticks): self.tick()
            self.put(1, 0)
            self.tick()
            self.assertEqual(self.get(2), 6)
            self.released()
            self.put(1, 1)
            self.tick()
            self.assertEqual((self.get(1), self.get(3)), (0, 1))

    def test_event_buffer_saturates_without_corruption(self):
        self.arm()
        for n in range(640): self.tick(n & 1)
        self.assertGreater(self.get(8), 60)
        self.assertEqual(self.get(9), self.get(8) - 60)
        first_events = bytes(self.cpu.mem_read(self.symbols['scan_log'] + 64, 960))
        for n in range(256): self.tick(n & 1)
        self.assertEqual(bytes(self.cpu.mem_read(self.symbols['scan_log'] + 64, 960)), first_events)
        self.assertTrue(all(0x20000000 <= a < 0x20001000 or
                           a in (0xE000E010, 0xE000E014, 0xE000E018, 0x40021014,
                                 0x48000400, 0x48000404, 0x48000410)
                           for a, _ in self.writes))

    def test_fault_handler_disables_future_movement(self):
        self.arm()
        for _ in range(self.interval): self.tick()
        self.cpu.emu_start(self.symbols['Default_Handler'], 0x08007000, count=1000)
        self.assertEqual((self.get(1), self.get(2), self.get(3)), (0, 6, 3))
        self.released()
        before = self.get(5)
        for _ in range(128): self.tick()
        self.assertEqual(self.get(5), before)


if __name__ == '__main__': unittest.main()
