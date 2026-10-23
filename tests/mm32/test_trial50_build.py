"""Compiled TIM3 stop2go, with modeled 16-bit counter and compare interrupts."""
import struct
import unittest
import test_trial48_build as prior
import test_reference_scan_build as ref
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_FINE_STOP2GO_TRIAL50_20261009.axf'
    signature = 0x4d503530
    defines = prior.Tests.defines + ['-DFINE_STOP2GO']
    # Replaced continuous/coarse/staggered cadence requirements, not regressions.
    test_minute_pulses_staggered_with_uninterrupted_seconds = None
    test_nominal_fast_burst_finishes_within_half_second = None
    test_return_just_after_00_does_not_wait_another_minute = None
    test_catchup_retains_normal_phase_tolerance_and_correction_hold = None
    test_three_full_laps_during_minute_catchup_have_no_minute_parking = None

    def test_nominal_edges_have_uniform_eight_tick_spacing(self):
        self.test_constant_spacing_and_width_over_counter_wraps()

    def test_poll_jitter_does_not_gate_individual_pulses(self):
        self.fine_run(); starts=[]
        for i in range(600):
            if i%126 == 0:
                self.setword('rtc_pace',2,self.word('rtc_pace',2)+1)
                self.setword('rtc_edge_tick',0,self.get(4))
            self.tick()
        starts=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        self.assertIn(set(b-a for a,b in zip(starts,starts[1:])),getattr(self,'fine_spacing_sets',({3776},)))

    def test_five_second_debt_is_slewed_not_burst(self):
        self.fine_run(); self.setword('rtc_pace',2,80)
        for _ in range(128): self.tick()
        starts=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        self.assertIn(set(b-a for a,b in zip(starts,starts[1:])),getattr(self,'fine_spacing_sets',({3776},)))

    def test_minute_waits_for_physical_12_then_moves_without_stopping_seconds(self):
        self.test_both_start_at_00_not_at_58()

    def test_catchup_preserves_six_tick_pulses_and_released_gap(self):
        # Width is measured on the fine clock, not rounded coarse observations.
        self.test_constant_spacing_and_width_over_counter_wraps()
        self.assertGreater(self.word('minute_log',181),self.word('minute_log',182))

    def test_phase_debt_gets_complete_pulses_not_skipped_frames(self):
        self.test_five_second_debt_is_slewed_not_burst()

    def test_button_rec_finishes_runtime_burst_then_homes(self):
        self.test_rec_drains_hardware_pulse_and_queued_minute()

    def test_five_second_physical_lag_still_gates_minutes(self):
        self.fine_run(); self.advance_timer(2930); self.reg(0x0c,0)
        self.put(30,1); self.put(5,4); self.put(15,46)
        for _ in range(80): self.tick()
        self.assertEqual(self.get(13),0)
        self.put(15,47); self.put(5,0); self.setword('rtc_boundary',0,1)
        self.tick()
        self.assertEqual(self.get(3),9)  # A whole skipped minute is not hidden.

    def setUp(self):
        super().setUp()
        self.cpu.mem_map(0x40000000, 0x1000)
        self.counter = self.timer_time = self.sr = self.remainder = 0
        self.edges = []
        def timer_write(cpu, access, a, size, value, user):
            if a == 0x40000410: self.sr &= value
            if a == 0x40000414 and value & 1:
                self.counter = 0; self.sr = 1
            if a in (0x48000010, 0x48000410):
                self.edges.append((self.timer_time, a, value))
        def timer_read(cpu, access, a, size, value, user):
            if a == 0x40000410: self.reg(0x10, self.sr)
            if a == 0x40000424: self.reg(0x24, self.counter)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, timer_write, begin=0x40000400, end=0x40000440)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, timer_write, begin=0x48000010, end=0x48000410)
        self.cpu.hook_add(UC_HOOK_MEM_READ, timer_read, begin=0x40000400, end=0x40000440)

    def reg(self, offset, value=None):
        addr = 0x40000400 + offset
        if value is not None:
            self.cpu.mem_write(addr, struct.pack('<I', value))
        return struct.unpack('<I', self.cpu.mem_read(addr, 4))[0]

    def advance_timer(self, counts):
        # Flags occur even with DIER disabled, just as on the real timer.
        while counts and self.reg(0) & 1:
            events = [((self.reg(0x34+4*i)-self.counter)&65535) or 65536
                      for i in range(4)]
            step = min(min(events), counts)
            self.counter = (self.counter+step)&65535
            self.timer_time += step; counts -= step
            for i, delay in enumerate(events):
                if delay == step: self.sr |= 2 << i
            if self.sr & self.reg(0x0c) & 30:
                self.call('TIM3_Handler')

    def tick(self, high=0):
        self.cpu.mem_write(0x48000408, struct.pack('<I', high << 14))
        self.remainder += self.word('rtc_pace', 1)+1
        counts, self.remainder = divmod(self.remainder, 128)
        self.advance_timer(counts)
        super().tick(high)

    def fine_run(self):
        self.running()
        self.put(5, 0); self.put(15, 45); self.put(16, 11)
        self.rtc_time(11,45,0); self.setword('rtc_last',0,11*3600+45*60)
        self.setword('rtc_pace',4,1); self.setword('rtc_pace',2,0)
        self.setword('rtc_release_edge',0,0)
        self.setword('rtc_boundary', 0, 0)
        self.edges=[]
        self.tick()

    def test_timer_vectors_and_clock_no_af_outputs(self):
        vector=struct.unpack('<I',self.cpu.mem_read(0x08000080,4))[0]
        self.assertEqual(vector, self.symbols['TIM3_Handler'])
        self.fine_run()
        self.assertEqual((self.reg(0x28),self.reg(0x2c),self.reg(0x20)),(127,65535,0))
        self.assertEqual(self.word('minute_log',181),3776)

    def test_constant_spacing_and_width_over_counter_wraps(self):
        self.fine_run()
        for _ in range(4*128):
            self.setword('rtc_edge_tick',0,self.get(4)); self.tick()
        starts=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        falls=[t for t,a,v in self.edges if a==0x48000010 and v==1<<23]
        self.assertGreater(len(starts),60)
        self.assertIn(set(b-a for a,b in zip(starts,starts[1:])),getattr(self,'fine_spacing_sets',({3776},)))
        self.assertEqual(set(b-a for a,b in zip(starts,falls)),{2930})
        self.assertEqual(self.get(3),0)

    def test_both_start_at_00_not_at_58(self):
        self.fine_run()
        self.advance_timer(2930)
        self.reg(0x0c,0); self.put(30,1)
        self.put(5,58)
        for _ in range(128): self.tick()
        self.assertEqual(self.get(13),0)
        self.put(15,46); self.put(5,0); self.setword('rtc_boundary',0,1)
        self.edges=[]; self.tick()
        rises=[(t,a,v) for t,a,v in self.edges if (a==0x48000410 and v in (1,2,4)) or (a==0x48000010 and v==128)]
        self.assertEqual(len(rises),2)
        self.assertEqual(rises[0][0],rises[1][0])
        for _ in range(64): self.tick()
        self.assertEqual((self.get(13),self.get(22),self.get(3)),(6,706,0))

    def test_late_timer_fault_cannot_burst_or_reenergize(self):
        self.fine_run()
        self.counter=(self.reg(0x38)+1200)&65535; self.sr|=4
        self.call('TIM3_Handler')
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.reg(0x0c),0)
        self.call('TIM3_Handler'); self.released()

    def test_unsupported_clock_fails_without_changing_global_clock(self):
        self.running(); self.cpu.mem_write(0x40021004,struct.pack('<I',4<<8))
        self.tick()
        self.assertEqual(self.get(3),10)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x40021004,4))[0],4<<8)

    def test_three_real_laps_minute_and_seconds_launch_together(self):
        self.fine_run(); start=self.get(4)
        parks=[]; last=0
        for elapsed in range(1,181*128+1):
            if elapsed%128==0:
                sod=11*3600+45*60+elapsed//128
                self.rtc_time(sod//3600,sod//60%60,sod%60)
                self.rtc_poll()
            p=self.word('seconds_log',248)+1
            self.tick(int(891<=p<=906))
            self.assertEqual(self.get(3),0,(elapsed,self.get(3)))
            if self.word('seconds_log',255)!=last:
                last=self.word('seconds_log',255); parks.append(self.get(4)-start)
        self.assertEqual(len(parks),3)
        self.assertTrue(all(abs(p-(58+60*i)*128)<15 for i,p in enumerate(parks)),parks)
        self.assertEqual((self.get(13),self.get(22)),(18,708))
        starts=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        intervals=[b-a for a,b in zip(starts,starts[1:])]
        cadence={count for observed in getattr(self,'fine_spacing_sets',({3776},)) for count in observed}
        self.assertTrue(all(v in cadence or v>100000 for v in intervals),set(intervals))

    def test_rec_drains_hardware_pulse_and_queued_minute(self):
        self.test_both_start_at_00_not_at_58()
        # Start a fresh live pulse plus a complete minute marker.
        self.reg(0x0c,0); self.put(30,1); self.put(15,47);self.put(5,0)
        self.setword('rtc_boundary',0,1); self.tick()
        self.setword('minute_log',229,1); self.setword('minute_log',227,2)
        for _ in range(70): self.tick()
        self.assertEqual(self.get(2),1)
        self.assertEqual(self.reg(0x0c),0)
        self.assertEqual(self.word('minute_log',229),1)

    def test_minute_overlap_does_not_change_seconds_spacing(self):
        self.test_both_start_at_00_not_at_58()
        starts=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        self.assertGreater(len(starts),6)
        self.assertIn(set(b-a for a,b in zip(starts,starts[1:])),getattr(self,'fine_spacing_sets',({3776},)))
        mrises=[t for t,a,v in self.edges if a==0x48000410 and v in (2,4)]
        self.assertEqual(len(mrises),6)
        self.assertEqual(set(b-a for a,b in zip(mrises,mrises[1:])),{3906})

    def test_calibration_updates_only_at_new_lap(self):
        self.fine_run(); self.setword('rtc_pace',1,63475)
        for _ in range(64): self.tick()
        self.assertEqual(self.word('minute_log',181),3776)
        # Force a safe parked boundary after an actual pulse completes.
        self.advance_timer((self.reg(0x38)-self.counter)&65535)
        self.reg(0x0c,0); self.put(30,1); self.put(5,0)
        self.setword('rtc_boundary',0,1); self.tick()
        self.assertEqual(self.word('minute_log',181),3835)

    def test_rec_during_coarse_minute_catchup_does_not_deadlock(self):
        self.fine_run(); self.put(2,10)
        self.setword('minute_active',0,1)
        self.setword('minute_end',0,self.get(4)+4)
        self.setword('minute_log',229,1); self.setword('minute_log',227,2)
        for _ in range(16): self.tick()
        self.assertEqual(self.get(2),1)
        self.assertEqual(self.reg(0x0c),0)

    def test_counter_flags_while_disabled_cannot_shorten_next_minute_pulse(self):
        self.test_both_start_at_00_not_at_58()
        # Disabled compare flags are real hardware behavior, not clean RAM.
        self.sr|=24
        self.advance_timer((self.reg(0x38)-self.counter)&65535)
        self.reg(0x0c,0); self.put(30,1); self.put(15,47); self.put(5,0)
        self.setword('rtc_boundary',0,1); self.tick()
        self.assertEqual(self.sr&24,0)
        self.assertEqual(self.reg(0x0c)&24,24)
        self.advance_timer(1952); self.assertEqual(self.word('minute_active'),1)
        self.advance_timer(1); self.assertEqual(self.word('minute_active'),0)


if __name__ == '__main__': unittest.main()
