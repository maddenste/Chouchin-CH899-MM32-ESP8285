"""RC6N: native ARM hardware-count polling and sampled sensor regressions."""
import unittest
from pathlib import Path
from check_rc6l_autonomous import Tests as TimerModel
from check_rc6k_quartz import Tests as Quartz

class Tests(TimerModel):
    artifact=Path(__file__).parent/'release_candidate_rc6n/build/MM32SPIN05PF_AUTONOMOUS_PWM_RC6N_20261022.axf'
    signature=0x4d505277

    def complete_lap(self,window=(888,900)):
        for _ in range(8000):
            self.tick(int(window[0]<=self.bt_count<window[1]))
            self.assertEqual(self.get(3),0,(self.bt_count,self.word('seconds_log',248)))
            if self.get(30):break
        self.assertEqual(self.bt_count,960)
        self.assertEqual(self.word('seconds_log',248),960)
        self.assertEqual(self.word('seconds_log',219),960)
        self.assertEqual(self.reg(0x0c),0)
        self.assertEqual(self.get(3),0)

    def test_sampled_lap_without_any_seconds_irq(self):
        self.start_pwm()
        self.complete_lap()
        self.assertEqual(self.word('seconds_log',251),890)
        self.assertEqual(self.word('seconds_log',254),960)
        self.assertEqual(self.word('seconds_log',255),1)
        self.assertEqual(self.pad,[False,False])
        self.assertFalse(self.overlaps)
        rises=[e[0] for e in self.pad_edges if e[2]]
        self.assertEqual(len(rises),960)
        self.assertEqual(set(b-a for a,b in zip(rises,rises[1:])),{self.word('minute_log',181)})

    def test_flags_can_stay_high_without_blocking_sampling(self):
        self.start_pwm()
        for _ in range(500):
            self.sr|=2
            self.tick()
            self.assertEqual(self.get(3),0)
        self.assertGreater(self.word('seconds_log',219),50)
        self.assertEqual(self.word('seconds_log',214),0)
        self.assertEqual(self.reg(0x0c),0)

    def test_actual_sampling_outage_still_stops_with_snapshot(self):
        self.start_pwm()
        self.advance_timer(self.word('minute_log',181)*3,dispatch=False)
        self.tick()
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',17),1)
        self.assertEqual(self.pad,[False,False])

    def test_missing_reference_still_stops(self):
        self.start_pwm()
        for _ in range(8000):
            self.tick()
            if self.get(3):break
        self.assertEqual(self.get(3),5)
        self.assertEqual(self.bt_count,960)
        self.assertEqual(self.pad,[False,False])

    def test_three_revolutions_in_both_stop_modes(self):
        for mode in (2,3):
            self.setUp();self.start_pwm(mode)
            for lap in range(3):
                self.complete_lap()
                self.assertEqual(self.word('seconds_log',255),lap+1)
                self.assertEqual(self.pad,[False,False])
                if lap<2:
                    for _ in range(512):
                        self.tick()
                        self.assertEqual(self.get(3),0,(mode,lap,'hold'))
                        if not self.get(30):break
                    self.assertEqual(self.get(30),0)
                    self.assertTrue(self.gate())
            self.assertEqual(self.get(12),2880)
            self.assertGreaterEqual(self.get(13),12)

    def test_late_reference_phase_is_observed_not_a_timer_fault(self):
        self.start_pwm()
        # Start polling at different sub-pulse phase, still under one 128 Hz
        # tick. Compare IRQ suppression remains permanent for the whole lap.
        self.advance_timer(1500,dispatch=False)
        self.complete_lap((892,904))
        self.assertEqual(self.word('seconds_log',254),964)
        # The passive audit marks a qualified, held reference as retained (4).
        self.assertIn(self.word('minute_log',196),(2,4))
        self.assertEqual(self.word('minute_log',198),4)

    def test_spurious_seconds_irq_does_not_consume_count(self):
        self.start_pwm()
        for _ in range(128):
            self.sr|=2
            before=self.word('seconds_log',219)
            self.call('TIM3_Handler')
            self.assertEqual(self.word('seconds_log',219),before)
            self.tick()
            self.assertEqual(self.get(3),0)

    def test_long_sensor_high_still_stops(self):
        self.start_pwm()
        for _ in range(8000):
            self.tick(int(self.bt_count>=888))
            if self.get(3):break
        self.assertEqual(self.get(3),5)
        self.assertLess(self.bt_count,960)
        self.assertEqual(self.pad,[False,False])

if __name__=='__main__':
    names=['test_sampled_lap_without_any_seconds_irq',
           'test_flags_can_stay_high_without_blocking_sampling',
           'test_actual_sampling_outage_still_stops_with_snapshot',
           'test_missing_reference_still_stops',
           'test_three_revolutions_in_both_stop_modes',
           'test_late_reference_phase_is_observed_not_a_timer_fault',
           'test_spurious_seconds_irq_does_not_consume_count',
           'test_long_sensor_high_still_stops',
           'test_hardware_generates_and_stops_960_without_any_interrupt',
           'test_minutes_continue_while_seconds_parked',
           'test_rec_drain_and_stop_return_gpio_ownership',
           'test_normal_modes_remain_same_waveforms',
           'test_catchup_and_runtime_handover_preserve_seconds_af',
           'test_timer_stall_watchdog_releases_coils',
           'test_native_rec_drain_enters_homing',
           'test_boundary_mode_switches_enter_and_leave_pwm',
           'test_safe_fault_drains_before_gpio_parking',
           'test_quartz_and_calendar_coexist_in_size_optimised_build',
           'test_parked_audit_can_probe_and_restores_seconds',
           'test_full_hardware_budget_across_rates_and_start_polarities']
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not r.wasSuccessful())
