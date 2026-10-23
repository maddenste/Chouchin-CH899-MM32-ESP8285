"""RC6G: normal electrical engine, faster fixed Stop2Go interval, :00 hold.

Historical expected values are updated explicitly below, without removing
their safety/sequence assertions. Old waveform equivalence applies to normal
modes only; new all-mode width and fixed-lap tests cover the intended change.
"""
import inspect
import struct
import textwrap
import unittest
from pathlib import Path
from test_rc6f_gpio import Tests as RC6F
from test_rc6d_fixed import Tests as RC6D
from test_rc6e_diag import Tests as RC6E
from test_rc6_motor_guard import Tests as Guard
from test_release_candidate_build import Tests as Release
from elftools.elf.elffile import ELFFile
from intelhex import IntelHex
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP


class Tests(RC6F):
    artifact = RC6F.artifact.parent.parent.parent / 'release_candidate_rc6g/build/MM32SPIN05PF_NORMAL_ENGINE_RC6G_20261021.axf'
    signature = 0x4d505270
    fine_spacing_sets = ({15104},)

    @staticmethod
    def fixed_interval(rate, residue=0):
        return ((rate * 1024 + residue) * 29 + 61440) // 122880

    def test_gpio_exact_source_scope(self):
        root = Path(__file__).parent
        old, new = root/'release_candidate_rc6f/src', root/'release_candidate_rc6g/src'
        changes = set()
        self.assertEqual({p.relative_to(old) for p in old.rglob('*') if p.is_file()},
                         {p.relative_to(new) for p in new.rglob('*') if p.is_file()})
        for p in new.rglob('*'):
            if p.is_file() and p.read_bytes() != (old/p.relative_to(new)).read_bytes():
                changes.add(p.name)
        self.assertEqual(changes, {'fine_stop2go.h', 'startup.c', 'parallel_home_main.c'})

    def test_normal_identical_to_rc6f_gpio_waveforms(self):
        RC6F.setUpClass()
        for mode in (0, 1):
            for rate in (50000, 62500, 63108, 75000):
                old = RC6F(); old.setUp(); self.setUp()
                for t in (old, self):
                    t.setword('rtc_pace', 1, rate-1)
                    t.setword('release_state', 1, 777)
                    t.mode_run(mode)
                    t.setword('request_pulses', 0, 6)
                    t.call('fine_minutes_rise', t.counter)
                    t.advance_timer(t.word('minute_log', 181)*128)
                self.assertEqual(self.edges, old.edges)
                self.assertEqual(self.reg(0x28), 31)

    def test_normal_all_modes_share_divider_and_drive_widths(self):
        for rate in (50000, 62500, 63108, 75000):
            widths = []
            for mode in range(4):
                self.setUp(); self.setword('rtc_pace', 1, rate-1)
                self.mode_run(mode)
                self.assertEqual(self.reg(0x28), 31)
                widths.append(tuple(self.word('minute_log', i) for i in (182, 183, 184)))
                self.assertLess(widths[-1][0], self.word('minute_log', 181))
            self.assertEqual(widths, [widths[0]]*4)
        self.assertEqual(self.fixed_interval(62500), 15104)
        self.assertAlmostEqual(15104*960/250000, 57.999360)
        self.assertAlmostEqual((959*15104+11719)/250000, 57.985820)

    def test_normal_calibration_does_not_retime_widths_at_hold_release(self):
        self.mode_run(3)
        widths = tuple(self.word('minute_log', i) for i in (182, 183, 184))
        epoch = self.word('seconds_log', 215)
        self.advance_timer((self.reg(0x38)-self.counter)&65535)
        self.reg(0x0c, 0); self.put(30, 1); self.put(5, 0)
        self.setword('rtc_pace', 1, 63475)
        self.setword('rtc_boundary', 0, 1); self.tick()
        self.assertEqual(self.word('minute_log', 181), self.fixed_interval(63476))
        self.assertEqual(tuple(self.word('minute_log', i) for i in (182, 183, 184)), widths)
        self.assertEqual(self.word('seconds_log', 215), epoch)
        self.assertEqual(self.get(3), 0)

    def test_normal_dirty_sram_real_reset_initializes_diagnostics(self):
        # Deliberately do not preload ELF RAM segments as the older harness did.
        flash = IntelHex(str(self.artifact.with_suffix('.hex')))
        for pattern in (0xa5, 0x01, 0x02, 0xff):
            cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
            cpu.mem_map(0x08000000, 0x10000); cpu.mem_map(0x20000000, 0x1000)
            cpu.mem_write(0x20000000, bytes([pattern])*4096)
            for start, end in flash.segments():
                cpu.mem_write(start, bytes(flash.tobinarray(start=start, end=end-1)))
            reached = []
            def main(cpu, address, size, user):
                if address == (self.symbols['main'] & ~1):
                    reached.append(True); cpu.emu_stop()
            cpu.hook_add(UC_HOOK_CODE, main)
            cpu.reg_write(UC_ARM_REG_SP, 0x20001000)
            cpu.emu_start(self.symbols['Reset_Handler'], 0x08008000, count=100000)
            self.assertTrue(reached)
            self.assertEqual(bytes(cpu.mem_read(0x20000c40, 160)), bytes(160))
        self.mode_run(3)
        self.assertEqual(self.word('pulse_diag', 1), 0x45444745)
        self.assertEqual(self.word('pulse_diag', 2), 1)


def adapt(owner, name, replacements):
    """Keep an inherited test body and assertions; change declared expectations.

    This avoids editing historical/rollback suites and fails if a specified
    replacement ever stops matching. No firmware or binary is transformed.
    """
    original = getattr(owner, name)
    source = textwrap.dedent(inspect.getsource(original))
    for old, new in replacements:
        assert old in source, (name, old)
        source = source.replace(old, new)
    scope = dict(original.__globals__)
    exec(compile(source, '<RC6G expectations: '+name+'>', 'exec'), scope)
    setattr(Tests, name, scope[name])


adapt(RC6D, 'test_constant_spacing_and_width_over_counter_wraps', [('3754', '15104'), ('2816', '11719')])
adapt(RC6D, 'test_release_catchup_uniform_while_seconds_run_all_modes', [
    ('62500 if mode & 2 else 250000', '250000'), ('(3754,)', '(15104,)')])
adapt(Release, 'test_release_catchup_finishes_whole_markers_without_seconds_restart', [
    ('62500 if mode&2 else 250000', '250000')])
adapt(Release, 'test_minute_overlap_does_not_change_seconds_spacing', [
    ('{3906}', '{15625}')])
adapt(Release, 'test_late_timer_fault_cannot_burst_or_reenergize', [
    ('+1200)', '+4800)')])  # Preserve the original 19.2-ms injected lateness.
for name in ('test_release_startup_latest_time_mode_before_first_pulse',
             'test_release_actual_homing_time_selects_first_lap'):
    adapt(Release, name, [('127 if mode&2 else 31', '31')])
adapt(Release, 'test_release_duty_all_modes', [
    ('(period*3+2)//4 if mode&2 else (rate*4*6+64)//128', '(rate*4*6+64)//128'),
    ('rate*(1 if mode&2 else 4)*4', 'rate*4*4')])
adapt(RC6D, 'test_fine_fraction_conserves_measured_rate_over_48_hours', [
    ('* 123 / (1 << 21)', '* 29 / 122880')])
adapt(RC6D, 'test_three_real_laps_minute_and_seconds_launch_together', [
    ('3754', '15104'), ('2816', '11719'), ('/ 62500', '/ 250000'), ('g > 100000', 'g > 500000')])
adapt(RC6D, 'test_fixed_full_precision_rounding_and_nominal_lap', [
    ('* 960 / 62500, 57.66144', '* 960 / 250000, 57.99936')])
adapt(Guard, 'test_guard_vectors_priority_and_stable_ram_controls', [('self.reg(0x28),127', 'self.reg(0x28),31')])
adapt(Guard, 'test_guard_far_compare_executes_tick_immediately', [('-200)', '-800)')])
adapt(Guard, 'test_guard_overrun_cannot_silently_delay_motor', [('+150)', '+600)')])
# The inherited RC6E wrapper expected 150 old timer counts. Equivalent injected
# duration at the now universal /32 divider is 600 counts = 2.4 ms nominal.
def test_guard_overrun(self):
    GuardTest = getattr(Tests, '_guard_overrun')
    GuardTest(self)
    self.assertEqual(self.word('pulse_diag', 23), 600)
Tests._guard_overrun = Tests.test_guard_overrun_cannot_silently_delay_motor
Tests.test_guard_overrun_cannot_silently_delay_motor = test_guard_overrun
adapt(RC6E, 'test_diag_waveform_matches_rc6d_all_modes', [('range(4)', '(0, 1)')])
adapt(RC6F, 'test_gpio_waveform_and_other_gpio_match_rc6e_all_modes', [('range(4)', '(0, 1)')])

if __name__ == '__main__': unittest.main()
