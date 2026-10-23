"""Compiled Trial28 tests: legacy UART plus an open-drain PCF8563 model."""
import struct
import subprocess
import unittest
import test_trial27_build as base
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from elftools.elf.elffile import ELFFile
from intelhex import IntelHex
ROOT=base.ROOT
AXF=ROOT/'build/MM32SPIN05PF_WIFI_RTC_SET_TRIAL28B_20261008.axf'
HEX=AXF.with_suffix('.hex')
class RTC(base.Bus):
    def __init__(self):
        super().__init__(data=[8,0,0xd5,0x16,2,1,0,1,0,0x80,0x80,0x80,0x80,0x80,3,0x20])
        self.pos=0; self.address=0; self.pointer=0; self.calendar_writes=[]; self.readback_override=None
        self.calendar_snapshots=[]; self.calendar_read_count=0; self.snapshot=None
    def write(self,addr,value):
        starts=self.starts; count=len(self.received)
        super().write(addr,value)
        if self.starts!=starts:
            self.pos=0
            if self.starts==4 and self.readback_override:
                for r,b in self.readback_override.items(): self.data[r]=b
        if len(self.received)!=count:
            b=self.received[-1]
            accepted=self.ack and len(self.received)!=self.nack_at
            if self.pos==0: self.address=b
            elif self.pos==1: self.pointer=b
            elif accepted and self.address==0xa2:
                self.calendar_writes.append((self.pointer,b))
                self.data[self.pointer]=b
                self.pointer+=1
            self.pos+=1
    def tx_level(self):
        # base.Bus resets transmit index to zero at each read address.
        # A real PCF8563 instead starts at the selected register pointer.
        if self.index==0 and self.bits==0:
            self.snapshot=self.data[:]
            if self.pointer==2:
                self.calendar_read_count+=1
                if self.calendar_snapshots:
                    for r,b in self.calendar_snapshots.pop(0).items(): self.snapshot[r]=b
        self.slave=(self.snapshot[(self.pointer+self.index)%16]>>(7-self.bits))&1

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([str(base.COMPILER),'--target=arm-arm-none-eabi','-mcpu=cortex-m0',
            '-mthumb','-std=gnu11','-O2','-Wall','-Wextra','-Werror',
            '-Wl,--scatter=rtc_survey.sct','-Wl,--entry=Reset_Handler',
            'startup.c','wifi_rtc_set_trial28.c','../mm32_uart.c','-o',str(AXF)],
            cwd=ROOT/'target',check=True,capture_output=True,text=True)
        subprocess.run([str(base.COMPILER.with_name('fromelf.exe')),'--i32',f'--output={HEX}',str(AXF)],check=True,capture_output=True)
        with AXF.open('rb') as f:
            elf=ELFFile(f)
            cls.loads=[(s['p_vaddr'],s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
            cls.symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        assert cls.symbols['wifi_rtc']==0x20000000
        assert cls.symbols['Image$$RW_IRAM1$$ZI$$Limit']<0x20000c00
    def setUp(self):
        self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        for a,n in [(0x08000000,0x8000),(0x20000000,0x1000),(0x40021000,0x1000),
                    (0x48000000,0x1000),(0x40004000,0x1000),(0xe000e000,0x1000)]: self.cpu.mem_map(a,n)
        for a,data in self.loads:
            if data: self.cpu.mem_write(a,data)
        self.bus=RTC(); self.writes=[]
        def write(uc,access,a,size,v,user): self.writes.append((a,v)); self.bus.write(a,v)
        def read(uc,access,a,size,v,user):
            if a==0x48000408:
                scl,sda=self.bus.levels(); self.put(a,(scl<<8)|(sda<<9))
            elif a==0x48000404: self.put(a,self.bus.crh)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,write); self.cpu.hook_add(UC_HOOK_MEM_READ,read)
        for a in [0x48000000,0x48000004,0x48000400]: self.put(a,0x44444444)
        self.cpu.reg_write(UC_ARM_REG_SP,0x20001000)
        self.cpu.emu_start(self.symbols['Reset_Handler'],0x08007f00,count=30000)
    def put(self,a,v): self.cpu.mem_write(a,struct.pack('<I',v))
    def word(self,offset): return struct.unpack('<I',self.cpu.mem_read(0x20000000+offset,4))[0]
    def call(self,name='wifi_rtc_poll'):
        self.cpu.reg_write(UC_ARM_REG_LR,0x08007f01)
        self.cpu.emu_start(self.symbols[name],0x08007f00,count=2000000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),0x08007f00)
    def command(self,v=1): self.put(0x20000004,v); self.call()
    def feed(self,line=b'+TIME:Thu Oct  8 02:30:45 2026 +0100 09:00\r\n'):
        for b in line:
            self.put(0x40004408,2); self.put(0x40004404,b); self.call()
        self.put(0x40004408,0)
    def assert_safe(self):
        allowed={0x40021014,0x4002101c,0x48000000,0x48000010,0x48000020,
                 0x48000400,0x48000404,0x48000410,0x48000414,0x48000420,
                 0x40004400,0x40004414,0x40004418,0x4000441c,0x40004420,0x40004424,
                 0xe000e010,0xe000e014,0xe000e018}
        for a,v in self.writes:
            if 0x20000000<=a<0x20001000: continue
            self.assertIn(a,allowed)
            if a==0x48000404: self.assertEqual(v&~0xff,0x44444400); self.assertIn(v&0xff,[0x44,0x66])
            if a==0x48000400: self.assertEqual(v&~0xf0000,0x44404444)
            if a==0x48000000: self.assertEqual(v&~0xff00,0x44440044)
            if a==0x48000410: self.assertEqual(v&~0x03000310,0)
            if a==0x48000414: self.assertEqual(v,16)
            if a==0x48000010: self.assertEqual(v,4)
        self.assertEqual(self.bus.crh,0x44444444)
        self.assertTrue(all(2<=r<=8 for r,v in self.bus.calendar_writes))
    def test_boot_inert(self):
        self.assertEqual(self.word(0),0x4d503238); self.command(99)
        self.assertEqual(self.word(8),3); self.assertFalse([a for a,v in self.writes if a>=0x40000000])
    def test_debugger_command_after_idle_load_survives_resume(self):
        state={'loaded':False,'halted':False}
        def read(uc,access,a,size,v,user):
            if a==0x20000004: state['loaded']=True
        def code(uc,a,size,user):
            if state['loaded'] and not state['halted']:
                state['halted']=True; uc.emu_stop()
        h1=self.cpu.hook_add(UC_HOOK_MEM_READ,read)
        h2=self.cpu.hook_add(UC_HOOK_CODE,code)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        self.cpu.reg_write(UC_ARM_REG_LR,0x08007f01)
        self.cpu.emu_start(self.symbols['wifi_rtc_poll'],0x08007f00,count=1000)
        self.assertTrue(state['halted'])
        self.cpu.hook_del(h1); self.cpu.hook_del(h2)
        self.put(0x20000004,1)
        pc=self.cpu.reg_read(UC_ARM_REG_PC)
        self.cpu.emu_start(pc|1,0x08007f00,count=10000)
        self.assertEqual(self.word(4),1)
        self.call(); self.assertEqual(self.word(8),1)
        self.assertEqual(self.word(12),1); self.assert_safe()
    def test_success_preserves_controls_clears_vl_and_ignores_offset(self):
        original=self.bus.data[:]; self.command(); self.feed()
        self.assertEqual(self.word(8),2); self.assertEqual(self.word(56),7); self.assertEqual(self.word(60),1)
        self.assertEqual(self.bus.data[2:9],[0x45,0x30,2,8,4,0x10,0x26])
        self.assertEqual([self.bus.data[i] for i in [0,1,9,10,11,12,13,14,15]],
                         [original[i] for i in [0,1,9,10,11,12,13,14,15]])
        self.assertEqual(self.bus.received,[0xa2,0,0xa3,0xa2,2,0x45,0x30,2,8,4,0x10,0x26,0xa2,0,0xa3])
        self.assertEqual(self.bus.master_acks,[True]*15+[False]+[True]*15+[False])
        count=len(self.bus.calendar_writes); self.command(); self.feed()
        self.assertEqual(len(self.bus.calendar_writes),count); self.assert_safe()
    def test_bad_lines_and_ack_do_not_write(self):
        self.command(); self.feed(b'garbage\r\n'); self.feed(b'+USER:OK\r\n')
        self.assertEqual(self.word(8),1); self.assertEqual(self.bus.received,[])
        self.command(2); self.assertEqual(self.word(8),4); self.assert_safe()
    def test_invalid_year_no_write(self):
        self.command(); self.feed(b'+TIME:Thu Oct  8 02:30:45 1999 +0100 09:00\r\n')
        self.assertEqual(self.word(8),6); self.assertEqual(self.bus.received,[]); self.assert_safe()
    def test_timeout(self):
        self.command(); self.put(self.symbols['legacy_ticks'],15360); self.call()
        self.assertEqual(self.word(8),5); self.assertEqual(self.bus.received,[]); self.assert_safe()
    def test_user_requests_unchanged(self):
        self.command(); self.put(self.symbols['legacy_ticks'],256); self.put(0x40004408,1)
        for _ in range(5): self.call()
        self.assertEqual([v for a,v in self.writes if a==0x40004400],list(b'USER\n')); self.assert_safe()
    def test_nacks_before_and_during_write(self):
        for n in [1,2,3,4,5,6,9,12,13,14,15]:
            self.setUp(); self.bus.nack_at=n; self.command(); self.feed()
            self.assertEqual(self.word(8),7); self.assertEqual(self.word(20),4); self.assert_safe()
    def test_stuck_clock_releases(self):
        self.bus.stuck_at=40; self.command(); self.feed()
        self.assertEqual(self.word(8),7); self.assertEqual(self.word(20),7); self.assert_safe()
    def test_busy_or_existing_pin_configuration_not_overridden(self):
        for mode in ['busy','configured']:
            self.setUp()
            if mode=='busy': self.bus.force_busy=True
            else: self.bus.crh=0x44444422
            self.command(); self.feed(); self.assertEqual(self.word(8),7)
            self.assertEqual(self.bus.received,[]); self.assertFalse(self.bus.calendar_writes)
    def test_stopped_rtc_refused(self):
        self.bus.data[0]=0x28; self.command(); self.feed()
        self.assertEqual(self.word(8),7); self.assertEqual(self.word(20),9)
        self.assertFalse(self.bus.calendar_writes); self.assert_safe()
    def test_leap_day_weekday(self):
        self.command(); self.feed(b'+TIME:Thu Feb 29 23:59:59 2024 +0000 09:00\r\n')
        self.assertEqual(self.word(8),2); self.assertEqual(self.bus.data[2:9],[0x59,0x59,0x23,0x29,4,2,0x24]); self.assert_safe()
    def test_uart_error_refuses_write(self):
        self.command(); self.put(0x4000440c,16); self.feed()
        self.assertEqual(self.word(8),6); self.assertFalse(self.bus.calendar_writes); self.assert_safe()
    def test_bad_readback_never_reports_success(self):
        for override in [{2:0xc5},{2:0x46,13:0},{3:0x6a},{6:5},{2:0x48}]:
            self.setUp(); self.bus.readback_override=override; self.command(); self.feed()
            self.assertEqual(self.word(8),8); self.assertEqual(self.word(60),0); self.assert_safe()
    def test_readback_accepts_one_second_midnight_rollover(self):
        self.bus.readback_override={2:0,3:0,4:0,5:1,6:1,7:0x03}
        self.command(); self.feed(b'+TIME:Sun Feb 28 23:59:59 2027 +0000 09:00\r\n')
        self.assertEqual(self.word(8),2); self.assert_safe()
    def test_timeout_mid_calendar_write_reports_partial_write(self):
        self.bus.stuck_at=205; self.command(); self.feed()
        self.assertEqual(self.word(8),7); self.assertEqual(self.word(20),7)
        self.assertGreater(self.word(56),0); self.assertLess(self.word(56),7); self.assert_safe()
    def test_image_bounds(self):
        h=IntelHex(str(HEX)); self.assertEqual(h.minaddr(),0x08000000); self.assertLess(h.maxaddr(),0x08008000)

if __name__=='__main__': unittest.main()
