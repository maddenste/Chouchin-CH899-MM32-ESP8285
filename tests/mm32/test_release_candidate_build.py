"""Clean standalone MM32 release candidate: ordinary selectable clock modes."""
import struct
import unittest
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PRIMASK, UC_ARM_REG_R0, UC_ARM_REG_PC
from test_trial69_build import Tests as Prior
from test_trial63_build import Tests as SleepPrior

class Tests(Prior):
    artifact=Prior.artifact.with_name('MM32SPIN05PF_RELEASE_CANDIDATE_RC5_20261011.axf')
    signature=0x4d505205
    source_dir=Prior.artifact.parent.parent/'release_candidate/src/target'
    # Features are fixed in the standalone source, not selected by trial flags.
    defines=[]
    component_sources=['parallel_home_main.c','parallel_minute_component.c',
                       'parallel_seconds_component.c','../mm32_uart.c']
    extra_sources=['parallel_leds.c','rtc.c']
    irq_instruction_budget=20000
    return_sentinel=0x08007f00

    def test_release_final_home_dwell_before_catchup_all_modes(self):
        for mode in range(4):
            for entry in range(73,79):
                with self.subTest(mode=mode,entry=entry):
                    self.setUp()
                    self.setword('minute_log',188,0);self.setword('minute_log',189,0)
                    pulses=[]
                    def trace(cpu,access,address,size,value,user):
                        if value&6 in (2,4) or value&(6<<16):
                            pulses.append((self.get(4),value))
                    self.cpu.hook_add(UC_HOOK_MEM_WRITE,trace,begin=0x48000410,end=0x48000410)
                    self.tick()
                    self.feed(f'+TIME:Thu Oct  8 05:34:23 2026 +0100 10:00 {mode}0\r\n'.encode())
                    home=None;deadline=None
                    for elapsed in range(1,8000):
                        if elapsed%128==0:
                            sod=5*3600+34*60+23+elapsed//128
                            self.rtc_time(sod//3600,sod//60%60,sod%60);self.rtc_poll()
                        p=self.word('seconds_log',5)+1
                        m=self.get(20)+int(bool(self.word('minute_active')))
                        self.tick(int(3<=p<=19) if self.get(19)==1 else int(m>=entry))
                        self.assertEqual(self.get(3),0)
                        if self.get(8):
                            self.assertEqual(self.word('minute_log',254),self.get(10)+128)
                        if self.get(7) and home is None:
                            home=self.get(11);deadline=self.word('minute_log',251)
                            self.assertEqual(deadline-home,128)
                        if home is not None and self.get(4)>=deadline+20:break
                    self.assertIsNotNone(home)
                    rises=[(tick,value) for tick,value in pulses if value&6 in (2,4)]
                    last=next(e for e in reversed(rises) if e[0]<=home)
                    after=[e for e in rises if e[0]>home]
                    self.assertEqual(after[0][0],deadline)
                    self.assertNotEqual(last[1],after[0][1])
                    self.assertEqual([b[0]-a[0] for a,b in zip(after,after[1:])],[8,8])
                    for rise,_ in after:
                        fall=next(t for t,v in pulses if t>rise and v&(6<<16))
                        self.assertEqual(fall-rise,4)
                    self.assertEqual(self.get(20)-self.word('minute_log',249),52)

    def test_release_home_settle_wrap_and_zero_target_release(self):
        for start in (10000,0xfffffff8):
            self.setUp();self.startup_release_fixture()
            self.put(4,start);self.put(2,10);self.put(22,600)
            self.setword('rtc_edge_tick',0,start)
            self.setword('minute_log',214,start)
            self.put(25,start)
            due=(start+128)&0xffffffff
            self.setword('minute_log',251,due);self.setword('minute_log',252,1)
            count=self.get(23)
            for _ in range(127):
                self.tick();self.assertFalse(self.word('minute_active'))
                self.assertEqual(self.get(23),count)
            self.tick();self.assertTrue(self.word('minute_active'))
            self.assertEqual(self.word('minute_log',252),0)
        self.setUp();self.startup_release_fixture()
        self.setword('minute_log',251,self.get(4)+128);self.setword('minute_log',252,1)
        self.setword('rtc_boundary',0,1);self.tick()
        self.assertEqual(self.get(26),0)
        for _ in range(127):self.tick()
        self.setword('rtc_boundary',0,1);self.tick()
        self.assertEqual(self.get(26),1)

    def test_release_seconds_home_gap_and_fresh_boundary(self):
        for mode in range(4):
            for start in (10000,0xfffffff8):
                with self.subTest(mode=mode,start=start):
                    self.setUp();self.startup_release_fixture()
                    self.put(4,start);self.setword('rtc_edge_tick',0,start)
                    self.setword('minute_log',214,start)
                    self.setword('minute_log',188,mode)
                    self.setword('minute_log',254,(start+128)&0xffffffff)
                    self.setword('minute_log',255,1)
                    for _ in range(127):
                        self.setword('rtc_boundary',0,1);self.tick()
                        self.assertEqual(self.get(26),0)
                        self.assertFalse(self.word('second_active'))
                    # The deadline alone is not a release edge.
                    self.tick();self.assertEqual(self.get(26),0)
                    self.setword('rtc_boundary',0,1);self.tick()
                    self.assertEqual(self.get(26),1)
                    self.assertEqual(self.word('minute_log',255),0)
                    self.assertEqual(self.word('minute_log',189),mode)

    def test_release_both_home_deadlines_are_independent(self):
        for seconds_due in (10040,10300):
            self.setUp();self.startup_release_fixture()
            self.put(2,10);self.put(22,600)
            self.setword('minute_due',0,10001)
            self.setword('minute_log',251,10128);self.setword('minute_log',252,1)
            self.setword('minute_log',254,seconds_due);self.setword('minute_log',255,1)
            for _ in range(127):self.tick()
            self.assertFalse(self.word('minute_active'))
            self.tick();self.assertTrue(self.word('minute_active'))
            self.assertEqual(self.get(26),0)

    def test_release_catchup_uniform_while_seconds_run_all_modes(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp(); self.startup_release_fixture()
                self.wire(f'+TIME:Wed Oct  7 23:45:00 2026 +0100 10:00 {mode}0\r\n'.encode())
                self.put(2,10); self.put(22,600)
                self.setword('rtc_boundary',0,1); self.tick()
                self.edges.clear(); self.hold(0,512)
                self.assertEqual((self.get(2),self.get(3)),(10,0))
                hz=62500 if mode&2 else 250000
                rises=[stamp for stamp,a,v in self.edges if a==0x48000410 and v in (2,4)]
                falls=[stamp for stamp,a,v in self.edges if a==0x48000410 and v==6<<16]
                seconds=[stamp for stamp,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
                self.assertGreater(len(rises),60)
                # Capture starts after one rise and can end before the last
                # fall. Compare only complete pulse pairs inside the window.
                falls=[stamp for stamp in falls if stamp>rises[0]]
                self.assertGreaterEqual(min(len(rises),len(falls)),60)
                # Integer counter observations may differ by one fine count;
                # there must be no seconds-gated 117ms gaps or short pulses.
                self.assertTrue(all(abs((b-a)/hz-.0625)<.00002 for a,b in zip(rises,rises[1:])))
                self.assertTrue(all(abs((b-a)/hz-.03125)<.00002 for a,b in zip(rises,falls)))
                ideal=(3776,3777) if mode&2 else (15625,)
                self.assertTrue(all(b-a in ideal for a,b in zip(seconds,seconds[1:])))

    def startup_release_fixture(self):
        self.running()
        self.put(4,10000)
        self.put(26,0); self.put(2,11)
        self.put(5,0); self.put(22,705)
        self.setword('minute_log',180,0)
        self.setword('minute_log',185,0)
        self.setword('minute_log',188,0)
        self.setword('minute_log',189,0)
        self.setword('minute_log',190,0)
        self.setword('minute_log',192,0)
        self.setword('rtc_pace',4,1)
        self.fixture_clock()

    def test_release_catchup_finishes_whole_markers_without_seconds_restart(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp(); self.mode_run(mode); self.simulate(1)
                target=(self.get(16)%12)*60+self.get(15)
                self.put(2,10); self.put(22,(target-2)%720)
                self.put(25,self.get(4))
                self.setword('catchup_pulses',0,0)
                self.setword('minute_due',0,self.get(4)+1)
                laps=self.word('minute_log',185)
                count=self.get(23); self.edges.clear()
                self.simulate(3)
                self.assertEqual((self.get(2),self.get(3),self.get(22)),(7,0,target))
                self.assertEqual(self.get(23)-count,12)
                self.assertEqual(self.word('catchup_pulses'),0)
                self.assertEqual(self.word('minute_log',185),laps)
                hz=62500 if mode&2 else 250000
                rises=[stamp for stamp,a,v in self.edges if a==0x48000410 and v in (2,4)]
                falls=[stamp for stamp,a,v in self.edges if a==0x48000410 and v==6<<16]
                self.assertEqual(len(rises),12)
                # Finish may issue another low write after the final fall.
                self.assertTrue(all(abs((b-a)/hz-.03125)<.00002 for a,b in zip(rises,falls[:12])))

    def test_release_startup_latest_time_mode_before_first_pulse(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp(); self.startup_release_fixture()
                self.wire(f'+TIME:Wed Oct  7 23:45:00 2026 +0100 10:00 {mode}0\r\n'.encode())
                self.assertEqual(self.word('minute_log',188),mode)
                self.assertEqual(self.word('minute_log',189),0)
                self.setword('rtc_boundary',0,1); self.tick()
                self.assertEqual(self.get(26),1)
                self.assertEqual(self.word('minute_log',189),mode)
                self.assertEqual(self.word('minute_log',190),0)
                self.assertEqual(self.word('minute_log',185),1)
                self.assertEqual(self.reg(0x28),127 if mode&2 else 31)
                self.assertEqual(self.get(3),0)

    def test_release_startup_latest_settings_win_without_early_release(self):
        self.startup_release_fixture(); self.put(2,10); self.put(22,600)
        for mode in (3,1,2):
            self.wire(f'+TIME:Wed Oct  7 23:45:00 2026 +0100 10:00 {mode}0\r\n'.encode())
        self.put(7,0); self.setword('rtc_boundary',0,1); self.tick()
        self.assertEqual(self.get(26),0)
        self.put(7,1); self.tick()
        self.assertEqual(self.get(26),0)
        self.setword('rtc_boundary',0,1); self.tick()
        self.assertEqual(self.get(26),1)
        self.assertEqual(self.word('minute_log',189),2)
        self.assertEqual(self.get(3),0)

    def test_release_correction_does_not_bypass_mode_queue(self):
        self.mode_run(0)
        self.put(26,0); self.put(2,11); self.put(5,0)
        self.setword('minute_log',180,0)
        self.setword('minute_log',188,3)
        self.setword('daily_log',13,3)
        self.put(22,600); self.setword('rtc_boundary',0,1)
        self.tick()
        self.assertEqual(self.word('minute_log',189),0)
        self.assertGreater(self.word('minute_log',185),0)
        self.assertEqual(self.get(3),0)

    def test_release_actual_homing_time_selects_first_lap(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp()
                self.setword('minute_log',188,self.boot_modes[0])
                self.setword('minute_log',189,self.boot_modes[1])
                self.setword('minute_log',192,self.boot_night)
                self.tick()
                self.feed(f'+TIME:Thu Oct  8 12:00:23 2026 +0100 10:00 {mode}0\r\n'.encode())
                self.assertEqual(self.word('minute_log',188),mode)
                self.assertEqual(self.word('minute_log',189),0)
                for elapsed in range(1,128*120):
                    if self.get(2)==1:
                        high=(int(246<=self.word('seconds_log',5)+1<=262)
                              if self.get(19)==1 else int(self.word('minute_log',5)+1>=13))
                    else:
                        p=self.word('seconds_log',248)+1
                        high=int(889<=p<=904)
                    self.tick(high)
                    if elapsed%128==0:
                        sod=12*3600+23+elapsed//128
                        self.rtc_time(sod//3600,sod//60%60,sod%60)
                        self.call('parallel_poll_once')
                    self.assertEqual(self.get(3),0,(elapsed,self.get(2)))
                    if self.get(26):
                        self.assertEqual((self.get(7),self.get(8)),(1,1))
                        self.assertGreaterEqual(self.get(9)-self.get(10),128)
                        self.assertGreaterEqual(self.get(9)-self.get(11),128)
                        self.assertEqual(self.word('minute_log',189),mode)
                        self.assertEqual(self.word('minute_log',185),1)
                        self.assertEqual(self.reg(0x28),127 if mode&2 else 31)
                        break
                else:
                    self.fail('First post-homing release never occurred')

    def test_release_startup_factory_time_keeps_default_mode(self):
        self.startup_release_fixture()
        self.wire(b'+TIME:Wed Oct  7 23:45:00 2026 +0100 10:00\r\n')
        self.setword('rtc_boundary',0,1); self.tick()
        self.assertEqual((self.get(26),self.word('minute_log',189)),(1,0))
        self.assertEqual(self.reg(0x28),31)
        self.assertEqual(self.get(3),0)

    @classmethod
    def prepare_sleep_model(cls):
        # Only the emulator's WFI is replaced; delivered binary is unchanged.
        cls.symbols['sleep_diag_idle']=cls.symbols['cpu_sleep_idle']
        SleepPrior.prepare_sleep_model.__func__(cls)

    def test_release_defaults_and_no_profiler(self):
        self.assertEqual(self.boot_modes,(0,0))
        self.assertEqual(self.boot_night,1)
        self.assertLessEqual(self.ram_end,0x20000c30)
        for name in ('pd_rise','pd_fall','pd_finish','pd_begin','sleep_diag_add',
                     'timing_diag_timer_body','timing_diag_systick_body'):
            self.assertNotIn(name,self.symbols)
        before=[self.word('seconds_log',i) for i in range(214,221)]
        self.idle()
        self.assertEqual(before,[self.word('seconds_log',i) for i in range(214,221)])

    def test_constant_spacing_and_width_over_counter_wraps(self):
        self.fine_run()
        for _ in range(512):
            self.setword('rtc_edge_tick',0,self.get(4)); self.tick()
        rises=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        falls=[t for t,a,v in self.edges if a==0x48000010 and v==1<<23]
        self.assertGreater(len(rises),60)
        self.assertTrue(set(b-a for a,b in zip(rises,rises[1:]))<={3776,3777})
        self.assertEqual(set(b-a for a,b in zip(rises,falls)),{2832})
        self.assertEqual(self.get(3),0)

    def test_release_duty_all_modes(self):
        for mode in range(4):
            self.setUp(); self.mode_run(mode)
            period=self.word('minute_log',181); width=self.word('minute_log',182)
            rate=self.word('rtc_pace',1)+1
            self.assertEqual(width,(period*3+2)//4 if mode&2 else (rate*4*6+64)//128)
            self.assertEqual(self.word('minute_log',183),(rate*(1 if mode&2 else 4)*4+64)//128)
            self.assertLess(width,period)

    def test_release_ordinary_park_keeps_timer(self):
        for mode in (2,3):
            self.setUp(); self.mode_run(mode); writes=[]
            def observe(cpu,access,address,size,value,user):
                if address in (0x40000400,0x40000414,0x40000428): writes.append((address,value))
            hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,observe,begin=0x40000400,end=0x40000440)
            self.simulate(181); self.cpu.hook_del(hook)
            self.assertGreaterEqual(self.word('seconds_log',255),2)
            self.assertEqual(writes,[])
            self.assertEqual(self.get(3),0)

    def test_release_sleep_without_profiling_and_esp_guard(self):
        self.setword('minute_log',211,0)
        self.assertEqual(self.idle(),[1])
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),0)
        self.setword('minute_log',211,1)
        self.assertEqual(self.idle(),[])
        self.setword('minute_log',211,0)
        self.assertEqual(self.idle(epoch=(self.word('seconds_log',213)-1)&0xffffffff),[])
        self.cpu.reg_write(UC_ARM_REG_PRIMASK,1)
        self.assertEqual(self.idle(),[])
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),1)

    def test_audit_ram_addresses(self):
        self.assertEqual(self.symbols['minute_log']+188*4,0x20000534)
        self.assertEqual(self.symbols['minute_log']+195*4,0x20000550)
        self.assertEqual(self.symbols['parallel_log']+4,0x20000648)

    def test_button_clean_exact_protocol_and_ack_while_motors_run(self):
        # AP recovery intentionally keeps power/red alive after CLEAN_OK.
        self.running(); self.hold(3); self.writes.clear()
        self.cpu.mem_write(0x40004408,struct.pack('<I',1)); self.hold(3,530)
        self.assertEqual(bytes(v for a,v in self.writes if a==0x40004400),b'CLEAN\nCLEAN\n')
        self.feed(b'CLEAN_OK\r\n')
        self.assertEqual((self.button(10),self.button(15)),(0,1))
        self.assertTrue(self.output&16)
        self.assertEqual(self.get(28),4)
        self.assertEqual(self.get(2),7)

    def test_button_clean_still_services_real_rtc_edges(self):
        # Use advancing civil time, not Trial41's now-stale 23:45:24 sample.
        self.running(); self.hold(3)
        edges=self.word('rtc_pace',2); self.hold(3,128)
        self.assertEqual(self.word('rtc_pace',2),edges+1)
        self.assertEqual(self.button(10),1)
        self.assertEqual(self.get(3),0)

    def test_button_mset_during_clean_cannot_queue_surprise_wake(self):
        self.running(); self.hold(3); self.hold(0,4); self.hold(2)
        self.assertEqual(self.button(7),0)
        self.feed(b'CLEAN_OK\r\n'); self.call('parallel_poll_once')
        self.assertEqual(self.button(17),0)
        self.assertTrue(self.output&16) # Existing CLEAN setup session, not M.SET.

    def test_release_fault10_is_visible_and_safe(self):
        self.mode_run(3)
        self.cpu.reg_write(UC_ARM_REG_R0,10); self.call('fail')
        self.assertEqual((self.get(2),self.get(3)),(6,10))
        self.assertEqual(self.reg(0x0c),0)
        self.assertEqual(self.word('minute_log',211),0)
        self.cpu.reg_write(UC_ARM_REG_R0,0); self.call('parallel_leds_fault_start')
        end=9*64+8; starts=[]; previous=False
        for tick in range(end+1281):
            self.cpu.reg_write(UC_ARM_REG_R0,tick); self.call('parallel_leds_tick')
            on=self.led_on()
            if on and not previous: starts.append(tick)
            if end<=tick<end+1280:self.assertFalse(on)
            previous=on
        self.assertEqual(starts,[64*i for i in range(10)]+[end+1280])

    def test_release_epoch_zero_is_valid_with_factory_time(self):
        self.setword('minute_log',188,self.boot_modes[0])
        self.setword('minute_log',189,self.boot_modes[1])
        self.setword('minute_log',192,self.boot_night)
        self.tick()
        self.feed(b'+TIME:Sat Jan  1 00:00:00 2000 +0000 10:00\r\n')
        self.assertEqual(self.get(6),1)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('daily_log',12),1)
        self.call('daily_poll')
        self.assertEqual(self.word('daily_log',3),36000)
        self.call('rtc_motion_stamp')
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0),0)
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',192)),(0,1))

    def test_web_time_receipt_does_not_end_sixty_second_lease(self):
        self.running(); self.hold(2); start=self.get(4)
        time=f'{self.get(16):02}:{self.get(15):02}:{self.get(5):02}'.encode()
        self.feed(b'+TIME:Wed Oct  7 '+time+b' 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log'),3)
        self.assertTrue(self.output&16)
        self.poll_at(start+7679); self.assertTrue(self.output&16)
        self.poll_at(start+7680); self.assertFalse(self.output&16)
        self.assertEqual((self.get(2),self.get(3)),(7,0))

    def test_scheduled_wake_at_non_hour_minute_and_success(self):
        # Seed the RTC-window clock coherently; two polls are no longer a
        # civil second, unlike the historical frequent-read implementation.
        self.mode_run(0); self.put(5,59)
        self.rtc_time(23,45,59); self.fixture_clock()
        now=self.now_stamp()
        self.setword('daily_log',10,23); self.setword('daily_log',11,46)
        self.schedule(now)
        self.assertEqual(self.word('daily_log',1),0)
        self.hold(0,128)
        self.assertEqual(self.word('daily_log',1),1)
        self.assertEqual(self.word('daily_log'),2)
        self.assertTrue(self.output&16)
        self.assertEqual(self.get(28),4)
        self.feed(b'+TIME:Wed Oct  7 23:46:00 2026 +0100 23:46\r\n')
        self.assertEqual((self.get(2),self.get(3)),(7,0))
        self.assertFalse(self.output&16); self.assertEqual(self.get(28),2)
        self.assertEqual(self.word('daily_log'),3)
        self.assertEqual(self.word('daily_log',3),now-now%86400+86400+23*3600+46*60)
        for _ in range(5):self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',1),1)

    def test_window_real_systick_handler_mid_i2c_then_sleep(self):
        self.window_seed(); self.setword('minute_log',211,0)
        for _ in range(4):self.tick()
        count=[0]
        def suspend(cpu,address,size,user):
            count[0]+=1
            if count[0]==62500:cpu.emu_stop()
        hook=self.cpu.hook_add(UC_HOOK_CODE,suspend)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        self.call('parallel_poll_once'); self.cpu.hook_del(hook)
        self.assertEqual(count[0],62500)
        context=self.cpu.context_save()
        self.advance_timer((self.word('rtc_pace',1)+1)//128)
        self.call('SysTick_Handler'); self.cpu.context_restore(context)
        self.cpu.emu_start(self.cpu.reg_read(UC_ARM_REG_PC)|1,self.return_sentinel,count=2000000)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('rtc_poll_tick'),self.get(4))
        reads=self.word('rtc_pace',5); self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',5),reads)
        self.assertEqual(self.idle(),[1])

    def test_night_resume_at_0600(self):
        self.test_window_0600_resume_uses_timer_boundary_all_modes()

    def test_late_mode_handover_does_not_wait_a_full_minute(self):
        # A real optical reference arrives one second late. Keep both RTC
        # registers and projected civil time advancing coherently throughout.
        for old in (0,1):
            for new in (2,3):
                self.setUp(); self.mode_run(old)
                for elapsed in range(1,62*128+1):
                    if elapsed%128==0:
                        sec=elapsed//128
                        if sec==25:self.setword('minute_log',188,new)
                        sod=23*3600+45*60+sec
                        self.rtc_time(sod//3600,sod//60%60,sod%60); self.rtc_poll()
                    p=self.word('seconds_log',248)+1
                    self.tick(int(975-self.seconds_offset<=p<=990-self.seconds_offset))
                    self.assertEqual(self.get(3),0)
                self.assertEqual(self.word('minute_log',189),new)
                self.assertEqual(self.word('minute_log',190),0)
                self.assertEqual(self.get(30),0)

if __name__=='__main__': unittest.main()
