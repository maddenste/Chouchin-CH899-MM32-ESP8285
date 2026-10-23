"""RC6AE: real ARM correction/RTC code plus timer model, not motor physics."""
import unittest
from pathlib import Path
from check_rc6ad_startup_parking import Tests as Prior, ButtonTests as ButtonPrior, RTCTests as RTCPrior
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0

ARTIFACT=Path(__file__).parent/'release_candidate_rc6ae/build/MM32SPIN05PF_CORRECTION_RESUME_RC6AE_20261022.axf'

class Tests(Prior):
    artifact=ARTIFACT
    signature=0x4d505288

    def result(self,name,*args):
        self.call(name,*args)
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def correction_fixture(self,style=3,saver=0,hour=14,delta=1,second=30):
        self.start_pwm(style)
        self.setword('minute_log',192,saver)
        # Accept a real UART record before freezing correction ownership.
        wire=f'+TIME:Thu Oct 22 {hour:02}:20:{second:02} 2026 +0100 10:00 {style}{saver}\r\n'.encode()
        for b in wire:self.call('uart_probe_consume',b)
        target=self.result('rtc_event_stamp',self.symbols['uart_probe_time_event'])
        source=target-delta;sod=source%86400
        self.put(16,sod//3600);self.put(15,sod//60%60);self.put(5,sod%60)
        self.put(22,(sod//60)%720);self.fixture_clock()
        self.setword('seconds_log',227,source)
        # Model an already completed, qualified hardware-reference hold.
        # Observer gating for normal modes is armed before that completion.
        self.store(0x40012c2c,65535)
        self.advance_timer(self.pair()[0]*970,dispatch=False)
        self.assertEqual(self.bt_count,960)
        self.setword('seconds_log',219,960)
        self.setword('second_active',0,0);self.setword('second_highs',0,0)
        self.put(30,1)
        self.setword('daily_log',0,7);self.setword('daily_log',12,1)
        self.setword('daily_log',13,1);self.setword('daily_log',6,target)
        self.setword('daily_log',7,source)
        self.setword('correction_runtime_started',0,0)
        return target

    def trace(self):
        writes=[]
        hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,
            lambda c,a,address,size,value,u:writes.append((address,value)))
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        return writes,hook

    def frozen(self):
        return (self.counter,self.down,self.reg(0),self.reg(0x28),self.reg(0x2c),
                self.reg(0x34),self.reg(0x38),self.reg(0x3c),self.reg(0x20),
                self.raw(0x48000000)&(15<<28),self.raw(0x48000400)&15)

    def test_actual_daily_correction_retains_waveform_then_resumes_all_styles(self):
        for style in range(4):
            with self.subTest(style=style):
                self.setUp();self.correction_fixture(style)
                frozen=self.frozen();edges=len(self.pad_edges)
                writes,hook=self.trace()
                self.call('daily_poll') # Includes real RTC write/readback over modeled I2C.
                self.assertEqual(self.get(3),0)
                self.assertEqual(self.word('daily_log',13),3)
                self.assertEqual(self.get(26),0);self.assertEqual(self.get(30),1)
                self.assertEqual(self.frozen(),frozen)
                self.assertEqual(self.word('wifi_rtc',2),2)
                # Actual catch-up/boundary state machine, without jumping
                # directly to the lower-level resume helper.
                self.tick()
                self.assertEqual(self.get(2),11)
                self.assertFalse(self.gate());self.assertEqual(self.frozen(),frozen)
                self.put(5,0);self.fixture_clock();self.setword('rtc_boundary',0,1)
                self.tick()
                self.cpu.hook_del(hook)
                self.assertEqual(self.get(3),0)
                self.assertEqual(self.get(2),7)
                self.assertEqual(self.word('daily_log',13),0)
                self.assertEqual(self.word('seconds_log',58),1)
                self.assertEqual(self.frozen(),frozen)
                self.assertEqual(len(self.pad_edges),edges)
                self.assertTrue(self.gate())
                # Disabling an unused advisory IRQ is harmless; no waveform
                # register, UG, CCER or motor ownership may change.
                self.assertFalse([(a,v) for a,v in writes if
                                  0x40000400<=a<=0x40000440 and a!=0x4000040c])
                p,w=self.pair();before=len(self.pad_edges)
                self.advance_timer(p*100,dispatch=False)
                events=self.pad_edges[before:]
                rises=[e for e in events if e[2]];falls=[e for e in events if not e[2]]
                self.assertEqual((len(rises),len(falls)),(100,100))
                self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
                self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
                self.assertFalse(self.overlaps)

    def test_forward_catchup_and_backward_wait_keep_phase_all_styles(self):
        for style in range(4):
            for delta in (61,-31):
                with self.subTest(style=style,delta=delta):
                    self.setUp();self.correction_fixture(style,delta=delta)
                    frozen=self.frozen();writes,hook=self.trace()
                    self.call('daily_poll')
                    for _ in range(256):
                        self.tick()
                        if self.get(2)==11:break
                    self.assertEqual(self.get(3),0)
                    self.assertEqual(self.get(2),11)
                    self.assertFalse(self.gate());self.assertEqual(self.frozen(),frozen)
                    # For the backwards case, let actual time reach the
                    # retained minute-hand position; no reverse motor motion.
                    minute=self.get(22)
                    self.put(16,minute//60);self.put(15,minute%60);self.put(5,0)
                    self.fixture_clock();self.setword('rtc_boundary',0,1);self.tick()
                    self.cpu.hook_del(hook)
                    self.assertEqual(self.get(3),0);self.assertEqual(self.get(2),7)
                    self.assertTrue(self.gate());self.assertEqual(self.frozen(),frozen)
                    self.assertEqual(self.word('seconds_log',58),1)
                    self.assertFalse([(a,v) for a,v in writes if
                                      0x40000400<=a<=0x40000440 and a!=0x4000040c])

    def test_permanently_parked_correction_does_not_launch_seconds(self):
        for style in range(4):
            self.setUp();self.initial_release(style,2,14)
            wire=f'+TIME:Thu Oct 22 14:00:30 2026 +0100 10:00 {style}2\r\n'.encode()
            for b in wire:self.call('uart_probe_consume',b)
            target=self.result('rtc_event_stamp',self.symbols['uart_probe_time_event'])
            self.setword('seconds_log',227,target-1)
            for i,v in ((0,7),(12,1),(13,1),(6,target),(7,target-1)):
                self.setword('daily_log',i,v)
            self.setword('correction_runtime_started',0,0)
            writes,hook=self.trace();self.call('daily_poll');self.tick()
            self.put(5,0);self.fixture_clock();self.setword('rtc_boundary',0,1);self.tick()
            self.cpu.hook_del(hook)
            self.assertEqual(self.get(3),0);self.assertEqual(self.get(2),7)
            self.assertEqual(self.reg(0)&1,0)
            self.assertEqual(self.word('seconds_log',60),1)
            self.assertFalse([(a,v) for a,v in writes if a==0x40000414])

    def test_exact_corrected_zero_resumes_with_minute_marker_all_styles(self):
        for style in range(4):
            self.setUp();self.correction_fixture(style,second=0)
            frozen=self.frozen();writes,hook=self.trace()
            self.call('daily_poll');self.tick()
            self.cpu.hook_del(hook)
            self.assertEqual(self.get(3),0);self.assertEqual(self.get(2),7)
            self.assertTrue(self.gate());self.assertEqual(self.frozen(),frozen)
            self.assertEqual(self.word('request_pulses'),6)
            self.assertEqual(self.word('seconds_log',58),1)
            self.assertFalse([(a,v) for a,v in writes if
                              0x40000400<=a<=0x40000440 and a!=0x4000040c])
            for _ in range(64):self.tick()
            self.assertEqual(self.get(3),0)
            self.assertEqual(self.word('request_pulses'),0)
            self.assertEqual(self.get(22),140)
            self.assertFalse(self.overlaps)

    def test_overnight_correction_stays_gated_until_morning_all_styles(self):
        for style in range(4):
            self.setUp();self.correction_fixture(style,1,5)
            frozen=self.frozen();self.call('daily_poll');self.tick()
            self.put(5,0);self.fixture_clock();self.setword('rtc_boundary',0,1);self.tick()
            self.assertEqual(self.get(3),0);self.assertFalse(self.gate())
            self.assertEqual(self.frozen(),frozen)
            self.put(16,6);self.put(15,0);self.put(5,0);self.put(22,360);self.fixture_clock()
            self.setword('rtc_boundary',0,1);self.tick()
            self.assertEqual(self.get(3),0);self.assertTrue(self.gate())
            self.assertEqual(self.frozen(),frozen)

class ButtonTests(ButtonPrior):
    artifact=ARTIFACT
    signature=0x4d505288

class RTCTests(RTCPrior):
    artifact=ARTIFACT
    signature=0x4d505288

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_normal_overnight_lap_and_morning_release_preserve_waveform',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_always_parked_runtime_minute_width_is_valid_without_seconds_launch',
            'test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
            'test_unexpected_timer_stop_is_not_treated_as_first_launch',
            'test_native_rec_drain_enters_homing',
            'test_actual_sampling_outage_still_stops_with_snapshot',
            'test_normal_calibration_changes_only_safe_gap_without_extra_counts',
            'test_normal_waveform_continues_across_three_hardware_wraps_without_cpu',
            'test_timer_stall_watchdog_releases_coils']
    suite=unittest.TestSuite([Tests(n) for n in names]+[
        ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'),
        ButtonTests('test_sleep_closes_lease_without_reply_or_motor_change'),
        RTCTests('test_compact_calendar_failures_restore_bus')])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
