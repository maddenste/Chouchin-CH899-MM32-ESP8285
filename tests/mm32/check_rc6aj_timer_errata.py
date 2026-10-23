"""Actual RC6AJ ARM plus timer/DMA model. No physical motor model.

Checks the vendor erratum workaround and fail-safe configuration checks.
The model does NOT reproduce undocumented silicon trigger timing or prove
that this defect caused the reported physical lumpiness.
"""
import unittest
from pathlib import Path
from check_rc6ah_output_gate import Tests as Prior
from unicorn import UC_HOOK_MEM_WRITE

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6aj/build/MM32SPIN05PF_TIMER_ERRATA_RC6AJ_20261022.axf'
    signature=0x4d50528d

    def test_all_styles_and_reference_apply_workaround_before_update_or_enable(self):
        for style in range(4):
            self.setUp();events=[]
            def write(c,a,address,size,value,u):
                if address in (0x40000414,0x40000014) and value&1:
                    base=address-0x14
                    self.assertEqual(self.raw(base+8),0x70)
                    events.append((base,'UG'))
                if address in (0x40000400,0x40000000) and value&1:
                    self.assertEqual(self.raw(address+8),0x70)
                    events.append((address,'CEN'))
                if address==0x40012c14 and value&1:
                    self.assertEqual(self.raw(0x40012c08),0x70)
                if address==0x40012c00 and value&1:
                    self.assertEqual(self.raw(0x40012c08),0x27)
                self.assertNotEqual(address,0x40014008) # Reserved on TIM14.
            hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,write,
                                       begin=0x40000000,end=0x40020000)
            self.cpu.ctl_remove_cache(0x08000000,0x08008000)
            self.start_pwm(style);self.call('quartz_poll')
            self.cpu.hook_del(hook)
            self.assertEqual(self.reg(8),0x70)
            self.assertEqual(self.raw(0x40000008),0x70)
            self.assertEqual(self.raw(0x40012c08),0x27)
            self.assertEqual(self.pair(),(31250 if style<2 else 30029,23438))
            self.assertIn((0x40000400,'UG'),events)
            self.assertIn((0x40000000,'UG'),events)

    def test_stop_keeps_unused_slave_selectors_safe(self):
        self.start_pwm(3);self.call('fine_stop')
        self.assertEqual(self.reg(8),0x70)
        self.assertEqual(self.raw(0x40012c08),0x70)
        self.assertEqual(self.reg(0)&1,0)
        self.assertEqual(self.pad,[False,False])

    def test_corrupt_running_pwm_or_observer_configuration_stops(self):
        for address in (0x40000408,0x40012c08):
            self.setUp();self.start_pwm(3);self.store(address,0)
            self.call('clock_tick_body')
            self.assertEqual(self.get(3),10)
            self.assertEqual(self.pad,[False,False])
            self.assertEqual(self.reg(0)&1,0)
            if address==0x40000408:
                self.assertEqual(self.word('seconds_log',63),0)

    def test_corrupt_held_pwm_is_not_released(self):
        self.held_fixture();self.store(0x40000408,0)
        self.call('pwm_resume_lap')
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.pad,[False,False])

    def test_pending_release_rechecks_configuration(self):
        self.held_fixture();self.counter=self.pair()[1]//2+64;self.down=False
        self.call('pwm_resume_lap')
        self.assertEqual(self.word('seconds_log',61),1)
        self.store(0x40000408,0);self.call('pwm_try_resume')
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.pad,[False,False])

    def test_corrupt_reference_configuration_stops_before_measurement(self):
        self.start_pwm(3);self.call('quartz_poll')
        self.assertEqual(self.raw(0x40000008),0x70)
        self.store(0x40000008,0);self.call('quartz_poll')
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',65),0)
        self.assertEqual(self.pad,[False,False])

    def test_reference_calibration_keeps_both_standalone_selectors(self):
        self.start_pwm(3);self.call('quartz_poll');self.q(11,0)
        before=(self.pair(),self.word('second_polarity'),self.counter,self.down)
        for i in range(134):
            self.call('quartz_sample',(200-i*64)%255,
                      (0xfff00000+i*125000)&0xffffffff,20000)
        self.assertGreaterEqual(self.q(14),1)
        self.assertEqual(self.q(16),64000000)
        self.assertEqual(self.raw(0x40000008),0x70)
        self.assertEqual(self.reg(8),0x70)
        self.assertEqual(before,(self.pair(),self.word('second_polarity'),self.counter,self.down))

    def test_full_catchup_to_normal_transition_six_laps(self):
        self.acquisition(0,3)
        self.put(16,10);self.put(15,0);self.put(5,0);self.fixture_clock()
        protected={0x40000400,0x40000408,0x40000414,0x40000418,
                   0x4000041c,0x40000424,0x40000428,0x4000042c,
                   0x40000434,0x40000438,0x4000043c}
        writes=[];transition_laps=None
        def write(c,a,address,size,value,u):
            if address in protected:writes.append((self.get(4),address,value))
        hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,write,
                                   begin=0x40000400,end=0x40000440)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        for _ in range(365*128):
            self.tick(int(888<=self.bt_count<900))
            self.assertEqual(self.get(3),0)
            if self.get(2)==7 and transition_laps is None:
                transition_laps=self.word('seconds_log',255)
        self.cpu.hook_del(hook)
        self.assertEqual(transition_laps,3)
        self.assertEqual(self.get(2),7)
        self.assertEqual(self.word('seconds_log',255),6)
        self.assertTrue(writes)
        self.assertEqual({tick for tick,address,value in writes},{writes[0][0]})
        p,w=self.pair();rises=[e for e in self.pad_edges if e[2]]
        falls=[e for e in self.pad_edges if not e[2]]
        self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
        intervals=[b[0]-a[0] for a,b in zip(rises,rises[1:])]
        self.assertEqual({n for n in intervals if n<2*p},{p})
        self.assertEqual(self.reg(8),0x70)
        self.assertFalse(self.overlaps)

    def test_dma_stops_exactly_960_but_timer_runs_without_cpu(self):
        for delay in (0,2,32,128):
            self.setUp();self.start_pwm(3);self.dma_delay=delay
            p,w=self.pair();self.advance_timer(p*1020,dispatch=False)
            rises=[e for e in self.pad_edges if e[2]]
            falls=[e for e in self.pad_edges if not e[2]]
            self.assertEqual((len(rises),len(falls)),(960,960))
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
            self.assertEqual(self.reg(0)&0x61,0x61)
            self.assertEqual(self.reg(8),0x70)
            self.assertFalse(self.gate());self.assertEqual(self.pad,[False,False])
            self.assertEqual(len(self.dma_writes),1)
            before=(self.counter,self.down);edges=len(self.pad_edges)
            self.advance_timer(p//3,dispatch=False)
            self.assertNotEqual((self.counter,self.down),before)
            self.assertEqual(len(self.pad_edges),edges)

if __name__=='__main__':
    names=[n for n in Prior.__dict__ if n.startswith('test_')]
    names+=[n for n in Tests.__dict__ if n.startswith('test_') and n not in names
            and n!='test_full_catchup_to_normal_transition_six_laps']
    names+=['test_normal_waveform_continues_across_three_hardware_wraps_without_cpu',
            'test_normal_calibration_changes_only_safe_gap_without_extra_counts',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_echo_exact_complete_record_only_after_settings_processed',
            'test_native_rec_drain_enters_homing']
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not r.wasSuccessful())
