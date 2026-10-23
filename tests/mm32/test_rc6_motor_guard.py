"""RC6 guard tests and inherited movement regressions, existing native ELF.

The harness models PendSV and lets close compares occur before a deferred
tick. Borrowed timer cycles are deducted before the next scheduled SysTick.
Hardware CPU execution duration is tested explicitly, not assumed by Unicorn.
"""
import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.analysis_deps'))
from elftools.elf.elffile import ELFFile
from intelhex import IntelHex
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0
from test_release_candidate_build import Tests as Prior


class Tests(Prior):
    artifact=ROOT/'mm32_port/release_candidate_rc6/build/MM32SPIN05PF_MOTOR_GUARD_RC6_20261020.axf'
    signature=0x4d505206

    @classmethod
    def setUpClass(cls):
        delivered=IntelHex(str(cls.artifact.with_suffix('.hex')))
        with cls.artifact.open('rb') as f:
            elf=ELFFile(f)
            for segment in elf.iter_segments():
                if segment['p_type']=='PT_LOAD' and 0x08000000<=segment['p_paddr']<0x08008000:
                    assert all(delivered[segment['p_paddr']+i]==b for i,b in enumerate(segment.data()))
            cls.loads=[(s['p_vaddr'],s.data(),s['p_memsz']) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
            cls.symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
            cls.ram_end=max(s['sh_addr']+s['sh_size'] for s in elf.iter_sections()
                           if s['sh_flags']&2 and 0x20000000<=s['sh_addr']<0x20001000)
        cls.symbols['scan_log']=cls.symbols['parallel_log']
        cls.symbols['release_state']=cls.symbols['seconds_log']+228*4
        for offset,name in enumerate(('manual_web_active','manual_web_deadline','manual_web_tick_seen')):
            cls.symbols[name]=cls.symbols['minute_log']+(217+offset)*4
        cls.prepare_sleep_model()

    def setUp(self):
        self.pendsv=False
        self.borrowed_cycles=0
        super().setUp()
        def icsr(cpu,access,address,size,value,user):
            if value&(1<<28):self.pendsv=True
            if value&(1<<27):self.pendsv=False
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,icsr,begin=0xe000ed04,end=0xe000ed04)
        self.cpu.mem_write(0xe000ed04,b'\0'*4)

    def call(self,name,*args):
        super().call(name,*args)
        if self.pendsv and name!='PendSV_Handler':
            self.pendsv=False
            self.cpu.mem_write(0xe000ed04,b'\0'*4)
            super().call('PendSV_Handler')

    def tick(self,high=0):
        self.seconds_input=high
        self.cpu.mem_write(0x48000408,struct.pack('<I',high<<14))
        cycles=self.word('rtc_pace',1)+1-self.borrowed_cycles
        self.borrowed_cycles=0
        if self.reg(0)&1:
            self.remainder+=max(cycles,0)
            counts,self.remainder=divmod(self.remainder,self.reg(0x28)+1)
            self.advance_timer(counts)
        self.call('SysTick_Handler')
        # A pending tick waits for an actual enabled motor edge, not an
        # immediate busy retry. The next SysTick stays on its original grid.
        for _ in range(8):
            if not self.word('seconds_log',214):return
            enabled=self.reg(0x0c)&30
            self.assertTrue(enabled)
            delta=min(((self.reg(0x34+4*i)-self.counter)&65535) or 65536
                      for i in range(4) if enabled&(2<<i))
            self.borrowed_cycles+=delta*(self.reg(0x28)+1)
            self.advance_timer(delta)
        self.fail('deferred tick did not find a safe gap')

    def test_guard_vectors_priority_and_stable_ram_controls(self):
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x08000038,4))[0],self.symbols['PendSV_Handler'])
        self.assertEqual(self.symbols['minute_log']+188*4,0x20000534)
        self.mode_run(3)
        shpr=struct.unpack('<I',self.cpu.mem_read(0xe000ed20,4))[0]
        self.assertEqual(shpr>>16,0x8080)
        self.assertEqual(self.reg(0x28),127)

    def test_guard_each_compare_defers_tick_without_moving_edge(self):
        for mode in range(4):
            for channel in range(4):
                for to_edge in (1,40,120):
                    with self.subTest(mode=mode,channel=channel,to_edge=to_edge):
                        self.setUp();self.mode_run(mode)
                        if channel>=2:
                            self.setword('request_pulses',0,6)
                            self.call('fine_minutes_rise',self.counter)
                        enabled=self.reg(0x0c)
                        self.reg(0x0c,2<<channel)
                        due=self.reg(0x34+4*channel)
                        self.counter=(due-to_edge)&65535
                        self.sr=0
                        before=self.get(4);self.edges.clear()
                        self.call('SysTick_Handler')
                        self.assertEqual(self.get(4),before)
                        self.assertEqual(self.word('seconds_log',214),1)
                        start=self.timer_time
                        self.advance_timer(to_edge)
                        self.assertTrue(self.edges)
                        self.assertEqual(self.edges[0][0],start+to_edge)
                        self.assertEqual(self.word('seconds_log',214),0)
                        self.assertEqual(self.get(4),before+1)
                        self.assertEqual(self.get(3),0)

    def test_guard_far_compare_executes_tick_immediately(self):
        self.mode_run(3)
        self.reg(0x0c,4)
        self.counter=(self.reg(0x38)-200)&65535;self.sr=0
        before=self.get(4)
        self.call('SysTick_Handler')
        self.assertEqual(self.get(4),before+1)
        self.assertEqual(self.word('seconds_log',214),0)

    def test_guard_due_flag_and_counter_wrap(self):
        self.mode_run(3)
        self.reg(0x0c,4);self.reg(0x38,20);self.counter=65530;self.sr=0
        before=self.get(4);self.call('SysTick_Handler')
        self.assertEqual(self.get(4),before)
        self.advance_timer(26)
        self.assertEqual(self.get(4),before+1)
        self.assertEqual(self.get(3),0)
        self.setword('second_active',0,1)
        self.reg(0x0c,4);self.reg(0x38,self.counter);self.sr=4
        before=self.get(4);self.call('SysTick_Handler')
        self.assertEqual(self.get(4),before)
        self.call('TIM3_Handler')
        self.assertEqual(self.get(4),before+1)

    def test_guard_timer_stop_releases_deferred_tick(self):
        self.mode_run(3)
        self.reg(0x0c,4);self.counter=(self.reg(0x38)-1)&65535;self.sr=0
        before=self.get(4);self.call('SysTick_Handler')
        self.assertEqual(self.get(4),before)
        self.call('fine_stop')
        self.assertEqual(self.get(4),before+1)
        self.assertEqual(self.word('seconds_log',214),0)

    def test_guard_backlog_fault_is_latched(self):
        self.mode_run(3)
        self.reg(0x0c,4);self.counter=(self.reg(0x38)-1)&65535;self.sr=0
        self.call('SysTick_Handler');self.call('SysTick_Handler')
        self.assertEqual((self.get(2),self.get(3)),(6,10))
        self.assertEqual(self.reg(0x0c),0)

    def test_guard_overrun_cannot_silently_delay_motor(self):
        self.mode_run(3)
        self.reg(0x0c,4);self.counter=(self.reg(0x38)-500)&65535;self.sr=0
        fired=[]
        def slow(cpu,address,size,user):
            if address==(self.symbols['clock_tick_body']&~1) and not fired:
                fired.append(1);self.counter=(self.counter+150)&65535
        hook=self.cpu.hook_add(UC_HOOK_CODE,slow)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        self.call('SysTick_Handler');self.cpu.hook_del(hook)
        self.assertTrue(fired)
        self.assertEqual((self.get(2),self.get(3)),(6,10))
        self.assertEqual(self.reg(0x0c),0)


if __name__=='__main__':unittest.main()
