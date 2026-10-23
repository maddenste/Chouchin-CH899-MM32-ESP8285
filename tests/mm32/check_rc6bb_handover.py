"""RC6BB compiled ARM regressions; no target connection or physical model."""
import sys
import unittest
from pathlib import Path
import check_rc6ba_audit as baseline
from unicorn import UC_HOOK_MEM_WRITE

IMAGE=Path(__file__).resolve().parents[2]/'firmware/mm32/build/MM32SPIN05PF_HANDOVER_RC6BB_20261023.axf'
for cls in (baseline.Tests,baseline.Buttons,baseline.General,baseline.RTCChecks,baseline.RecoveryChecks):
    cls.artifact=IMAGE
    cls.signature=0x4d50529f

class Handover(baseline.Tests):
    def prepare(self,phase=17000,down=False):
        self.held_fixture(3)
        self.counter=phase; self.down=down; self.refresh()
        self.put(30,0); self.call('parallel_seconds_runtime_begin')
        self.call('pwm_resume_lap')

    def test_request_never_opens_outputs_at_any_start_phase(self):
        for phase,down in ((15000,False),(15881,False),(17000,False),(19000,False),(17000,True)):
            with self.subTest(phase=phase,down=down):
                self.setUp(); self.prepare(phase,down)
                self.assertEqual(self.reg(0x20),0)
                self.assertEqual(self.word('seconds_log',61),1)
                slot=self.reg(0x40)
                commits=[]
                hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,
                    lambda c,a,address,size,value,u: commits.append((self.counter,self.down))
                    if address==0x40000420 and value==0x110 else None,
                    begin=0x40000420,end=0x40000423)
                self.cpu.ctl_remove_cache(0x08000000,0x08008000)
                self.settle_release()
                self.cpu.hook_del(hook)
                self.assertEqual(commits,[(slot,False)])
                self.assertEqual(self.word('seconds_log',61),0)
                self.assertEqual(self.reg(0x20),0x110)
                self.assertEqual(self.get(3),0)

    def test_late_or_downcount_irq_stays_off_then_recovers(self):
        for phase,down in ((17000,False),(15881,True)):
            self.setUp();self.prepare()
            self.counter=phase;self.down=down;self.refresh()
            self.store(0x40000410,self.reg(0x10)|16)
            self.call('TIM3_Handler')
            self.assertEqual(self.reg(0x20),0)
            self.assertEqual(self.word('seconds_log',61),1)
            self.settle_release()
            self.assertEqual(self.reg(0x20),0x110)

    def test_queued_minute_is_deferred_not_discarded(self):
        self.held_fixture(3)
        self.setword('request_pulses',0,3)
        self.call('pwm_minutes_queue')
        self.assertEqual(self.word('release_state',2),1)
        self.put(30,0);self.call('parallel_seconds_runtime_begin');self.call('pwm_resume_lap')
        self.assertEqual(self.word('release_state',2),0)
        self.call('pwm_minutes_queue')
        self.assertEqual(self.word('release_state',2),0)
        self.assertEqual(self.word('request_pulses'),3)
        self.settle_release();self.call('pwm_minutes_queue')
        self.assertEqual(self.word('release_state',2),1)

    def test_safety_drain_cancels_pending_release(self):
        self.prepare();self.call('pwm_drain')
        self.advance_timer(31250*3)
        self.assertEqual(self.reg(0x20),0)
        self.assertEqual(self.word('seconds_log',61),0)

    def test_new_calibration_does_not_rewrite_seconds_handover(self):
        self.prepare()
        normal=self.word('seconds_log',66)
        self.setword('rtc_pace',1,62510)
        self.setword('release_state',1,17)
        self.settle_release()
        self.assertEqual(self.pair(),(normal,2*((normal*3+4)//8)))
        self.assertEqual(self.get(3),0)

if __name__=='__main__':
    if '--focused' in sys.argv:
        suite=unittest.defaultTestLoader.loadTestsFromNames([
            'Handover.'+n for n in Handover.__dict__ if n.startswith('test_')],module=sys.modules[__name__])
    else:
        selected=baseline.cases()
        if '--motor' in sys.argv:
            selected=[baseline.Tests(n) for n in (
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
        suite=unittest.TestSuite(selected)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
