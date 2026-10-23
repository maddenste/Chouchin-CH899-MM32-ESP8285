"""Read-only RC6AC audit checks. No firmware patch, flash or publishing."""
import unittest
from check_rc6ac_normal_resume import Tests as Base
from check_rc6s_rtc import Tests as RTCBase
from check_rc6w_startup_rtc import Tests as RecoveryBase
from unicorn import UC_HOOK_MEM_WRITE

class Tests(Base):
    def test_complete_settings_pair_is_latched_and_same_pair_does_not_reset(self):
        self.test_first_boot_latches_each_style_saver_pair_without_reset()

    def test_bad_and_truncated_uart_records_do_not_change_settings(self):
        self.start_pwm(3)
        good=b'+TIME:Thu Oct 22 14:20:30 2026 +0100 10:00 30\r\n'
        samples=[good[:-1],good.replace(b'Oct 22',b'Feb 30'),
                 good.replace(b'14:20',b'24:20'),good.replace(b' 30\r',b' 39\r'),
                 b'junk\n',b'A'*110+b'\r\n']
        for data in samples:
            # Clear an unfinished previous record through a rejected newline.
            self.call('uart_probe_consume',10)
            before=(self.word('minute_log',189),self.word('minute_log',192),self.word('minute_log',190))
            for b in data:self.call('uart_probe_consume',b)
            self.assertEqual(before,(self.word('minute_log',189),self.word('minute_log',192),self.word('minute_log',190)))

    def test_fault_led_counts_codes_1_to_10_with_ten_second_gap(self):
        for code in range(1,11):
            self.setUp();self.put(3,code);self.call('parallel_leds_fault_start',0)
            end=(code-1)*64+8;starts=[];previous=False
            for tick in range(end+1281):
                self.call('parallel_leds_tick',tick)
                on=bool(self.raw(0x48000010)&(1<<31))
                self.assertEqual(on,bool(self.raw(0x48000410)&(1<<19)))
                if on and not previous:starts.append(tick)
                if end<=tick<end+1280:self.assertFalse(on)
                previous=on
            self.assertEqual(starts,[64*i for i in range(code)]+[end+1280])

    def test_unsafe_fault_stops_motion_and_leaves_only_indicator_ticks(self):
        self.start_pwm(0);self.call('fail',5)
        self.assertEqual((self.get(2),self.get(3)),(6,5))
        self.assertEqual(self.pad,[False,False])
        self.assertEqual(self.word('minute_log',211),0)
        before=(self.get(12),self.get(13),self.word('rtc_pace',5),self.word('seconds_log',227))
        for _ in range(32):self.tick()
        self.assertEqual(before,(self.get(12),self.get(13),self.word('rtc_pace',5),self.word('seconds_log',227)))

class RTCChecks(RTCBase):
    artifact=Base.artifact
    signature=Base.signature

class RecoveryChecks(RecoveryBase):
    artifact=Base.artifact
    signature=Base.signature

class Findings(Base):
    """Expected reproductions of BAD behaviour, not release acceptance checks."""
    def acquisition(self,saver,style=3):
        self.start_pwm(style);self.call('fine_stop')
        self.setword('minute_log',192,saver)
        self.put(16,5);self.put(15,0);self.put(5,0);self.fixture_clock()
        self.put(30,0);self.put(26,0);self.put(7,1);self.put(8,1)
        self.put(22,0) # Minute hand has just homed to 12; target is 05:00.
        self.setword('seconds_log',56,0);self.setword('seconds_log',57,0)
        self.setword('seconds_log',255,0);self.setword('minute_log',185,0)
        self.call('catchup_begin',self.get(4));self.setword('rtc_boundary',0,1)

    def test_reproduces_always_parked_seconds_pwm_launch_during_catchup(self):
        for style in range(4):
            self.setUp();self.acquisition(2,style);self.tick()
            self.assertEqual(self.get(2),10)
            self.assertEqual(self.get(3),0)
            self.assertEqual(self.word('minute_log',192),2)
            self.assertTrue(self.reg(0)&1) # BUG: seconds waveform starts.
            self.assertTrue(self.gate())

    def test_reproduces_second_overnight_rotation_and_pwm_rebuild_during_catchup(self):
        self.acquisition(1)
        launches=[]
        def write(cpu,access,address,size,value,user):
            if address==0x40000414 and value==1:launches.append(self.get(4))
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,write)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        for _ in range(9000):
            self.tick(int(888<=self.bt_count<900))
            self.assertEqual(self.get(3),0)
            if len(launches)>=2 and self.bt_count>1:break
        self.assertEqual(self.get(2),10)
        self.assertEqual(self.get(16),5)
        self.assertEqual(self.word('seconds_log',255),1)
        self.assertEqual(len(launches),2) # BUG: rebuilt instead of overnight hold.
        self.assertGreater(self.bt_count,1) # Second revolution is under way.

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_all_twelve_style_changes_request_reset_without_live_switch',
            'test_coarse_homing_pulse_finishes_before_reset',
            'test_fresh_boot_accepts_new_saved_style_without_another_restart',
            'test_sleep_parser_accepts_only_complete_uppercase_command',
            'test_clean_defers_sleep_and_new_wake_discards_old_request',
            'test_normal_drain_across_counter_wrap',
            'test_actual_sampling_outage_still_stops_with_snapshot',
            'test_timer_stall_watchdog_releases_coils',
            'test_native_rec_drain_enters_homing']
    suite=unittest.TestSuite([Tests(n) for n in names]+[
        RTCChecks('test_real_reset_initializes_relocated_state_and_preserves_stack_reservation'),
        RTCChecks('test_compact_calendar_failures_restore_bus'),
        RecoveryChecks('test_permanently_held_sda_fails_bounded_and_releases_pins'),
        RecoveryChecks('test_permanently_held_scl_fails_bounded_and_releases_pins'),
        RecoveryChecks('test_wrong_pin_modes_are_not_overridden')])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
