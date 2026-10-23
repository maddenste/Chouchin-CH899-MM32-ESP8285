"""RTC quiet intervals, continuous timer time, genuine bit-banged reads."""
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC
import test_trial64_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_RTC_SYNC_SLEEP_TRIAL65_20261010.axf')
    signature=0x4d503635
    defines=prior.Tests.defines+['-DRTC_SYNC_WINDOWS']

    def fixture_clock(self):
        # Historical helpers shortcut startup. Seed the new projected clock
        # from their actual RTC model as real acquisition would do.
        self.call('rtc_motion_stamp')
        stamp=self.cpu.reg_read(UC_ARM_REG_R0)
        stamp=stamp//86400*86400+self.get(16)*3600+self.get(15)*60+self.get(5)
        self.setword('seconds_log',227,stamp)
        tick=self.get(4)-1
        self.setword('rtc_edge_tick',0,tick)
        self.setword('seconds_log',221,tick+992)
        self.setword('seconds_log',223,2)
        self.setword('seconds_log',224,tick)
        self.setword('seconds_log',225,self.get(16)*3600+self.get(15)*60+self.get(5))
        self.setword('seconds_log',226,1)
        self.setword('rtc_window_cycles',0,self.word('rtc_pace',0)-(self.word('rtc_pace',1)+1))

    def fine_run(self):
        super().fine_run()
        self.put(5,0); self.put(15,45); self.put(16,11)
        self.fixture_clock()

    def night_run(self,*args,**kwargs):
        super().night_run(*args,**kwargs); self.fixture_clock()

    def mode_run(self,mode):
        super().mode_run(mode); self.fixture_clock()

    def rtc_poll(self):
        self.call('parallel_poll_once')

    def hold(self,mask,ticks=388,poll=True):
        self.pressed=mask
        sod=self.get(16)*3600+self.get(15)*60+self.get(5)
        phase=(self.get(4)-self.word('rtc_edge_tick',0))%128
        for i in range(ticks):
            now=(sod+(phase+i+1)//128)%86400
            self.rtc_time(now//3600,now//60%60,now%60)
            self.tick()
            if poll and (i%4==0 or i==ticks-1): self.call('parallel_poll_once')

    def window_seed(self):
        self.running()
        self.rtc_time(11,45,0)
        self.setword('rtc_clock_seeded',0,0)
        self.setword('seconds_log',223,0)
        self.call('parallel_poll_once')

    def test_window_duplicate_does_not_stop_civil_clock(self):
        self.window_seed()
        for _ in range(128): self.tick()
        self.call('parallel_poll_once')
        self.assertEqual((self.get(5),self.get(3)),(1,0))

    def test_window_no_reads_in_quiet_interval(self):
        self.window_seed()
        for _ in range(128): self.tick()
        self.rtc_time(11,45,1); self.call('parallel_poll_once')
        self.assertEqual(self.word('seconds_log',223),2)
        reads=self.word('rtc_pace',5)
        for _ in range(128*7):
            self.tick(); self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',5),reads)
        self.assertEqual((self.get(5),self.get(3)),(8,0))

    def test_window_frozen_rtc_is_bounded(self):
        self.window_seed()
        for _ in range(194): self.tick()
        self.call('parallel_poll_once')
        self.assertNotEqual(self.get(3),0)

    def test_window_interrupt_during_actual_read_then_sleep(self):
        self.window_seed(); self.setword('minute_log',211,0)
        for _ in range(4): self.tick()
        count=[0]; interrupted=[False]
        def inject(cpu,address,size,user):
            count[0]+=1
            if count[0]==62500:
                interrupted[0]=True
                # A serviced interrupt during real I2C; emulate its effects
                # without recursively entering Unicorn from its code hook.
                self.put(4,self.get(4)+1)
                self.setword('seconds_log',213,self.word('seconds_log',213)+1)
        epoch=self.word('seconds_log',213)
        hook=self.cpu.hook_add(UC_HOOK_CODE,inject)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        try: self.call('parallel_poll_once')
        finally: self.cpu.hook_del(hook)
        self.assertTrue(interrupted[0])
        self.assertEqual(self.idle(epoch=epoch),[])
        reads=self.word('rtc_pace',5)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',5),reads)
        self.assertEqual(self.idle(),[1])

    def test_window_real_systick_handler_mid_i2c_then_sleep(self):
        self.window_seed(); self.setword('minute_log',211,0)
        for _ in range(4): self.tick()
        count=[0]
        def suspend(cpu,address,size,user):
            count[0]+=1
            if count[0]==62500: cpu.emu_stop()
        hook=self.cpu.hook_add(UC_HOOK_CODE,suspend)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        self.call('parallel_poll_once')
        self.cpu.hook_del(hook)
        self.assertEqual(count[0],62500)
        context=self.cpu.context_save()
        # Execute the real compiled timer/SysTick paths while I2C is stopped,
        # then resume its saved thread registers. SRAM/peripherals persist.
        self.advance_timer((self.word('rtc_pace',1)+1)//128)
        self.call('SysTick_Handler')
        self.cpu.context_restore(context)
        self.cpu.emu_start(self.cpu.reg_read(UC_ARM_REG_PC)|1,0x08007000,count=2000000)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('rtc_poll_tick',0),self.get(4))
        reads=self.word('rtc_pace',5); self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',5),reads)
        self.assertEqual(self.idle(),[1])

    def test_window_calibration_requires_second_observation(self):
        self.window_seed()
        for _ in range(128): self.tick()
        self.rtc_time(11,45,1); self.call('parallel_poll_once')
        for _ in range(992): self.tick()
        self.rtc_time(11,45,8); self.call('parallel_poll_once')
        self.assertEqual(self.word('seconds_log',223),3)
        self.assertEqual(self.word('rtc_pace',4),0)
        for _ in range(32): self.tick()
        self.rtc_time(11,45,9); self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',4),1)
        self.assertEqual(self.word('rtc_pace',1),62499)

    def test_window_calendar_jump_is_rejected(self):
        self.window_seed()
        for _ in range(4): self.tick()
        self.bus.data[5]=0x11
        self.call('parallel_poll_once')
        self.assertEqual(self.get(3),9)

    def test_window_fractional_calibration_across_cycle_counter_wrap(self):
        self.window_seed()
        for _ in range(128): self.tick()
        self.rtc_time(11,45,1); self.call('parallel_poll_once')
        anchor=0xffff0000
        self.setword('rtc_window_cycles',0,anchor)
        self.setword('rtc_pace',0,anchor)
        for _ in range(992): self.tick()
        self.rtc_time(11,45,8); self.call('parallel_poll_once')
        for _ in range(32): self.tick()
        self.setword('rtc_pace',0,(anchor+1024*62500+1000)&0xffffffff)
        self.rtc_time(11,45,9); self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',1),62499)
        self.assertEqual(self.word('release_state',1),1000)
        self.assertEqual(self.get(3),0)

    def test_window_tick_wrap_keeps_quiet_deadline_and_clock(self):
        self.window_seed()
        self.put(4,0xffffff80)
        self.setword('rtc_edge_tick',0,0xffffff80)
        self.setword('seconds_log',223,2)
        self.setword('seconds_log',221,0x100)
        reads=self.word('rtc_pace',5)
        for _ in range(128): self.tick(); self.call('parallel_poll_once')
        self.assertEqual(self.get(4),0)
        self.assertEqual(self.word('rtc_pace',5),reads)
        self.assertEqual((self.get(5),self.get(3)),(1,0))

    def test_window_midnight_uses_real_calendar_rollover(self):
        self.window_seed()
        stamp=self.word('seconds_log',227)//86400*86400+86399
        self.setword('seconds_log',227,stamp)
        self.setword('rtc_last',0,86399)
        self.put(16,23); self.put(15,59); self.put(5,59)
        self.rtc_time(23,59,59)
        for _ in range(128): self.tick()
        old=self.bus.data[5]
        day=(old>>4)*10+(old&15)+1
        self.bus.data[5]=(day//10)*16+day%10
        self.rtc_time(0,0,0); self.call('parallel_poll_once')
        self.assertEqual(self.word('seconds_log',227),stamp+1)
        self.assertEqual((self.get(16),self.get(15),self.get(5),self.get(3)),(0,0,0,0))

    def test_window_daily_deadline_fires_during_quiet_interval(self):
        self.window_seed()
        for _ in range(128): self.tick()
        self.rtc_time(11,45,1); self.call('parallel_poll_once')
        self.setword('daily_log',3,self.word('seconds_log',227)+2)
        self.setword('daily_log',0,1)
        reads=self.word('rtc_pace',5)
        for _ in range(256): self.tick(); self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',0),2)
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(self.word('rtc_pace',5),reads)
        self.assertEqual(self.idle(),[])

    def test_window_manual_lease_and_time_keeps_cpu_awake(self):
        self.running(); self.hold(2)
        self.assertEqual(self.get(3),0)
        time=f'{self.get(16):02}:{self.get(15):02}:{self.get(5):02}'.encode()
        self.feed(b'+TIME:Wed Oct  7 '+time+b' 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log',0),3)
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(self.idle(),[])
        # Keep the simulated RTC running throughout the real 60-second lease.
        self.hold(0,7680)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.idle(),[1])

    def test_window_0600_resume_uses_timer_boundary_all_modes(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp(); self.night_run(mode,5,59)
                pulses=self.get(12)
                self.night_simulate(59,5,59)
                self.assertEqual(self.get(12),pulses)
                self.night_simulate(2,5,59,59)
                self.assertGreater(self.get(12),pulses)
                self.assertEqual(self.word('minute_log',193),0)
                self.assertEqual(self.get(22),360)

if __name__=='__main__': unittest.main()
