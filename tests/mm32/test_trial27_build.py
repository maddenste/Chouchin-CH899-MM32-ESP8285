"""Offline compiled PB8/PB9 probe tests with an emulated I2C slave."""
import struct
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / '.analysis_deps'))
from elftools.elf.elffile import ELFFile
from intelhex import IntelHex
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR
COMPILER = Path('C:/Users/Steve/AppData/Local/Keil_v5/ARM/ARMCLANG/bin/armclang.exe')
AXF = ROOT / 'build/MM32SPIN05PF_RTC_READ_PB8_PB9_TRIAL27_20261007.axf'
HEX = AXF.with_suffix('.hex')

class Bus:
    def __init__(self, ack=True, data=None, nack_at=None, stuck_at=None):
        self.crh = 0x44444444
        self.odr = 0
        self.slave = 1
        self.mode = 'idle'
        self.bits = 0
        self.byte = 0
        self.received = []
        self.master_acks = []
        self.data = data or list(range(16))
        self.index = 0
        self.ack = ack
        self.nack_at = nack_at
        self.stuck_at = stuck_at
        self.clocks = 0
        self.starts = self.stops = 0
        self.force_busy = False

    def master(self, pin):
        mode = (self.crh >> ((pin - 8) * 4)) & 15
        return 1 if mode == 4 else int(bool(self.odr & (1 << pin)))

    def levels(self):
        scl = self.master(8)
        if self.stuck_at is not None and self.clocks >= self.stuck_at: scl = 0
        return scl, self.master(9) & self.slave & (not self.force_busy)

    def tx_level(self):
        self.slave = (self.data[self.index] >> (7 - self.bits)) & 1

    def write(self, addr, value):
        old_scl, old_sda = self.levels()
        if addr == 0x48000404: self.crh = value
        elif addr == 0x48000410:
            self.odr = (self.odr | (value & 0xffff)) & ~(value >> 16)
        else: return
        scl, sda = self.levels()
        if old_scl and scl and old_sda != sda:
            if not sda:
                self.starts += 1
                self.mode, self.bits, self.byte, self.slave = 'rx', 0, 0, 1
            else:
                self.stops += 1
                self.mode, self.slave = 'idle', 1
            return
        if not old_scl and scl:
            self.clocks += 1
            if self.mode == 'rx':
                self.byte = (self.byte << 1) | sda
                self.bits += 1
                if self.bits == 8: self.mode = 'rx8'
            elif self.mode == 'ack': self.mode = 'ack_done'
            elif self.mode == 'tx':
                self.bits += 1
                if self.bits == 8: self.mode = 'tx8'
            elif self.mode == 'master_ack':
                self.master_acks.append(not sda)
                self.mode = 'master_ack_done'
        elif old_scl and not scl:
            if self.mode == 'rx8':
                self.received.append(self.byte)
                allowed = self.ack and len(self.received) != self.nack_at
                self.slave = 0 if allowed else 1
                self.mode = 'ack'
            elif self.mode == 'ack_done':
                if self.byte == 0xa3 and self.slave == 0:
                    self.mode, self.bits, self.index = 'tx', 0, 0
                    self.tx_level()
                else: self.mode, self.bits, self.byte, self.slave = 'rx', 0, 0, 1
            elif self.mode == 'tx': self.tx_level()
            elif self.mode == 'tx8': self.mode, self.slave = 'master_ack', 1
            elif self.mode == 'master_ack_done':
                if self.master_acks[-1]:
                    self.index += 1
                    self.mode, self.bits = 'tx', 0
                    self.tx_level()
                else: self.mode, self.slave = 'idle', 1

class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([str(COMPILER), '--target=arm-arm-none-eabi', '-mcpu=cortex-m0',
                        '-mthumb', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-Wl,--scatter=rtc_survey.sct', '-Wl,--entry=Reset_Handler',
                        'startup.c', 'rtc_read_probe.c', '-o', str(AXF)],
                       cwd=ROOT / 'target', check=True, capture_output=True, text=True)
        subprocess.run([str(COMPILER.with_name('fromelf.exe')), '--i32', f'--output={HEX}',
                        str(AXF)], check=True, capture_output=True)
        with AXF.open('rb') as f:
            elf = ELFFile(f)
            cls.loads = [(s['p_vaddr'], s.data()) for s in elf.iter_segments()
                         if s['p_type'] == 'PT_LOAD']
            cls.symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        assert cls.symbols['rtc_probe'] == 0x20000000
        assert cls.symbols['Image$$RW_IRAM1$$ZI$$Limit'] < 0x20000C00

    def setUp(self):
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for base, size in [(0x08000000,0x8000), (0x20000000,0x1000),
                           (0x40021000,0x1000), (0x48000000,0x1000)]: self.cpu.mem_map(base,size)
        for base,data in self.loads:
            if data: self.cpu.mem_write(base,data)
        self.bus = Bus()
        self.writes = []
        def write(uc, access, addr, size, value, user):
            self.writes.append((addr,value))
            self.bus.write(addr,value)
        def read(uc, access, addr, size, value, user):
            if addr == 0x48000408:
                scl,sda = self.bus.levels()
                uc.mem_write(addr, struct.pack('<I', (0xf08 & ~0x300) | (scl << 8) | (sda << 9)))
            elif addr == 0x48000404: uc.mem_write(addr,struct.pack('<I', self.bus.crh))
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,write)
        self.cpu.hook_add(UC_HOOK_MEM_READ,read)
        self.cpu.reg_write(UC_ARM_REG_SP,0x20001000)
        self.cpu.emu_start(self.symbols['Reset_Handler'],0x08007F00,count=30000)

    def word(self,offset): return struct.unpack('<I',self.cpu.mem_read(0x20000000+offset,4))[0]
    def call(self,name='probe_poll'):
        self.cpu.reg_write(UC_ARM_REG_LR,0x08007F01)
        self.cpu.emu_start(self.symbols[name],0x08007F00,count=1000000)
    def run_command(self,value=1):
        self.cpu.mem_write(0x20000004,struct.pack('<I',value)); self.call()
    def assert_safe_writes(self):
        for addr,value in self.writes:
            if 0x20000000 <= addr < 0x20001000: continue
            self.assertIn(addr,(0x40021014,0x48000404,0x48000410))
            if addr == 0x40021014: self.assertEqual(value,1 << 18)
            elif addr == 0x48000404:
                self.assertEqual(value & ~0xff,0x44444400)
                self.assertIn(value & 0xff,(0x44,0x66))
            else:
                self.assertEqual(value & ~0x03000300,0)
        self.assertEqual(self.bus.crh,0x44444444)
        self.assertEqual(self.bus.odr & 0x300,0x300)

    def test_boot_and_invalid_command_are_gpio_inert(self):
        self.assertEqual(self.word(0),0x4D503237)
        self.run_command(99)
        self.assertEqual(self.word(8),10)
        self.assertFalse(any(a < 0x20000000 or a >= 0x20001000 for a,v in self.writes))

    def test_full_read_exact_protocol_and_one_attempt(self):
        self.run_command()
        self.assertEqual(self.word(8),2)
        self.assertEqual(self.word(20),7)
        self.assertEqual(self.word(24),16)
        self.assertEqual([self.word(48+4*i) for i in range(16)],self.bus.data)
        self.assertEqual(self.bus.received,[0xa2,0,0xa3])
        self.assertEqual(self.bus.starts,2)
        self.assertEqual(self.bus.stops,1)
        self.assertEqual(self.bus.master_acks,[True]*15+[False])
        old = len(self.writes)
        self.run_command()
        self.assertFalse(any(a >= 0x40000000 for a,v in self.writes[old:]))
        self.assert_safe_writes()

    def test_address_nack_releases(self):
        self.bus.ack=False; self.run_command()
        self.assertEqual(self.word(8),4)
        self.assertEqual(self.bus.received,[0xa2])
        self.assert_safe_writes()

    def test_pointer_and_read_address_nacks_release(self):
        for number, status in [(2,5),(3,6)]:
            self.setUp(); self.bus.nack_at=number; self.run_command()
            self.assertEqual(self.word(8),status)
            self.assert_safe_writes()

    def test_busy_bus_never_drives(self):
        self.bus.force_busy=True; self.run_command()
        self.assertEqual(self.word(8),3)
        self.assertFalse(any(a >= 0x48000000 for a,v in self.writes))

    def test_clock_timeout_releases_without_recovery_scan(self):
        self.bus.stuck_at=4; self.run_command()
        self.assertEqual(self.word(8),7)
        self.assertLessEqual(self.word(44),210)
        self.assert_safe_writes()

    def test_timeout_mid_read_releases(self):
        self.bus.stuck_at=50; self.run_command()
        self.assertEqual(self.word(8),7)
        self.assertGreater(self.word(24),0)
        self.assertLess(self.word(24),16)
        self.assert_safe_writes()

    def test_read_preserves_all_raw_bits(self):
        self.bus.data=[0,0x80,0x59,0x23,0x31,6,0x92,0x26,0xff,1,2,3,4,5,6,7]
        self.run_command()
        self.assertEqual(self.word(8),2)
        self.assertEqual([self.word(48+4*i) for i in range(16)],self.bus.data)
        self.assertEqual(self.bus.received,[0xa2,0,0xa3])
        self.assert_safe_writes()

    def test_existing_configuration_not_overridden(self):
        self.bus.crh=0x44444422; self.run_command()
        self.assertEqual(self.word(8),8)
        self.assertFalse(any(a >= 0x48000000 for a,v in self.writes))

    def test_fault_releases_only_test_pair(self):
        self.cpu.mem_write(self.symbols['active'],struct.pack('<I',1))
        self.cpu.mem_write(0x20000024,struct.pack('<I',0x44444444))
        self.bus.crh=0x44444466
        self.cpu.emu_start(self.symbols['Default_Handler'],0x08007F00,count=1000)
        self.assert_safe_writes()

    def test_image_bounds(self):
        image=IntelHex(str(HEX))
        self.assertGreaterEqual(image.minaddr(),0x08000000)
        self.assertLess(image.maxaddr(),0x08008000)
        self.assertEqual(struct.unpack('<I',bytes(image[i] for i in range(0x08000000,0x08000004)))[0],0x20001000)

if __name__ == '__main__': unittest.main()
