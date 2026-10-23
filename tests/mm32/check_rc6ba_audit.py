"""RC6BA compiled ARM audit regressions. Timer/RTC models, no hardware access."""
import sys
import unittest
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PRIMASK
from elftools.elf.elffile import ELFFile
from check_rc6az_immediate_set import Tests as Immediate, Buttons as PriorButtons
from check_rc6ay_second_sync import Tests as Phase
from audit_rc6ac_final import Tests as AuditPrior, RTCChecks as RTCPrior, RecoveryChecks as RecoveryPrior

ARTIFACT=Path(__file__).parent/'release_candidate_rc6ba/build/MM32SPIN05PF_AUDITED_RC6BA_20261023.axf'

class Tests(Immediate):
    artifact=ARTIFACT
    signature=0x4d50529e
    urgent_word=186

    def test_overnight_audit_status_never_becomes_correction_request(self):
        for status in range(1,7):
            with self.subTest(status=status):
                self.setUp();self.start_pwm(3)
                self.put(16,23);self.put(15,45);self.put(5,30)
                self.fixture_clock()
                self.setword('minute_log',195,1)
                self.setword('minute_log',202,1)
                self.setword('minute_log',201,1)
                self.setword('minute_log',160,status)
                self.setword('daily_log',0,1);self.setword('daily_log',13,0)
                epoch=self.word('seconds_log',215)
                for _ in range(4):self.tick()
                self.assertEqual(self.word('minute_log',self.urgent_word),0)
                self.assertEqual(self.word('seconds_log',220),0)
                self.assertEqual(self.word('seconds_log',215),epoch)
                self.assertEqual(self.word('minute_log',160),status)
                self.assertEqual(self.get(3),0)

    def test_audit_initialisation_does_not_erase_urgent_drain(self):
        self.moving_update()
        self.setword('minute_log',202,0)
        self.call('audit_tick',self.get(4),7)
        self.assertEqual(self.word('minute_log',self.urgent_word),1)
        self.assertEqual(self.word('minute_log',160),0)
        self.finish_immediate()

    def test_daily_finish_preserves_alignment_audit_result(self):
        self.start_pwm()
        self.setword('minute_log',160,3)
        self.setword('minute_log',self.urgent_word,2)
        self.call('daily_finish',3,123456)
        self.assertEqual(self.word('minute_log',self.urgent_word),0)
        self.assertEqual(self.word('minute_log',160),3)

    def test_takeover_at_final_commit_mask_cannot_be_overwritten(self):
        for owner in (229,230,190):
            with self.subTest(owner=owner):
                self.setUp();self.moving_update()
                for _ in range(32):
                    self.tick()
                    if self.word('minute_log',self.urgent_word)==2:break
                with self.artifact.open('rb') as stream:
                    elf=ELFFile(stream)
                    symbol=elf.get_section_by_name('.symtab').get_symbol_by_name('daily_poll')[0]
                    start=symbol['st_value']&~1;end=start+symbol['st_size']
                masks=[a for a in range(start,end,2)
                       if bytes(self.cpu.mem_read(a,2))==b'\x72\xb6']
                self.assertTrue(masks)
                # The last daily_poll CPSID is its post-I2C commit boundary.
                target=masks[-1];injected=[]
                def takeover(cpu,address,size,user):
                    if injected:return
                    injected.append(address)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_PRIMASK),0)
                    self.setword('minute_log',owner,1)
                    if owner==229:
                        self.put(2,1);self.setword('daily_log',0,0)
                        self.setword('daily_log',13,0)
                        self.setword('minute_log',self.urgent_word,0)
                hook=self.cpu.hook_add(UC_HOOK_CODE,takeover,begin=target,end=target)
                self.cpu.ctl_remove_cache(0x08000000,0x08008000)
                self.call('daily_poll');self.cpu.hook_del(hook)
                self.assertTrue(injected)
                self.assertEqual(self.word('minute_log',204),0)
                self.assertEqual(self.word('minute_log',owner),1)
                self.assertEqual(self.word('wifi_rtc',15),1)
                self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),0)

    def test_admission_checks_motor_state_under_interrupt_mask(self):
        source,due=self.admit(delta=60)
        observed=[]
        address=self.symbols['minute_active']
        from unicorn import UC_HOOK_MEM_READ
        def read(cpu,access,where,size,value,user):
            observed.append(cpu.reg_read(UC_ARM_REG_PRIMASK))
        hook=self.cpu.hook_add(UC_HOOK_MEM_READ,read,begin=address,end=address)
        self.reach(source,due)
        self.cpu.hook_del(hook)
        self.assertTrue(observed);self.assertTrue(all(observed))
        self.assertEqual(self.word('wifi_rtc',15),1)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),0)
        for state in ('powered','queued','partial','rec','clean','restart'):
            self.setUp();source,due=self.admit(delta=60)
            before=len(self.bus.calendar_writes)
            if state=='powered':self.setword('minute_active',0,1)
            if state=='queued':self.setword('request_pulses',0,1)
            if state=='partial':self.setword('minute_log',191,1)
            if state=='rec':self.setword('minute_log',229,1)
            if state=='clean':self.setword('minute_log',230,1)
            if state=='restart':self.setword('minute_log',190,1)
            self.reach(source,due)
            self.assertEqual(len(self.bus.calendar_writes),before,state)
            self.assertEqual(self.word('daily_log',13),1)

    def test_error6_setup_accepts_new_time_only_for_reset_not_motion(self):
        self.start_pwm();self.call('motors_off')
        self.put(2,6);self.put(3,6)
        self.setword('minute_log',211,1)
        self.setword('ap_recovery',0,2)
        self.setword('ap_recovery',7,self.word('uart_probe_good_time'))
        writes,hook=self.trace();before=self.word('uart_probe_good_time')
        self.consume(self.wire_record())
        self.assertEqual(self.word('uart_probe_good_time'),before+1)
        self.assertEqual(self.get(2),6)
        self.assertFalse(any(self.pad))
        self.call('ap_recovery_poll')
        self.cpu.hook_del(hook)
        self.assertEqual(self.word('ap_recovery',0),3)
        self.assertEqual([(a,v) for a,v in writes if a==0xe000ed0c],[(0xe000ed0c,0x05fa0004)])
        self.assertFalse([(a,v) for a,v in writes if a in (0x40000400,0x40000414)])

    def test_other_faults_and_rec_cannot_publish_recovery_time(self):
        for fault,state,rec in [(n,2,0) for n in range(1,11) if n!=6]+[(6,1,0),(6,2,1)]:
            with self.subTest(fault=fault,state=state,rec=rec):
                self.setUp();self.start_pwm();self.call('motors_off')
                self.put(2,6);self.put(3,fault)
                self.setword('ap_recovery',0,state)
                self.setword('minute_log',229,rec)
                count=self.word('uart_probe_good_time');self.consume(self.wire_record())
                self.assertEqual(self.word('uart_probe_good_time'),count)

class Buttons(PriorButtons):
    artifact=ARTIFACT
    signature=Tests.signature

class General(Tests, AuditPrior):
    artifact=ARTIFACT
    signature=Tests.signature

class RTCChecks(Tests, RTCPrior):
    artifact=ARTIFACT
    signature=Tests.signature

class RecoveryChecks(RecoveryPrior):
    artifact=ARTIFACT
    signature=Tests.signature

def cases():
    names=[n for cls in (Tests,Immediate,Phase) for n in cls.__dict__ if n.startswith('test_')]
    names += ['test_rec_rehome_preserves_rtc_sampling_words',
              'test_first_postwrite_wrong_hour_rejected_all_modes',
              'test_transient_bad_read_recovers_without_reseed_or_phase_change',
              'test_first_advancing_read_is_rate_anchor_not_new_civil_phase',
              'test_three_wrong_reads_fault_without_adopting_wrong_hour',
              'test_startup_still_seeds_and_aligns_first_edge',
              'test_echo_exact_complete_record_only_after_settings_processed',
              'test_sleep_closes_lease_without_reply_or_motor_change',
              'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
              'test_bad_incomplete_and_non_time_lines_do_not_echo',
              'test_stop_modes_first_pulse_normal_then32_safe_updates',
              'test_boot_burst_counted_rejected_but_never_arms_recovery',
              'test_clean_time_cancels_pending_recovery_and_echoes',
              'test_idle_recovery_reconfigures_uart_not_motor_or_clocks',
              'test_recovery_defers_in_unsafe_or_busy_conditions']
    result=[Tests(n) for n in names]
    result.append(Buttons('test_mset_wakes_during_each_correction_stage_without_motor_changes'))
    general=[n for n in AuditPrior.__dict__ if n.startswith('test_')]
    general += ['test_all_twelve_style_changes_request_reset_without_live_switch',
                'test_coarse_homing_pulse_finishes_before_reset',
                'test_fresh_boot_accepts_new_saved_style_without_another_restart',
                'test_sleep_parser_accepts_only_complete_uppercase_command',
                'test_clean_defers_sleep_and_new_wake_discards_old_request',
                'test_normal_drain_across_counter_wrap',
                'test_actual_sampling_outage_still_stops_with_snapshot',
                'test_timer_stall_watchdog_releases_coils',
                'test_native_rec_drain_enters_homing']
    result += [General(n) for n in general]
    result += [RTCChecks('test_real_reset_initializes_relocated_state_and_preserves_stack_reservation'),
               RTCChecks('test_compact_calendar_failures_restore_bus'),
               RecoveryChecks('test_permanently_held_sda_fails_bounded_and_releases_pins'),
               RecoveryChecks('test_permanently_held_scl_fails_bounded_and_releases_pins'),
               RecoveryChecks('test_wrong_pin_modes_are_not_overridden')]
    return result

if __name__=='__main__':
    selected=cases()
    if '--new' in sys.argv:selected=[Tests(n) for n in Tests.__dict__ if n.startswith('test_')]
    if '--motor' in sys.argv:
        selected=[Tests(n) for n in (
            'test_normal_modes_keep_original_waveforms_and_no_ramp',
            'test_two_laps_and_normal_launch_again_after_hold',
            'test_late_ramp_irq_does_not_change_active_pulse',
            'test_overnight_stop_mode_resumes_with_ramp_without_second_timer_launch',
            'test_always_parked_never_launches_seconds_during_catchup_all_styles',
            'test_always_parked_runtime_minute_width_is_valid_without_seconds_launch',
            'test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
            'test_saver_change_alone_finishes_one_safe_restart')]
    if '--part=1' in sys.argv:selected=selected[::2]
    if '--part=2' in sys.argv:selected=selected[1::2]
    outcome=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
    raise SystemExit(not outcome.wasSuccessful())
