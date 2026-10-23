"""Compiled ARM phase-preserving release tests; no physical motor model."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'.analysis_deps'))
from check_rc6v_fixed_lap import Tests as Prior
from check_rc6w_startup_rtc import Tests as RTCRecovery
from unicorn import UC_HOOK_MEM_WRITE

ARTIFACT=Path(__file__).parent/'release_candidate_rc6x/build/MM32SPIN05PF_PHASE_RESUME_RC6X_20261022.axf'

class Tests(Prior):
    artifact=ARTIFACT
    signature=0x4d505281

    def test_release_does_not_write_pwm_or_motor_gpio_registers(self):
        self.start_pwm(3)
        self.complete_lap()
        frozen=self.counter, self.down, self.word('second_polarity')
        writes=[]
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,
            lambda c,a,address,size,value,u:writes.append((address,value)))
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        before=len(self.pad_edges)
        self.call('pwm_resume_lap')
        self.assertEqual(self.get(3),0)
        self.assertEqual((self.counter,self.down,self.word('second_polarity')),frozen)
        self.assertEqual(len(self.pad_edges),before)
        self.assertEqual(self.word('seconds_log',58),1)
        # Existing reference auditing can restore the shared optical sensor
        # selector on PB13/PB15. These are not motor outputs PB0/PA7.
        peripheral=[]
        for address,value in writes:
            if not 0x40000000<=address<0x50000000:continue
            if address==0x48000410:
                self.assertEqual(value & ~0xa000a000,0)
            else:peripheral.append((address,value))
        self.assertEqual(peripheral,[(0x40012c10,0),(0x40012c24,0)])
        self.assertTrue(self.gate())
        self.assertEqual(self.bt_count,0)

    def test_resumed_waveform_has_identical_width_spacing_and_polarity(self):
        for mode in (2,3):
            self.setUp();self.start_pwm(mode)
            p,w=self.pair()
            self.complete_lap()
            original=[e for e in self.pad_edges if e[2]]
            self.assertEqual(len(original),960)
            last_pin=original[-1][1]
            # Exercise small hardware gate synchronisation offsets too.
            for offset in (0,1,2):
                self.counter=self.reg(0x34)+offset
                self.down=False
                self.refresh()
                before=len(self.pad_edges)
                self.call('pwm_resume_lap')
                self.assertEqual(self.get(3),0)
                self.assertEqual(len(self.pad_edges),before)
                self.advance_timer(p*970,dispatch=False)
                events=self.pad_edges[before:]
                rises=[e for e in events if e[2]]
                falls=[e for e in events if not e[2]]
                self.assertEqual((len(rises),len(falls),self.bt_count),(960,960,960))
                self.assertNotEqual(rises[0][1],last_pin)
                self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
                self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{w})
                self.assertTrue(all(a[1]!=b[1] for a,b in zip(rises,rises[1:])))
                self.assertEqual(self.pad,[False,False])
                self.assertFalse(self.overlaps)
                # This test deliberately bypasses CPU observation. Prepare
                # only its completion count for the next isolated release.
                self.setword('seconds_log',219,960)
                last_pin=rises[-1][1]

    def test_invalid_release_is_rejected_and_coils_released(self):
        self.start_pwm(3)
        self.call('pwm_resume_lap') # A running lap must never be reset.
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.word('seconds_log',17),7)
        self.assertEqual(self.pad,[False,False])

class RTCTests(RTCRecovery):
    artifact=ARTIFACT
    signature=0x4d505281

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names += ['test_three_revolutions_in_both_stop_modes',
              'test_second_lap_keeps_first_pair_despite_new_calibration',
              'test_cached_pair_survives_mode_change_but_does_not_affect_normal',
              'test_rec_rehoming_clears_first_lap_cache',
              'test_all_modes_select_hardware_pwm',
              'test_stop2go_changes_back_to_normal_hardware_pwm',
              'test_normal_mode_change_stops_at_hardware_960',
              'test_missing_reference_still_stops',
              'test_timer_stall_watchdog_releases_coils',
              'test_sleep_closes_lease_without_reply_or_motor_change',
              'test_complete_time_is_preserved_and_processed_before_poweroff']
    rtc_names=['test_slave_held_sda_recovers_then_verifies_calendar',
               'test_permanently_held_sda_fails_bounded_and_releases_pins']
    suite=unittest.TestSuite([Tests(n) for n in names]+[RTCTests(n) for n in rtc_names])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
