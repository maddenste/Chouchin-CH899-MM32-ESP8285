"""Trial58 REC LEDs, with 52 minute and 68 seconds reference offsets."""
import unittest
import test_trial58_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_ALIGNMENT_52_68_TRIAL59_20261010.axf')
    signature=0x4d503539
    defines=[d for d in prior.Tests.defines if d!='-DHC32_FACTORY_ALIGNMENT']+['-DMIXED_ALIGNMENT']
    minute_offset=52
    seconds_offset=68

def load_tests(loader,tests,pattern):
    names=[n for n in prior.Tests.__dict__ if n.startswith('test_')]
    names += ['test_precise_minute_offset_across_six_entry_phases',
              'test_seconds_homing_and_runtime_use_same_offset',
              'test_audit_calibrated_reference_geometry',
              'test_audit_only_at_midnight',
              'test_scheduled_matching_time_keeps_blue_confirmation_on_recovery',
              'test_recovery_preserves_settings_and_completes_real_homing',
              'test_button_rec_can_park_without_time_and_locks_everything',
              'test_calibrated_all_modes_keep_complete_minute_markers']
    return unittest.TestSuite(Tests(n) for n in names)

if __name__=='__main__': unittest.main()
