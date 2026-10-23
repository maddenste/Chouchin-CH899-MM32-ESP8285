"""RC6R focused regressions against the RC6S compact RAM layout."""
import unittest
from pathlib import Path
from check_rc6q_uart_sleep import Tests as Prior

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6s/build/MM32SPIN05PF_STACK_RC6S_20261022.axf'
    signature=0x4d50527c

if __name__=='__main__':
    names=['test_sleep_parser_accepts_only_complete_uppercase_command',
           'test_sleep_closes_lease_without_reply_or_motor_change',
           'test_complete_time_is_preserved_and_processed_before_poweroff',
           'test_sleep_without_time_finishes_unsuccessful_daily_wake',
           'test_clean_defers_sleep_and_new_wake_discards_old_request',
           'test_all_modes_select_hardware_pwm',
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
