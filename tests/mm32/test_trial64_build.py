"""Trial63 with CPU Sleep suppressed for the entire ESP awake session."""
import unittest
import test_trial63_build as prior

class Tests(prior.Tests):
    artifact=prior.Tests.artifact.with_name('MM32SPIN05PF_SLEEP_ESP_GUARD_TRIAL64_20261010.axf')
    signature=0x4d503634
    defines=prior.Tests.defines+['-DCPU_SLEEP_ESP_GUARD']

    def test_sleep_esp_awake_blocks_wait_even_without_time(self):
        self.setword('minute_log',211,1)
        self.setword('minute_log',212,0)
        before=self.word('seconds_log',214)
        self.assertEqual(self.idle(),[])
        self.assertEqual(self.word('seconds_log',214),before)

    def test_sleep_esp_valid_time_does_not_end_guard(self):
        self.setword('minute_log',211,1)
        self.setword('minute_log',212,1)
        self.assertEqual(self.idle(),[])
        self.setword('minute_log',211,0)
        self.assertEqual(self.idle(),[1])

    def test_sleep_radio_session_lifecycle(self):
        self.call('radio_on')
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(self.idle(),[])
        self.call('radio_off')
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.idle(),[1])

if __name__=='__main__': unittest.main()
