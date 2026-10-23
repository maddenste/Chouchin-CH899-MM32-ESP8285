"""RC6J focused tests with a counter advancing DURING actual I2C code.
Instruction-derived time is a model, not measured silicon execution time.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.analysis_deps'))
from check_rc6i_quartz import Tests as Prior
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6j/build/MM32SPIN05PF_QUARTZ_REFERENCE_RC6J_20261021.axf'
    signature=0x4d505273

    @staticmethod
    def advancing_read(t,delay=0):
        t.start_counter()
        cycles=[0];samples=[]
        original=t.bus.tx_level
        def tx():
            if t.bus.index==0 and t.bus.bits==0 and t.bus.pointer==14:
                if samples and delay:
                    cycles[0]+=delay
                count=255-(cycles[0]*4096//8000000)%255
                t.bus.data[15]=count
                samples.append((cycles[0],count))
            original()
        t.bus.tx_level=tx
        # Deliberately conservative lower-bound one cycle per instruction.
        # Old implementation fails even before real M0 memory/branch costs.
        def code(*args):cycles[0]+=1
        def counter(cpu,access,address,size,value,user):
            cpu.mem_write(address,(cycles[0]&0xffffffff).to_bytes(4,'little'))
        a=t.cpu.hook_add(UC_HOOK_CODE,code)
        b=t.cpu.hook_add(UC_HOOK_MEM_READ,counter,begin=0x40000024,end=0x40000024)
        t.cpu.ctl_remove_cache(0x08000000,0x08008000)
        try:
            t.call('rtc_counter_read',0x20000f80)
            result=t.cpu.reg_read(UC_ARM_REG_R0)
        finally:
            t.cpu.hook_del(a);t.cpu.hook_del(b)
            t.bus.tx_level=original
        return result,samples,cycles[0]

    def test_old_build_reproduces_false_rejection_with_moving_counter(self):
        Prior.setUpClass();old=Prior();old.setUp()
        result,samples,total=self.advancing_read(old)
        self.assertEqual(result,0)
        self.assertEqual(old.word('wifi_rtc',5),0)
        delta=(samples[0][1]+255-samples[1][1])%255
        self.assertGreater(delta,24)
        print('RC6I reproduced: pair instructions',samples[1][0]-samples[0][0],
              'counter delta',delta,'limit24')

    def test_new_build_accepts_counter_advancing_during_i2c(self):
        result,samples,total=self.advancing_read(self)
        self.assertEqual(result,1)
        self.assertNotEqual(samples[0][1],samples[1][1])
        self.assertEqual(self.q(31),0)
        self.assertEqual(self.q(25),0)
        self.assertLess(total,40000)
        print('RC6J: total instructions',total,'pair delta',self.q(32),'expected',self.q(33))

    def test_timestamped_pair_accepts_valid_interrupt_delay_over_old_limit(self):
        result,samples,total=self.advancing_read(self,delay=64000)
        self.assertEqual(result,1)
        self.assertGreater(self.q(32),24)
        self.assertEqual(self.q(31),0)

if __name__=='__main__':
    names=['test_old_build_reproduces_false_rejection_with_moving_counter',
           'test_new_build_accepts_counter_advancing_during_i2c',
           'test_timestamped_pair_accepts_valid_interrupt_delay_over_old_limit',
           'test_counter_driver_preserves_calendar_alarm_clkout_and_pauses',
           'test_foreign_timer_interrupt_is_not_taken_over',
           'test_rate_calibration_reload_wrap_and_motor_unchanged',
           'test_clock_rates_and_fractional_precision',
           'test_bad_reads_and_long_gap_fall_back_without_stopping_motor',
           'test_calendar_set_pauses_counter_and_reseeds',
           'test_poll_uses_actual_i2c_counter_and_tim2_without_touching_tim3',
           'test_shared_grid_four_modes']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
