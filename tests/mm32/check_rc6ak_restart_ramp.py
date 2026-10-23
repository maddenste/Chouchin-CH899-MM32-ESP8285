"""Focused full-firmware ARM/timer/DMA checks. Not physical motor emulation."""
import unittest
from pathlib import Path
from check_rc6aj_timer_errata import Tests as Prior
from check_rc6ag_time_echo import ButtonTests as ButtonPrior
from unicorn import UC_HOOK_MEM_WRITE

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6ak/build/MM32SPIN05PF_RESTART_RAMP_RC6AK_20261023.axf'
    signature=0x4d50528e

    def held_fixture(self,style=3):
        self.start_pwm(style)
        self.advance_timer(31250*40) # Service the intentionally interrupt-based ramp.
        self.store(0x40012c2c,65535)
        self.advance_timer(self.pair()[0]*970,dispatch=False)
        self.assertEqual(self.reg(0x20),0)
        self.setword('seconds_log',219,960)
        self.setword('second_active',0,0);self.setword('second_highs',0,0)
        self.put(30,1)

    def test_normal_modes_keep_original_waveforms_and_no_ramp(self):
        for style in (0,1):
            self.setUp();self.start_pwm(style)
            self.assertEqual(self.pair(),(31250,23438))
            self.assertEqual(self.word('seconds_log',69),0)
            self.assertEqual(self.reg(0x0c),0)
            self.advance_timer(31250*40,dispatch=False)
            rises=[e for e in self.pad_edges if e[2]]
            falls=[e for e in self.pad_edges if not e[2]]
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{23438})
            self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{31250})

    def test_stop_modes_first_pulse_normal_then32_safe_updates(self):
        for style in (2,3):
            self.setUp();self.start_pwm(style)
            self.assertEqual(self.pair(),(31250,23438));self.assertEqual(self.reg(0x0c),16)
            writes=[]
            self.cpu.hook_add(UC_HOOK_MEM_WRITE,lambda c,a,address,size,value,u:writes.append((address,value)),begin=0x40000400,end=0x40000444)
            self.cpu.ctl_remove_cache(0x08000000,0x08008000)
            self.advance_timer(31250*40)
            self.assertEqual(self.get(3),0)
            self.assertEqual(self.word('seconds_log',67),32)
            self.assertEqual(self.word('seconds_log',69),0)
            self.assertEqual(self.word('seconds_log',70),32)
            self.assertEqual(self.pair(),(30029,22522))
            self.assertEqual(self.reg(0x0c),0)
            rises=[e for e in self.pad_edges if e[2]];falls=[e for e in self.pad_edges if not e[2]]
            self.assertGreater(len(falls),34)
            periods=[31250-(1221*j)//32 for j in range(33)]
            widths=[2*((p*3+4)//8) for p in periods]
            for j,(a,b) in enumerate(zip(rises,falls)):
                self.assertEqual(b[0]-a[0],widths[min(j,32)],(style,j,a,b))
            self.assertTrue(all(a[1]!=b[1] for a,b in zip(rises,rises[1:])))
            self.assertFalse(self.overlaps)
            self.assertFalse([(a,v) for a,v in writes if a in (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428)])
            self.assertEqual(len([a for a,v in writes if a==0x4000042c]),32)

    def test_two_laps_and_normal_launch_again_after_hold(self):
        self.start_pwm(3)
        for lap in range(2):
            self.complete_lap()
            self.assertEqual(self.get(3),0);self.assertEqual(self.bt_count,960)
            self.assertEqual(self.reg(0x20),0)
            self.assertEqual(self.pair(),(30029,22522))
            self.assertEqual(self.word('seconds_log',70),(lap+1)*32)
            self.assertEqual(self.word('seconds_log',71),lap+1)
            if lap==0:
                last_pin=[e[1] for e in self.pad_edges if e[2]][-1]
                before=len(self.pad_edges);polarity=self.word('second_polarity')
                self.advance_timer(30029*6,dispatch=False)
                self.assertEqual(len(self.pad_edges),before)
                self.put(30,0);self.call('parallel_seconds_runtime_begin')
                self.call('pwm_resume_lap');self.settle_release()
                self.assertEqual(self.pair(),(31250,23438))
                self.assertEqual(self.word('second_polarity'),polarity)
                self.assertEqual(self.word('seconds_log',67),0)
                self.advance_timer(31250)
                first=[e for e in self.pad_edges[before:] if e[2]][0]
                self.assertNotEqual(first[1],last_pin)

    def test_late_ramp_irq_does_not_change_active_pulse(self):
        self.start_pwm(3)
        self.advance_timer(31250*2,dispatch=False)
        # Deliberately call service during a powered top pulse.
        self.counter=31250-100;self.down=False;self.refresh()
        pair=self.pair();step=self.word('seconds_log',67)
        self.call('pwm_ramp_service')
        self.assertEqual(self.pair(),pair);self.assertEqual(self.word('seconds_log',67),step)
        self.assertEqual(self.get(3),0)

    def test_ramp_drain_and_stall_still_fail_safe(self):
        self.start_pwm(3);self.call('pwm_drain')
        self.assertEqual(self.word('seconds_log',69),0)
        self.advance_timer(31250*3,dispatch=False)
        self.assertEqual(self.pad,[False,False])
        self.assertEqual(self.reg(0x20),0)
        self.setUp();self.start_pwm(3)
        self.setword('seconds_log',67,0);self.bt_count=65
        self.call('pwm_ramp_service')
        self.assertEqual(self.get(3),10);self.assertEqual(self.pad,[False,False])

    def test_daily_correction_resumes_all_styles_without_rebuilding_timer(self):
        for style in range(4):
            self.setUp();self.held_fixture(style)
            self.consume(self.wire_record(style))
            target=self.result('rtc_event_stamp',self.symbols['uart_probe_time_event'])
            self.put(16,14);self.put(15,20);self.put(5,29);self.put(22,140);self.fixture_clock()
            self.setword('seconds_log',227,target-1)
            for i,v in ((0,7),(12,1),(13,1),(6,target),(7,target-1)):self.setword('daily_log',i,v)
            self.setword('correction_runtime_started',0,0)
            writes,hook=self.trace()
            self.call('daily_poll');self.tick()
            self.assertEqual(self.get(3),0);self.assertEqual(self.get(2),11)
            self.assertEqual(self.reg(0)&1,1);self.assertEqual(self.reg(0x20),0)
            self.put(5,0);self.fixture_clock();self.setword('rtc_boundary',0,1);self.tick()
            self.settle_release();self.cpu.hook_del(hook)
            self.assertEqual(self.get(2),7);self.assertEqual(self.get(3),0)
            self.assertEqual(self.pair(),(31250,23438))
            self.assertEqual(self.word('seconds_log',69),int(style>=2))
            self.assertFalse([(a,v) for a,v in writes if a in (0x40000400,0x40000408,0x40000414,0x40000418,0x4000041c,0x40000424,0x40000428)])

    def test_no_cpu_service_still_stops_at_exactly960_complete_pulses(self):
        self.start_pwm(3)
        self.advance_timer(31250*1000,dispatch=False)
        rises=[e for e in self.pad_edges if e[2]];falls=[e for e in self.pad_edges if not e[2]]
        self.assertEqual((len(rises),len(falls)),(960,960))
        self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{23438})
        self.assertEqual(self.reg(0x20),0);self.assertEqual(self.reg(0)&1,1)
        self.assertEqual(len(self.dma_writes),1);self.assertFalse(self.overlaps)

    def test_overnight_stop_mode_resumes_with_ramp_without_second_timer_launch(self):
        self.acquisition(1,3);launches=self.launch_trace();self.tick();self.complete_lap()
        self.assertEqual(self.get(3),0);self.assertEqual(len(launches),1)
        edges=len(self.pad_edges)
        for _ in range(512):self.tick()
        self.assertEqual(self.get(3),0);self.assertEqual(len(self.pad_edges),edges)
        self.put(16,6);self.put(15,0);self.put(5,0);self.fixture_clock()
        self.setword('rtc_boundary',0,1)
        self.settle_release()
        self.assertEqual(self.get(3),0);self.assertEqual(len(launches),1)
        self.assertEqual(self.pair(),(31250,23438))
        self.assertEqual(self.word('seconds_log',69),1)
        self.assertEqual(self.word('seconds_log',71),2)

class ButtonTests(Tests):
    # Reuse the button scenario on the CURRENT DMA/timer model, not the
    # historical pre-DMA fixture (which has no DMA peripheral mapping).
    pending=ButtonPrior.pending
    poll_web=ButtonPrior.poll_web
    test_mset_wakes_during_each_correction_stage_without_motor_changes=ButtonPrior.test_mset_wakes_during_each_correction_stage_without_motor_changes

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_normal_waveform_continues_across_three_hardware_wraps_without_cpu',
            'test_normal_calibration_changes_only_safe_gap_without_extra_counts',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_echo_exact_complete_record_only_after_settings_processed',
            'test_sleep_closes_lease_without_reply_or_motor_change',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_corrupt_running_pwm_or_observer_configuration_stops',
            'test_native_rec_drain_enters_homing']
    suite=unittest.TestSuite(Tests(n) for n in names)
    suite.addTest(ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
