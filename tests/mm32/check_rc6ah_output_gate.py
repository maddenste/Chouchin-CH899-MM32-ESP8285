"""Actual ARM firmware plus explicit timer/DMA model; no motor physics.

Models documented TIM1_CH1 -> DMA1 channel 2 one-shot CCER write. This is
an assumption about silicon behaviour, not a substitute for a live test.
"""
import unittest
from pathlib import Path
from check_rc6ag_time_echo import Tests as Prior
from unicorn import UC_HOOK_MEM_WRITE

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6ah/build/MM32SPIN05PF_OUTPUT_GATE_RC6AH_20261022.axf'
    signature=0x4d50528b

    def setUp(self):
        super().setUp()
        if not any(a<=0x40020000<=b for a,b,p in self.cpu.mem_regions()):
            self.cpu.mem_map(0x40020000,0x1000)
        self.dma_delay=0;self.dma_due=None;self.dma_failed=False;self.dma_writes=[]
        def dma_flags(c,a,address,size,value,u):
            if address==0x40020004:self.store(0x40020000,self.raw(0x40020000)&~value)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,dma_flags,begin=0x40020004,end=0x40020004)

    def gate(self):
        return bool(self.reg(0)&1) and self.reg(0x20)==0x110

    def dma_transfer(self):
        self.dma_due=None
        cfg=self.raw(0x4002001c)
        if not cfg&1 or self.raw(0x40020020)!=1:return
        self.assertEqual(cfg,0x3a19)
        self.assertEqual(self.raw(0x40020024),0x40000420)
        source=self.raw(0x40020028)
        self.assertLess(source,0x20000800)
        if self.dma_failed:
            self.store(0x40020000,self.raw(0x40020000)|0x80)
            self.call('DMA1_Channel2_3_Handler');return
        value=self.raw(source)
        self.store(0x40000420,value)
        self.store(0x40020020,0)
        self.store(0x4002001c,cfg&~1)
        self.store(0x40020000,self.raw(0x40020000)|0x30)
        self.dma_writes.append((self.timer_time,self.bt_count,value))
        self.refresh()

    def advance_timer(self,counts,dispatch=True):
        if not hasattr(self,'dma_due') or not self.word('seconds_log',218):
            return super().advance_timer(counts,dispatch)
        while counts:
            # Unlike earlier fixtures, TIM3 clock ignores TIM1's TRGO.
            active=bool(self.reg(0)&1)
            nexts=[]
            if active:
                top=self.reg(0x2c)
                nexts.append((self.counter if self.down else top-self.counter,'bound'))
                for ch in range(4):
                    compare=self.reg(0x34+ch*4)
                    delta=self.counter-compare if self.down else compare-self.counter
                    if delta>0 and compare<=top:nexts.append((delta,ch))
            if self.raw(0x40014000)&1:
                nexts.append((((self.raw(0x40014034)-self.mt_count)&65535) or 65536,'minute'))
            if self.dma_due is not None:nexts.append((self.dma_due-self.timer_time,'dma'))
            step=min([counts]+[d for d,k in nexts if d>0])
            events=[k for d,k in nexts if d==step]
            if active:self.counter+=-step if self.down else step
            if self.raw(0x40014000)&1:self.mt_count=(self.mt_count+step)&65535
            self.timer_time+=step;counts-=step
            if active:
                if 'bound' in events:self.down=not self.down;self.sr|=1
                for ch in range(4):
                    if ch in events:
                        self.sr|=2<<ch
                        if ch==0 and (self.reg(4)&0x70)==0x30:
                            if self.raw(0x40012c00)&1 and self.raw(0x40012c08)&0x77==0x27:
                                top=self.raw(0x40012c2c)&65535
                                self.bt_count=0 if self.bt_count>=top else self.bt_count+1
                                if self.bt_count==self.raw(0x40012c34) and self.raw(0x40012c0c)&0x200:
                                    if self.raw(0x4002001c)&1 and self.raw(0x40020020):
                                        if self.dma_delay:self.dma_due=self.timer_time+self.dma_delay
                                        else:self.dma_transfer()
            if 'dma' in events:self.dma_transfer()
            if 'minute' in events:self.mt_sr|=2
            self.refresh()
            if dispatch:
                if self.sr&self.reg(0x0c)&18:self.call('TIM3_Handler')
                if self.mt_sr&self.raw(0x4001400c)&2:self.call('TIM14_Handler')

    def settle_release(self):
        for _ in range(18):
            if self.gate():return
            self.tick()
            self.assertEqual(self.get(3),0)
        self.fail('safe release failed to find an up-counting gap')

    def test_dma_stops_exactly_960_but_timer_runs_without_cpu(self):
        for delay in (0,2,32,128):
            self.setUp();self.start_pwm(3);self.dma_delay=delay
            p,w=self.pair();self.advance_timer(p*1020,dispatch=False)
            rises=[e for e in self.pad_edges if e[2]];falls=[e for e in self.pad_edges if not e[2]]
            self.assertEqual((len(rises),len(falls)),(960,960))
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
            self.assertEqual(self.reg(0)&0x61,0x61);self.assertEqual(self.reg(8),0)
            self.assertFalse(self.gate());self.assertEqual(self.pad,[False,False])
            self.assertEqual(len(self.dma_writes),1)
            before=(self.counter,self.down);edges=len(self.pad_edges)
            self.advance_timer(p//3,dispatch=False)
            self.assertNotEqual((self.counter,self.down),before)
            self.assertEqual(len(self.pad_edges),edges)

    def test_sampled_three_laps_full_width_polarity_and_no_timer_rebuild(self):
        for style in (2,3):
            self.setUp();self.start_pwm(style);p,w=self.pair();writes=[]
            self.cpu.hook_add(UC_HOOK_MEM_WRITE,
                lambda c,a,address,size,value,u:writes.append((address,value)),
                begin=0x40000400,end=0x40000440)
            self.cpu.ctl_remove_cache(0x08000000,0x08008000)
            last_pin=None
            for lap in range(3):
                start=len(self.pad_edges);self.complete_lap()
                events=self.pad_edges[start:]
                rises=[e for e in events if e[2]];falls=[e for e in events if not e[2]]
                self.assertEqual((len(rises),len(falls)),(960,960))
                self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
                self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
                if last_pin is not None:self.assertNotEqual(rises[0][1],last_pin)
                last_pin=rises[-1][1]
                if lap<2:
                    self.advance_timer(p*5+123,dispatch=False)
                    self.put(30,0);self.call('parallel_seconds_runtime_begin')
                    self.call('pwm_resume_lap');self.settle_release()
            protected={0x40000400,0x40000408,0x40000414,0x40000418,
                       0x4000041c,0x40000424,0x40000428,0x4000042c,
                       0x40000434,0x40000438,0x4000043c}
            self.assertFalse([(a,v) for a,v in writes if a in protected])
            self.assertEqual(self.word('seconds_log',58),2)
            self.assertFalse(self.overlaps)

    def test_dma_transfer_error_stops_safely(self):
        self.start_pwm(3);self.dma_failed=True
        self.assertEqual((self.raw(0xe000e408)>>16)&255,128)
        self.advance_timer(self.pair()[0]*970)
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.pad,[False,False])
        self.assertEqual(self.reg(0)&1,0)

    def held_fixture(self,style=3):
        self.start_pwm(style)
        self.store(0x40012c2c,65535)
        self.advance_timer(self.pair()[0]*970,dispatch=False)
        self.assertEqual(self.reg(0x20),0)
        self.setword('seconds_log',219,960)
        self.setword('second_active',0,0);self.setword('second_highs',0,0)
        self.put(30,1)

    def test_late_release_irq_skips_unsafe_phase_then_delivers_full_pulse(self):
        self.held_fixture();p,w=self.pair()
        self.counter=w//2+64;self.down=False;self.refresh()
        self.put(30,0);self.call('parallel_seconds_runtime_begin');self.call('pwm_resume_lap')
        self.assertEqual(self.word('seconds_log',61),1)
        before=len(self.pad_edges)
        # Delay notification until the internal reference is already active.
        high=p-w//2
        self.advance_timer(high+200-self.counter,dispatch=False)
        self.call('TIM3_Handler')
        self.assertFalse(self.gate());self.assertEqual(len(self.pad_edges),before)
        self.advance_timer(p*4)
        self.assertTrue(self.gate());self.assertEqual(self.word('seconds_log',61),0)
        events=self.pad_edges[before:]
        rises=[e for e in events if e[2]];falls=[e for e in events if not e[2]]
        self.assertGreaterEqual(len(falls),1)
        self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
        self.assertFalse(self.overlaps)

    def test_daily_correction_retains_running_timer_and_releases_all_styles(self):
        for style in range(4):
            self.setUp();self.held_fixture(style)
            wire=self.wire_record(style);self.consume(wire)
            target=self.result('rtc_event_stamp',self.symbols['uart_probe_time_event'])
            self.put(16,14);self.put(15,20);self.put(5,29);self.put(22,140);self.fixture_clock()
            self.setword('seconds_log',227,target-1)
            for i,v in ((0,7),(12,1),(13,1),(6,target),(7,target-1)):
                self.setword('daily_log',i,v)
            self.setword('correction_runtime_started',0,0)
            pair=self.pair();writes,hook=self.trace()
            self.call('daily_poll');self.tick()
            self.assertEqual(self.get(3),0);self.assertEqual(self.get(2),11)
            self.assertEqual(self.reg(0)&1,1);self.assertEqual(self.reg(0x20),0)
            self.put(5,0);self.fixture_clock();self.setword('rtc_boundary',0,1);self.tick()
            self.settle_release();self.cpu.hook_del(hook)
            self.assertEqual(self.get(2),7);self.assertEqual(self.get(3),0)
            self.assertEqual(self.pair(),pair)
            self.assertEqual(self.word('seconds_log',58),1)
            self.assertFalse([(a,v) for a,v in writes if a in
                (0x40000400,0x40000408,0x40000414,0x40000418,0x4000041c,
                 0x40000424,0x40000428,0x4000042c,0x40000438,0x4000043c)])

    def test_normal_modes_resume_then_wrap_without_output_gaps(self):
        for style in (0,1):
            self.setUp();self.held_fixture(style);p,w=self.pair()
            before=len(self.pad_edges)
            self.put(30,0);self.call('parallel_seconds_runtime_begin');self.call('pwm_resume_lap')
            self.settle_release()
            self.advance_timer(p*1930,dispatch=False)
            events=self.pad_edges[before:]
            rises=[e for e in events if e[2]];falls=[e for e in events if not e[2]]
            self.assertGreaterEqual(len(rises),1930);self.assertGreaterEqual(len(falls),1930)
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
            self.assertTrue(self.gate());self.assertFalse(self.overlaps)

    def test_hold_blanks_do_not_advance_position_or_polarity(self):
        self.start_pwm(3);self.complete_lap()
        position=self.word('seconds_log',248);polarity=self.word('second_polarity')
        before=len(self.pad_edges);old=(self.counter,self.down)
        for _ in range(256):self.tick()
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('seconds_log',248),position)
        self.assertEqual(self.word('second_polarity'),polarity)
        self.assertEqual(len(self.pad_edges),before)
        self.assertNotEqual((self.counter,self.down),old)

    def test_resume_timeout_and_invalid_output_state_fail_safe(self):
        self.held_fixture();self.counter=self.pair()[1]//2+64;self.down=False
        self.call('pwm_resume_lap')
        self.put(4,self.word('seconds_log',62)+129)
        self.call('clock_tick_body')
        self.assertEqual(self.get(3),10);self.assertEqual(self.pad,[False,False])
        self.setUp();self.start_pwm(3);self.store(0x40000420,0x10)
        self.call('clock_tick_body')
        self.assertEqual(self.get(3),10);self.assertEqual(self.pad,[False,False])

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_normal_waveform_continues_across_three_hardware_wraps_without_cpu',
            'test_normal_calibration_changes_only_safe_gap_without_extra_counts',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_echo_exact_complete_record_only_after_settings_processed',
            'test_native_rec_drain_enters_homing']
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not r.wasSuccessful())
