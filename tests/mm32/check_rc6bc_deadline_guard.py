"""RC6BC compiled scheduling checks; no probe or physical motor."""
import sys
import unittest
from pathlib import Path
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from check_rc6bb_handover import baseline, Handover

ROOT=Path(__file__).resolve().parent
IMAGE=ROOT.parents[1]/'firmware/mm32/build/MM32SPIN05PF_DEADLINE_GUARD_RC6BC_20261024.axf'
for cls in (baseline.Tests,baseline.Buttons,baseline.General,baseline.RTCChecks,baseline.RecoveryChecks,Handover):
    cls.artifact=IMAGE;cls.signature=0x4d5052a0

class Deadline(baseline.Tests):
    def parked(self):
        self.held_fixture(3)
        self.put(2,7);self.put(16,2);self.put(15,7);self.put(5,40)
        self.put(22,127);self.put(26,1);self.put(30,1)
        self.setword('minute_log',192,1);self.setword('minute_log',191,0)
        self.setword('minute_log',195,0);self.setword('request_pulses',0,0)
        self.store(0x4001400c,0);self.setword('seconds_log',214,0)
        self.setword('seconds_log',16,0)

    def delayed_tick(self,counts=0,next_tick=False):
        fired=[]
        def hook(cpu,address,size,user):
            if address==(self.symbols['clock_tick_body']&~1) and not fired:
                fired.append(1)
                self.advance_timer(counts,dispatch=False)
                if next_tick:self.store(0xe000ed04,self.raw(0xe000ed04)|(1<<26))
        h=self.cpu.hook_add(UC_HOOK_CODE,hook)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        self.call('SysTick_Handler');self.cpu.hook_del(h)
        self.assertTrue(fired)

    def minute(self,phase,delta):
        self.setword('seconds_log',230,phase)
        self.setword('minute_active',0,int(phase==2))
        self.setword('request_pulses',0,2)
        self.store(0x40014034,(self.mt_count+delta)&65535)
        self.store(0x4001400c,2);self.mt_sr=0;self.refresh()

    def test_idle_tick_above_old_margin_is_not_a_missed_edge(self):
        self.parked();g=(self.word('rtc_pace',1)+64)//64
        self.delayed_tick(g+1)
        self.assertEqual(self.get(3),0);self.assertEqual(self.reg(0x20),0)

    def test_close_unpowered_rise_does_not_defer_clock(self):
        for start in (10000,65520):
            self.setUp();self.parked();self.mt_count=start;self.refresh()
            self.minute(1,16);tick=self.get(4)
            self.call('SysTick_Handler')
            self.assertEqual(self.get(4),tick+1)
            self.assertEqual(self.word('seconds_log',214),0)
            self.assertEqual(self.get(3),0)

    def test_delayed_rise_keeps_full_powered_width(self):
        for start in (10000,65520):
            self.setUp();self.parked();self.mt_count=start;self.refresh()
            self.minute(1,16)
            self.advance_timer(1000,dispatch=False)
            now=self.mt_count;width=self.word('minute_log',183)
            self.call('TIM14_Handler')
            self.assertEqual(self.get(3),0)
            self.assertEqual(self.word('seconds_log',230),2)
            self.assertEqual((self.raw(0x40014034)-now)&65535,width)

    def test_powered_fall_still_runs_before_deferred_tick(self):
        for start in (10000,65520):
            self.setUp();self.parked();self.mt_count=start;self.refresh()
            self.minute(2,32);tick=self.get(4)
            self.call('SysTick_Handler')
            self.assertEqual(self.get(4),tick)
            self.assertEqual(self.word('seconds_log',214),1)
            self.advance_timer(32)
            self.assertEqual(self.get(4),tick+1)
            self.assertEqual(self.word('minute_active'),0)
            self.assertEqual(self.get(3),0)

    def test_actual_late_powered_fall_is_still_fatal(self):
        self.parked();g=(self.word('rtc_pace',1)+64)//64
        self.minute(2,g*2)
        self.delayed_tick(g*3+2)
        self.assertEqual((self.get(2),self.get(3)),(6,10))
        self.assertEqual(self.word('seconds_log',17),33)

    def test_powered_pulse_with_a_distant_fall_is_not_a_false_overrun(self):
        self.parked();g=(self.word('rtc_pace',1)+64)//64
        self.minute(2,g*4)
        self.delayed_tick(g+1)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('minute_active'),1)

    def test_six_pulse_bursts_keep_width_and_seconds_epoch_across_timer_phases(self):
        for phase in range(0,65536,4096):
            with self.subTest(phase=phase):
                self.setUp();self.parked();self.mt_count=phase;self.refresh()
                self.setword('request_pulses',0,6)
                epoch=self.word('seconds_log',215)
                count=self.get(13)
                self.call('pwm_minutes_queue')
                width=self.word('minute_log',183)
                for pulse in range(6):
                    to_rise=(self.raw(0x40014034)-self.mt_count)&65535
                    self.advance_timer(to_rise+((pulse+phase//4096)*193)%1000,dispatch=False)
                    now=self.mt_count
                    self.call('TIM14_Handler')
                    self.assertEqual((self.raw(0x40014034)-now)&65535,width)
                    self.assertEqual(self.word('minute_active'),1)
                    self.advance_timer(width)
                    self.assertEqual(self.word('minute_active'),0)
                self.assertEqual(self.get(13)-count,6)
                self.assertEqual(self.word('request_pulses'),0)
                self.assertEqual(self.word('seconds_log',215),epoch)
                self.assertEqual(self.reg(0x20),0)
                self.assertEqual(self.get(3),0)

    def test_excessively_late_unpowered_rise_is_still_fatal(self):
        self.parked();self.minute(1,16)
        self.delayed_tick(self.word('minute_log',184)//4+32)
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',17),33)

    def test_real_next_systick_pending_is_still_fatal(self):
        self.parked();self.delayed_tick(next_tick=True)
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',17),32)
        self.assertTrue(self.word('seconds_log',75)&(1<<26))

    def test_real_backlog_is_still_fatal_and_distinguishable(self):
        self.parked();self.setword('seconds_log',214,1)
        self.call('SysTick_Handler')
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',17),31)
        self.assertEqual(self.word('seconds_log',41),1)
        self.assertEqual(self.word('seconds_log',214),0)

    def test_first_fault_metadata_is_not_overwritten(self):
        self.parked();self.setword('seconds_log',214,1)
        self.call('SysTick_Handler')
        saved=[self.word('seconds_log',n) for n in range(72,80)]
        self.call('motor_tick_fault',33,1234,5678)
        self.assertEqual(self.word('seconds_log',17),31)
        self.assertEqual([self.word('seconds_log',n) for n in range(72,80)],saved)

    def test_startup_backlog_does_not_read_uninitialised_motor_timers(self):
        self.assertEqual(self.word('seconds_log',218),0)
        reads=[]
        hooks=[self.cpu.hook_add(UC_HOOK_MEM_READ,
            lambda c,a,address,size,value,u:reads.append(address),begin=start,end=end)
            for start,end in ((0x40000400,0x4000044f),(0x40012c00,0x40012c4f),(0x40014000,0x4001404f))]
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        self.setword('seconds_log',214,1);self.call('SysTick_Handler')
        for hook in hooks:self.cpu.hook_del(hook)
        self.assertEqual(reads,[])
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',17),31)

if __name__=='__main__':
    if '--focused' in sys.argv:
        selected=[c(n) for c in (Deadline,) for n in c.__dict__ if n.startswith('test_')]
    elif '--handover' in sys.argv:
        selected=[Handover(n) for n in Handover.__dict__ if n.startswith('test_')]
    elif '--motor' in sys.argv:
        selected=[baseline.Tests(n) for n in (
            'test_normal_modes_keep_original_waveforms_and_no_ramp',
            'test_two_laps_and_normal_launch_again_after_hold',
            'test_late_ramp_irq_does_not_change_active_pulse',
            'test_overnight_stop_mode_resumes_with_ramp_without_second_timer_launch',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_always_parked_runtime_minute_width_is_valid_without_seconds_launch',
            'test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
            'test_saver_change_alone_finishes_one_safe_restart')]
    else:
        selected=baseline.cases()
        if '--part=1' in sys.argv:selected=selected[::2]
        if '--part=2' in sys.argv:selected=selected[1::2]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    raise SystemExit(not result.wasSuccessful())
