"""Compiled concurrent homing, legacy clock seed and edge-gated release."""
import struct
import subprocess
import unittest
import test_reference_scan_build as ref


class ParallelTests(unittest.TestCase):
    artifact=ref.ROOT/'build/MM32SPIN05PF_PARALLEL_HOME_TRIAL22_20261007.axf'
    signature=0x4D503232
    get=ref.ReferenceScanTests.get
    put=ref.ReferenceScanTests.put
    tick=ref.ReferenceScanTests.tick
    test_vectors_size_boot_and_idle=ref.ReferenceScanTests.test_vectors_size_boot_and_idle

    @classmethod
    def setUpClass(cls):
        result=subprocess.run([str(ref.COMPILER),'--target=arm-arm-none-eabi',
            '-mcpu=cortex-m0','-mthumb','-std=gnu11','-O2','-Wall','-Wextra','-Werror',
            '-DMM32_REFERENCE_SCAN','-DMM32_VARIABLE_CYCLES','-DMAX_CYCLES=6u',
            *getattr(cls,'defines',[]),
            '-Wl,--scatter=mm32spin05.sct','-Wl,--entry=Reset_Handler','startup.c',
            *getattr(cls,'component_sources',['parallel_home_main.c','parallel_minute_component.c',
            'parallel_seconds_component.c','motor_scan_probe.c','../mm32_uart.c']),
            *getattr(cls,'extra_sources',[]),
            '-o',str(cls.artifact)],cwd=getattr(cls,'source_dir',ref.ROOT/'target'),capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        subprocess.run([str(ref.COMPILER.with_name('fromelf.exe')),'--i32',
            f'--output={cls.artifact.with_suffix(".hex")}',str(cls.artifact)],check=True)
        with cls.artifact.open('rb') as f:
            elf=ref.ELFFile(f)
            cls.loads=[(s['p_vaddr'],s.data(),s['p_memsz']) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
            cls.symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
            cls.ram_end=max(s['sh_addr']+s['sh_size'] for s in elf.iter_sections()
                if s['sh_flags']&2 and 0x20000000<=s['sh_addr']<0x20001000)
        cls.symbols['scan_log']=cls.symbols['parallel_log']
        print(cls.artifact.stem,'command',hex(cls.symbols['parallel_log']+4),'RAM end',hex(cls.ram_end))

    def setUp(self):
        ref.ReferenceScanTests.setUp(self)
        # Main polls UART instead of WFI; boot instruction cutoff may be inside
        # that call. Invoke ISR tests from a fixed thread stack, not mid-call.
        self.cpu.reg_write(ref.UC_ARM_REG_SP,0x20000FF8)
        self.cpu.mem_map(0x40004000,0x1000)

    def word(self,name,index=0):
        return struct.unpack('<I',self.cpu.mem_read(self.symbols[name]+4*index,4))[0]

    def call(self,name):
        self.cpu.reg_write(ref.UC_ARM_REG_LR,0x08007001)
        self.cpu.emu_start(self.symbols[name],0x08007000,count=3000)

    def seed(self,seconds=23):
        for b in f'+TIME:Wed Oct  7 23:45:{seconds:02} 2026 +0100 09:00\r\n'.encode():
            self.cpu.mem_write(0x40004408,struct.pack('<I',2))
            self.cpu.mem_write(0x40004404,struct.pack('<I',b))
            self.call('parallel_poll_once')
        self.assertEqual(self.get(6),1)

    def home(self,minute_entry=13,seconds_entry=246,seed=True):
        self.put(1,1); self.tick()
        if seed: self.seed()
        overlap=False
        for _ in range(40000):
            high=0
            if self.get(19)==1:
                high=int(seconds_entry<=self.word('seconds_log',5)+1<=seconds_entry+16)
            elif self.get(19)==2:
                high=int(self.word('minute_log',5)+1>=minute_entry)
            self.tick(high)
            overlap |= bool(self.output&6 and (self.output&1 or self.a_output&128))
            if self.get(2) in (4,6): return overlap
        self.fail('no homing termination')

    @property
    def a_output(self):
        level=0
        for a,v in self.writes[-80:]:
            if a==0x48000010: level=(level|(v&65535))&~(v>>16)
        return level

    def released(self):
        self.assertEqual(self.output&(7|(1<<13)|(1<<15)),0)
        self.assertEqual(self.a_output&128,0)

    def test_seconds_first_park_and_release_only_new_00(self):
        self.assertTrue(self.home(minute_entry=100))
        self.assertEqual((self.get(7),self.get(8),self.get(3)),(1,1,0))
        self.assertLess(self.get(10),self.get(11))
        before=self.get(21); self.released()
        self.put(5,59); self.put(14,120)
        for _ in range(7):
            self.tick(); self.assertEqual(self.get(2),4); self.released()
        self.tick()
        self.assertEqual((self.get(2),self.get(5),self.get(14)),(7,0,0))
        self.assertEqual(self.get(21),before)
        for _ in range(23050):
            self.tick()
            if self.get(2) in (5,6): break
        self.assertEqual((self.get(2),self.get(3),self.get(12),self.get(13)),(5,0,2880,18))
        self.released()

    def test_minutes_first_and_stale_00_waits(self):
        self.assertTrue(self.home(seconds_entry=900))
        self.assertLess(self.get(11),self.get(10))
        self.put(5,0); self.put(14,0)
        for _ in range(128): self.tick()
        self.assertEqual(self.get(2),4)
        self.assertEqual(self.get(5),1)
        self.released()

    def test_missing_seconds_fails_safe(self):
        self.home(seconds_entry=2000)
        self.assertEqual((self.get(2),self.get(3)),(6,5)); self.released()

    def test_missing_minutes_fails_safe(self):
        self.home(minute_entry=2000)
        self.assertEqual((self.get(2),self.get(3)),(6,4)); self.released()

    def test_no_time_never_releases(self):
        self.home(seed=False)
        self.assertEqual(self.get(2),4)
        self.put(4,15359); self.tick()
        self.assertEqual((self.get(2),self.get(3)),(6,6)); self.released()

    def test_abort_and_exception(self):
        for exception in (False,True):
            self.setUp(); self.put(1,1); self.tick()
            for _ in range(12): self.tick()
            if exception: self.call('Default_Handler')
            else: self.put(1,0); self.tick()
            self.assertEqual((self.get(2),self.get(3)),(6,3 if exception else 2))
            self.released()

    def test_stack_margin(self): self.assertLessEqual(self.ram_end,0x20000C00)

    def test_initially_high_sensors_must_leave_and_reenter(self):
        self.put(1,1); self.tick(); self.seed()
        for _ in range(40000):
            high=0
            if self.get(19)==1:
                pulse=self.word('seconds_log',5)+1
                high=int(pulse<=16 or 961<=pulse<=977)
            elif self.get(19)==2:
                request=self.word('minute_log',5)+1
                high=int(request<=9 or 721<=request<=729)
            self.tick(high)
            if self.get(2) in (4,6): break
        self.assertEqual((self.get(2),self.get(3),self.get(7),self.get(8)),(4,0,1,1))
        self.assertGreaterEqual(self.word('seconds_log',240),962)
        self.assertEqual(self.word('minute_log',243),721)
        self.released()

    def test_stuck_high_never_claims_alignment(self):
        self.put(1,1); self.tick(); self.seed()
        for _ in range(9000):
            self.tick(1)
            if self.get(2)==6: break
        self.assertEqual((self.get(2),self.get(7),self.get(8)),(6,0,0))
        self.released()

    def test_completion_at_00_does_not_release_in_same_isr(self):
        self.home(minute_entry=100)
        # Both aligned: returning from homing cannot flow into a runtime pulse.
        self.assertEqual(self.get(9),0)
        self.put(5,59); self.put(14,127)
        self.tick()
        self.assertEqual((self.get(2),self.get(9)),(7,self.get(4)))
        self.assertEqual(self.get(12),0)

    def test_user_request_and_bad_time_no_clock(self):
        self.put(1,1); self.tick()
        self.put(4,256)
        emitted=[]
        for _ in range(5):
            self.cpu.mem_write(0x40004408,struct.pack('<I',1))
            before=len(self.writes); self.call('parallel_poll_once')
            emitted.extend(v for a,v in self.writes[before:] if a==0x40004400)
        self.assertEqual(bytes(emitted),b'USER\n')
        for b in b'USER_OK\r\n+TIME:bad\r\n':
            self.cpu.mem_write(0x40004408,struct.pack('<I',2))
            self.cpu.mem_write(0x40004404,struct.pack('<I',b))
            self.call('parallel_poll_once')
        self.assertEqual(self.get(6),0)


if __name__=='__main__': unittest.main()
