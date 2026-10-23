"""Native RC6A cleanup and exact RC6 waveform equivalence checks."""
import unittest
from test_rc6_motor_guard import Tests as RC6
from unicorn import UC_HOOK_CODE


class Tests(RC6):
    artifact=RC6.artifact.parent.parent.parent/'release_candidate_rc6a/build/MM32SPIN05PF_CLEAN_RC6A_20261021.axf'
    signature=0x4d50526a

    def setword(self,name,index,value):
        if name=='rtc_release_edge':
            # Historical shortcut fixtures seed the removed coarse-runtime
            # fallback's counter. TIM3 runtime never reads it in RC6A.
            self.assertEqual((index,value),(0,0))
            return
        super().setword(name,index,value)

    def test_cleanup_control_addresses_and_interval_cache(self):
        self.assertEqual(self.symbols['minute_log']+188*4,0x20000534)
        self.assertEqual(self.symbols['minute_log']+189*4,0x20000538)
        for mode in range(4):
            for rate in (50000,62500,63108,75000):
                self.setUp();self.setword('rtc_pace',1,rate-1)
                self.setword('release_state',1,1023);self.mode_run(mode)
                numerator=self.word('release_state',3)
                denominator=self.word('release_state',4)
                self.assertEqual(self.word('seconds_log',216),numerator//denominator)
                self.assertEqual(self.word('seconds_log',217),numerator%denominator)

    def test_cleanup_exact_rc6_rise_fall_sequence(self):
        RC6.setUpClass()
        for mode in range(4):
            for rate in (62500,63108):
                with self.subTest(mode=mode,rate=rate):
                    baseline=RC6();baseline.setUp();self.setUp()
                    for t in (baseline,self):
                        t.setword('rtc_pace',1,rate-1)
                        t.setword('release_state',1,230)
                        t.mode_run(mode)
                        t.setword('request_pulses',0,6)
                        t.call('fine_minutes_rise',t.counter)
                        t.advance_timer(t.word('minute_log',181)*128)
                    self.assertEqual(self.edges,baseline.edges)
                    self.assertEqual(self.get(3),0)

    def test_cleanup_seconds_rise_uses_fewer_instructions(self):
        RC6.setUpClass();measurements=[]
        for cls in (RC6,type(self)):
            t=cls();t.setUp();t.mode_run(3)
            t.advance_timer((t.reg(0x38)-t.counter)&65535)
            count=[0]
            def code(cpu,address,size,user):count[0]+=1
            hook=t.cpu.hook_add(UC_HOOK_CODE,code)
            t.cpu.ctl_remove_cache(0x08000000,0x08008000)
            t.advance_timer((t.reg(0x34)-t.counter)&65535)
            t.cpu.hook_del(hook);measurements.append(count[0])
            self.assertEqual(t.get(3),0)
        print('Seconds-rise instruction count RC6/RC6A:',measurements,flush=True)
        self.assertLess(measurements[1],measurements[0])

    def test_cleanup_daily_poll_avoids_unused_calendar_conversion(self):
        RC6.setUpClass();measurements=[]
        for cls in (RC6,type(self)):
            t=cls();t.setUp();t.mode_run(3)
            t.setword('daily_log',12,1);t.setword('daily_log',0,1)
            t.setword('daily_log',3,t.word('seconds_log',227)+3600)
            instructions=[0];conversions=[0]
            stamp=t.symbols['rtc_motion_stamp']&~1
            def code(cpu,address,size,user):
                instructions[0]+=1
                if address==stamp:conversions[0]+=1
            hook=t.cpu.hook_add(UC_HOOK_CODE,code)
            t.cpu.ctl_remove_cache(0x08000000,0x08008000)
            t.call('daily_poll');t.cpu.hook_del(hook)
            measurements.append((instructions[0],conversions[0]))
            self.assertEqual(t.get(3),0)
        print('Quiet daily poll (instructions,calendar conversions) RC6/RC6A:',measurements,flush=True)
        self.assertEqual((measurements[0][1],measurements[1][1]),(1,0))
        self.assertLess(measurements[1][0],measurements[0][0])

    def test_cleanup_sampled_stack_headroom(self):
        from unicorn.arm_const import UC_ARM_REG_SP
        depths=[]
        for phase in ('calendar','motor','uart'):
            self.setUp();lowest=[0x20000ff8]
            def code(cpu,address,size,user):
                lowest[0]=min(lowest[0],cpu.reg_read(UC_ARM_REG_SP))
            hook=self.cpu.hook_add(UC_HOOK_CODE,code)
            self.cpu.ctl_remove_cache(0x08000000,0x08008000)
            if phase=='calendar':self.window_seed()
            elif phase=='motor':
                self.mode_run(3)
                for _ in range(64):self.tick()
            else:self.call('UART2_Handler')
            self.cpu.hook_del(hook);depths.append(0x20000ff8-lowest[0])
        required=sum(depths)+64
        available=0x20000ff8-self.ram_end
        print('Sampled calendar/motor/UART stack depths, sum+frames, available:',
              depths,required,available,flush=True)
        self.assertLess(required,available)


if __name__=='__main__':unittest.main()
