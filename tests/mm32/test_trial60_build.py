"""Trial59, adjusting only seconds reference-to-home count to 70."""
import unittest
import test_trial59_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_ALIGNMENT_52_70_TRIAL60_20261010.axf')
    signature=0x4d503630
    defines=prior.Tests.defines+['-DSECONDS_ALIGNMENT_70']
    seconds_offset=70

def load_tests(loader,tests,pattern):
    names=['test_precise_minute_offset_across_six_entry_phases',
           'test_seconds_homing_and_runtime_use_same_offset',
           'test_rec_led_cadence_alternates_without_overlap',
           'test_rec_leds_stop_only_after_both_home_and_remain_off',
           'test_audit_calibrated_reference_geometry',
           'test_recovery_preserves_settings_and_completes_real_homing']
    return unittest.TestSuite(Tests(n) for n in names)

if __name__=='__main__': unittest.main()
