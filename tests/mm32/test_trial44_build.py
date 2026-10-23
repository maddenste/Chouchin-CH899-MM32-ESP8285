"""Trial43 unchanged except one-time reset autostart."""
import unittest
import test_trial43_build as prior
import test_reference_scan_build as ref


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_AUTOSTART_TRIAL44_20261009.axf'
    signature = 0x4d503434
    defines = prior.Tests.defines + ['-DAUTOSTART']

    def test_reset_arms_and_first_tick_starts_without_command_write(self):
        self.assertEqual((self.get(0), self.get(1), self.get(2)),
                         (self.signature, 1, 0))
        self.tick()
        self.assertEqual((self.get(1), self.get(2), self.get(3)), (1, 1, 0))
        self.assertTrue(self.output & 16)
        self.assertEqual(self.get(28), 1)
        for _ in range(16): self.tick()
        self.assertGreater(self.get(20), 0)
        self.assertGreater(self.get(21), 0)

    def test_abort_does_not_autorestart(self):
        self.tick(); self.put(1, 0); self.tick()
        self.assertEqual((self.get(2), self.get(3)), (6, 2))
        self.released()
        for _ in range(128): self.tick()
        self.assertEqual((self.get(1), self.get(2), self.get(3)), (0, 6, 2))
        self.assertFalse(self.output & 16)


if __name__ == '__main__': unittest.main()
