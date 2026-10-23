"""Trial56 behaviour with only HC32 factory reference-to-home pulse counts."""
import unittest
import test_trial56_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_FACTORY_ALIGNMENT_TRIAL57_20261010.axf')
    signature=0x4d503537
    defines=[d for d in prior.Tests.defines if d!='-DCALIBRATED_ALIGNMENT']+['-DHC32_FACTORY_ALIGNMENT']
    minute_offset=49
    seconds_offset=68

def load_tests(loader,tests,pattern):
    names=[name for name in prior.Tests.__dict__ if name.startswith('test_')]
    names += ['test_scheduled_wake_at_non_hour_minute_and_success',
              'test_audit_missing_insufficient_cancelled',
              'test_audit_glitch_and_stuck_high_not_pass',
              'test_audit_parked_all_modes_minutes_continue',
              'test_button_mset_works_before_startup_homing_completes',
              'test_button_rec_can_park_without_time_and_locks_everything']
    return unittest.TestSuite(Tests(name) for name in names)

if __name__=='__main__': unittest.main()
