"""Trial62 plus ordinary CPU Sleep and RAM duty-cycle telemetry."""
import unittest
import struct
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PRIMASK, UC_ARM_REG_PC
import test_trial62_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_SLEEP_DIAGNOSTIC_TRIAL63_20261010.axf')
    signature=0x4d503633
    defines=prior.Tests.defines+['-DCPU_SLEEP_DIAG']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prepare_sleep_model()

    @classmethod
    def prepare_sleep_model(cls):
        # WFI halts Unicorn's core permanently without a real interrupt
        # controller. Replace ONLY the diagnostic WFI in emulator memory;
        # the exported HEX/ELF retains the genuine instruction.
        address=cls.symbols['sleep_diag_idle']&~1
        cls.sleep_wfi=None
        for base,data,size in cls.loads:
            if base<=address<base+len(data):
                offset=data.index(b'\x30\xbf',address-base)
                cls.sleep_wfi=base+offset
                changed=data[:offset]+b'\x00\xbf'+data[offset+2:]
                cls.loads=[(a,changed if a==base else d,n) for a,d,n in cls.loads]
                break
        assert cls.sleep_wfi is not None

    def setUp(self):
        super().setUp()
        # Unicorn has no physical interrupt-driven WFI wake. Its startup
        # instruction budget can stop inside masked sleep; synthetic calls
        # begin in ordinary unmasked thread context instead.
        self.cpu.reg_write(UC_ARM_REG_PRIMASK,0)

    def idle(self, epoch=None, before=50000, after=45000, wrap=False):
        self.cpu.mem_write(0xe000e014,struct.pack('<I',62499))
        self.cpu.mem_write(0xe000e018,struct.pack('<I',before))
        self.cpu.mem_write(0xe000ed04,struct.pack('<I',0))
        self.cpu.mem_write(0xe000e200,struct.pack('<I',0))
        wakes=[]
        def wake(cpu,address,size,user):
            if address==self.sleep_wfi:
                wakes.append(cpu.reg_read(UC_ARM_REG_PRIMASK))
                cpu.mem_write(0xe000e018,struct.pack('<I',after))
                cpu.mem_write(0xe000ed04,struct.pack('<I',(1<<26) if wrap else 0))
                # Supply a synthetic wake; Unicorn otherwise stops at WFI.
                cpu.reg_write(UC_ARM_REG_PC,(address+size)|1)
        hook=self.cpu.hook_add(UC_HOOK_CODE,wake)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        self.cpu.reg_write(UC_ARM_REG_R0,self.word('seconds_log',213) if epoch is None else epoch)
        try: self.call('sleep_diag_idle')
        finally: self.cpu.hook_del(hook)
        return wakes

    def test_sleep_wait_measurement_excludes_irq_dispatch(self):
        before=self.word('seconds_log',216)
        self.assertEqual(self.idle(),[1])
        self.assertEqual(self.word('seconds_log',216)-before,5000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0xe000ed10,4))[0]&6,0)

    def test_sleep_boundary_elapsed_and_64bit_carry(self):
        self.setword('seconds_log',216,0xfffffff0)
        self.setword('seconds_log',217,2)
        self.assertEqual(self.idle(before=100,after=62000,wrap=True),[1])
        self.assertEqual(self.word('seconds_log',216),584)
        self.assertEqual(self.word('seconds_log',217),3)

    def test_sleep_serviced_irq_race_repolls_without_wait(self):
        self.assertEqual(self.idle(epoch=(self.word('seconds_log',213)-1)&0xffffffff),[])

    def test_sleep_disabled_and_masked_caller_never_wait(self):
        self.setword('seconds_log',212,0)
        self.assertEqual(self.idle(),[])
        self.setword('seconds_log',212,1)
        self.cpu.reg_write(UC_ARM_REG_PRIMASK,1)
        self.assertEqual(self.idle(),[])
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),1)

    def test_sleep_percentage_large_overnight_counters(self):
        total=8*3600*8000000
        waited=total*93//100
        for index,value in ((216,waited),(218,total)):
            self.setword('seconds_log',index,value&0xffffffff)
            self.setword('seconds_log',index+1,value>>32)
        self.idle()
        self.assertEqual(self.word('seconds_log',220),9300)

    def test_sleep_pending_interrupt_repolls_and_preserves_masks(self):
        for address,value in ((0xe000ed04,1<<26),(0xe000e200,1<<28)):
            self.setUp()
            self.cpu.mem_write(address,struct.pack('<I',value))
            old=self.word('seconds_log',214)
            self.call('sleep_diag_idle',self.word('seconds_log',213))
            self.assertEqual(self.word('seconds_log',214),old)
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),0)

    def test_sleep_tick_accounting_and_uart_generations(self):
        epoch=self.word('seconds_log',213)
        before=self.word('seconds_log',218)
        self.cpu.mem_write(0xe000e014,struct.pack('<I',62499))
        self.tick()
        self.assertEqual(self.word('seconds_log',218)-before,62500)
        self.assertEqual(self.word('seconds_log',213),epoch+1)
        self.cpu.mem_write(0x40004408,struct.pack('<I',0))
        self.call('UART2_Handler')
        self.assertEqual(self.word('seconds_log',213),epoch+2)

    def test_sleep_rollover_before_start_sample_is_not_false_sleep(self):
        self.cpu.mem_write(0xe000ed04,struct.pack('<I',0))
        self.cpu.mem_write(0xe000e200,struct.pack('<I',0))
        old=self.word('seconds_log',214)
        def pending(cpu,access,address,size,value,user):
            cpu.mem_write(0xe000ed04,struct.pack('<I',1<<26))
        hook=self.cpu.hook_add(UC_HOOK_MEM_READ,pending,begin=0xe000e018,end=0xe000e018)
        try: self.call('sleep_diag_idle',self.word('seconds_log',213))
        finally: self.cpu.hook_del(hook)
        self.assertEqual(self.word('seconds_log',214),old)

    def test_sleep_counters_do_not_overlap_homing_or_release_data(self):
        self.assertEqual(self.ram_end,0x20000c00)
        self.assertTrue(self.word('seconds_log',212))
        self.running()
        self.assertTrue(self.word('seconds_log',212))
        self.assertEqual(self.get(3),0)

if __name__=='__main__': unittest.main()
