"""Focused compiled-ARM checks for all-mode seconds PWM, plus timer model."""
import unittest
from pathlib import Path
from check_rc6n_autonomous import Tests as Prior
from unicorn import UC_HOOK_CODE

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6p/build/MM32SPIN05PF_ALL_SECONDS_PWM_RC6P_20261022.axf'
    signature=0x4d505279

    def advance_timer(self,counts,dispatch=True):
        if not hasattr(self,'bt_count') or not self.word('seconds_log',218):
            return super().advance_timer(counts,dispatch)
        while counts:
            active=bool(self.reg(0)&1) and self.gate()
            nexts=[]
            if active:
                top=self.reg(0x2c)
                nexts.append((self.counter if self.down else top-self.counter,'bound'))
                for channel in range(4):
                    ccr=self.reg(0x34+4*channel)
                    delta=self.counter-ccr if self.down else ccr-self.counter
                    if delta>0 and ccr<=top:nexts.append((delta,channel))
            if self.raw(0x40014000)&1:
                nexts.append((((self.raw(0x40014034)-self.mt_count)&65535) or 65536,'minute'))
            step=min([counts]+[d for d,k in nexts if d>0])
            events=[k for d,k in nexts if d==step]
            if active:self.counter+=-step if self.down else step
            if self.raw(0x40014000)&1:self.mt_count=(self.mt_count+step)&65535
            self.timer_time+=step;counts-=step
            if active:
                if 'bound' in events:self.down=not self.down;self.sr|=1
                for channel in range(4):
                    if channel in events:
                        self.sr|=2<<channel
                        if channel==0 and (self.reg(4)&0x70)==0x30:
                            if self.raw(0x40012c00)&1 and self.raw(0x40012c08)&0x77==0x27:
                                top=self.raw(0x40012c2c)&65535
                                self.bt_count=0 if self.bt_count>=top else self.bt_count+1
            if 'minute' in events:self.mt_sr|=2
            self.refresh()
            if dispatch:
                if self.sr&self.reg(0x0c)&18:self.call('TIM3_Handler')
                if self.mt_sr&self.raw(0x4001400c)&2:self.call('TIM14_Handler')

    def test_all_modes_select_hardware_pwm(self):
        for mode in range(4):
            self.setUp();self.start_pwm(mode)
            self.assertEqual(self.reg(0x0c),0)
            self.assertEqual(self.reg(0x28),15)
            self.assertEqual(self.raw(0x40012c2c),959 if mode<2 else 65535)
            self.assertEqual(self.word('minute_log',181),31250 if mode<2 else 30029)
            self.assertEqual(self.word('minute_log',182),23438)

    def test_normal_waveform_continues_across_three_hardware_wraps_without_cpu(self):
        self.start_pwm(0);p=self.word('minute_log',181)
        self.advance_timer(p*2890,dispatch=False)
        rises=[e for e in self.pad_edges if e[2]]
        self.assertEqual(len(rises),2890)
        self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
        self.assertTrue(all(a[1]!=b[1] for a,b in zip(rises,rises[1:])))
        self.assertTrue(self.gate())
        self.assertEqual(self.bt_count,10)
        self.assertFalse(self.overlaps)

    def test_two_sampled_revolutions_in_each_normal_mode(self):
        for mode in (0,1):
            self.setUp();self.start_pwm(mode)
            for _ in range(16000):
                self.tick(int(888<=self.bt_count<900))
                self.assertEqual(self.get(3),0,(mode,self.bt_count))
                self.assertEqual(self.get(30),0)
                if self.word('seconds_log',255)>=2:break
            self.assertEqual(self.word('seconds_log',255),2)
            self.assertGreaterEqual(self.get(12),1920)
            self.assertTrue(self.gate())
            rises=[e[0] for e in self.pad_edges if e[2]]
            self.assertEqual(set(b-a for a,b in zip(rises,rises[1:])),{31250})
            self.assertGreaterEqual(self.get(13),6)

    def test_normal_mode_change_stops_at_hardware_960(self):
        self.start_pwm(0)
        self.setword('minute_log',188,3)
        for _ in range(8000):
            self.tick(int(888<=self.bt_count<900))
            self.assertEqual(self.get(3),0)
            if self.get(30):break
        self.assertEqual(self.bt_count,960)
        self.assertEqual(self.pad,[False,False])
        for _ in range(512):
            self.tick()
            self.assertEqual(self.get(3),0)
            if self.word('minute_log',189)==3 and not self.get(30):break
        self.assertEqual(self.word('minute_log',189),3)
        self.assertEqual(self.raw(0x40012c2c),65535)
        self.assertTrue(self.gate())

    def test_normal_drain_across_counter_wrap(self):
        self.start_pwm(1)
        self.bt_count=0
        self.setword('seconds_log',219,959)
        self.setword('seconds_log',248,959)
        # Supply a valid previously exited reference for the completed lap.
        self.setword('seconds_log',251,890)
        self.setword('seconds_log',252,1)
        self.setword('seconds_log',254,960)
        self.call('pwm_drain')
        self.tick()
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.get(30),0)
        for _ in range(16):
            self.tick()
            self.assertEqual(self.get(3),0)
            if not self.gate():break
        self.assertFalse(self.gate())
        self.assertEqual(self.pad,[False,False])
        self.assertEqual(self.word('seconds_log',248),961)

    def test_normal_calibration_changes_only_safe_gap_without_extra_counts(self):
        for shift in (0.98,1.02):
            for down in (False,True):
                self.setUp();self.start_pwm(0)
                p=self.word('minute_log',181)
                self.down=down
                self.counter=p//2-1400 if down else p//2+1400
                self.bt_count=10;self.setword('seconds_log',219,10)
                self.setword('rtc_pace',1,int(62500*shift)-1)
                self.setword('seconds_log',54,1)
                self.refresh();self.assertEqual(self.pad,[False,False])
                before=self.bt_count;steps=[0]
                # Two HCLK cycles/instruction stress approximation while the
                # real update executes; timer advances every eight instructions.
                def advance(*args):
                    steps[0]+=1
                    if steps[0]%8==0:self.advance_timer(1,dispatch=False)
                hook=self.cpu.hook_add(UC_HOOK_CODE,advance)
                try:self.call('pwm_update_normal_rate')
                finally:self.cpu.hook_del(hook)
                self.assertEqual(self.bt_count,before)
                self.assertEqual(self.word('seconds_log',54),0)
                self.assertEqual(self.pad,[False,False])
                self.assertNotEqual(self.reg(0x2c),p)
                self.assertFalse(self.overlaps)
                self.advance_timer(self.reg(0x2c)*3,dispatch=False)
                self.assertEqual(self.bt_count,before+3)

    def test_stop2go_changes_back_to_normal_hardware_pwm(self):
        self.start_pwm(3);self.complete_lap()
        self.setword('minute_log',188,0)
        self.setword('rtc_boundary',0,1);self.put(5,0)
        self.tick()
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('minute_log',189),0)
        self.assertEqual(self.word('seconds_log',218),1)
        self.assertEqual(self.raw(0x40012c2c),959)
        self.assertEqual(self.reg(0x28),15)

    def test_normal_overnight_hold_stops_at_boundary(self):
        self.start_pwm(1)
        self.bt_count=950;self.setword('seconds_log',219,950)
        self.setword('seconds_log',248,950)
        self.setword('seconds_log',251,890)
        self.setword('seconds_log',252,1)
        self.setword('seconds_log',254,960)
        self.setword('minute_log',192,2)
        for _ in range(120):
            self.tick()
            self.assertEqual(self.get(3),0)
            if self.get(30):break
        self.assertEqual(self.bt_count,960)
        self.assertEqual(self.get(30),1)
        self.assertFalse(self.gate())
        self.assertEqual(self.pad,[False,False])

    def test_normal_safe_fault_drain_across_wrap(self):
        self.start_pwm(1)
        self.bt_count=0;self.setword('seconds_log',219,959)
        self.setword('seconds_log',248,959)
        self.setword('seconds_log',251,890)
        self.setword('seconds_log',252,1)
        self.setword('seconds_log',254,960)
        self.call('fail',8)
        for _ in range(24):
            self.tick()
            self.assertEqual(self.get(3),8)
            if not self.word('seconds_log',218):break
        self.assertEqual(self.get(2),14)
        self.assertEqual(self.word('seconds_log',218),0)

    def test_phase_locked_sampler_gets_advisory_calibration_notification(self):
        self.start_pwm(0)
        p=self.word('minute_log',181)
        self.counter=p//2+1;self.down=False
        self.setword('rtc_pace',1,63749)
        self.setword('seconds_log',54,1)
        self.call('pwm_update_normal_rate')
        self.assertEqual(self.reg(0x0c)&16,16)
        self.assertEqual(self.reg(0x2c),p)
        before=self.bt_count
        self.advance_timer(2200)
        self.assertEqual(self.word('seconds_log',54),0)
        self.assertEqual(self.reg(0x0c),0)
        self.assertGreater(self.reg(0x2c),p)
        self.assertEqual(self.bt_count,before)
        self.assertEqual(self.pad,[False,False])

if __name__=='__main__':
    names=['test_all_modes_select_hardware_pwm',
           'test_normal_waveform_continues_across_three_hardware_wraps_without_cpu',
           'test_normal_calibration_changes_only_safe_gap_without_extra_counts',
           'test_phase_locked_sampler_gets_advisory_calibration_notification',
           'test_two_sampled_revolutions_in_each_normal_mode',
           'test_normal_mode_change_stops_at_hardware_960',
           'test_normal_drain_across_counter_wrap',
           'test_stop2go_changes_back_to_normal_hardware_pwm',
           'test_normal_overnight_hold_stops_at_boundary',
           'test_normal_safe_fault_drain_across_wrap',
           'test_sampled_lap_without_any_seconds_irq',
           'test_actual_sampling_outage_still_stops_with_snapshot',
           'test_missing_reference_still_stops',
           'test_native_rec_drain_enters_homing',
           'test_safe_fault_drains_before_gpio_parking',
           'test_timer_stall_watchdog_releases_coils']
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not r.wasSuccessful())
