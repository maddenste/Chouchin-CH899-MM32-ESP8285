"""Calibrated homing plus Trial53 passive audit; separate new image."""
import unittest
import struct
import test_trial53_build as prior


class Tests(prior.Tests):
    artifact = prior.Tests.artifact.with_name('MM32SPIN05PF_CALIBRATED_ALIGNMENT_TRIAL56_20261010.axf')
    signature = 0x4d503536
    defines = prior.Tests.defines+['-DCALIBRATED_ALIGNMENT','-DNIGHTLY_DEFERRED_HOME']
    minute_offset=52
    seconds_offset=72

    def audit_start(self):
        self.put(16,23); self.put(15,30)
        self.call('audit_tick',100,7)
        self.assertEqual((self.a(0),self.a(1)),(1,1))

    def mode_run(self,mode):
        super().mode_run(mode)
        self.rtc_time(23,45,0); self.setword('rtc_last',0,23*3600+45*60)
        self.put(16,23)

    def simulate(self, seconds, edits=()):
        events = []; last = self.word('minute_log', 189)
        for elapsed in range(1, seconds*128+1):
            if elapsed % 128 == 0:
                sec = elapsed//128
                if sec in dict(edits): self.setword('minute_log',188,dict(edits)[sec])
                sod = 23*3600+45*60+sec
                self.rtc_time(sod//3600,sod//60%60,sod%60); self.rtc_poll()
            # Corrected seconds origin is four pulses past the old origin;
            # therefore the next real optical entry is four pulses earlier.
            p = self.word('seconds_log',248)+1
            self.tick(int(959-self.seconds_offset <= p <= 974-self.seconds_offset))
            self.assertEqual(self.get(3),0,(elapsed,self.get(3)))
            active = self.word('minute_log',189)
            if active != last: events.append((elapsed,active)); last=active
        return events

    def test_precise_minute_offset_across_six_entry_phases(self):
        for entry in range(73,79):
            self.setUp(); self.tick()
            for _ in range(12000):
                pulse=self.get(20)+int(bool(self.word('minute_active')))
                high=int(pulse>=entry) if self.get(19)==2 else 0
                self.tick(high)
                self.assertEqual(self.get(3),0)
                if self.get(7): break
            self.assertEqual(self.get(7),1)
            self.assertEqual(self.get(20)-self.word('minute_log',249),self.minute_offset)
            self.assertEqual(self.get(20),self.word('minute_log',250))

    def test_seconds_homing_and_runtime_use_same_offset(self):
        self.tick()
        for _ in range(6000):
            high=int(246<=self.word('seconds_log',5)+1<=262) if self.get(19)==1 else 0
            self.tick(high)
            if self.get(8): break
        self.assertEqual(self.get(8),1)
        self.assertEqual(self.word('seconds_log',5)-self.word('seconds_log',240),self.seconds_offset)
        self.call('parallel_seconds_runtime_begin')
        for p in range(1,961):
            self.call('parallel_seconds_runtime_done',6 if 959-self.seconds_offset<=p<=974-self.seconds_offset else 0)
        self.assertEqual(self.word('seconds_log',254),960)
        self.assertEqual(self.word('seconds_log',255),1)

    def test_calibrated_all_modes_keep_complete_minute_markers(self):
        for mode in range(4):
            self.setUp(); self.mode_run(mode); self.simulate(121)
            self.assertEqual((self.get(22),self.word('minute_log',191)),(707,0))
            self.assertEqual(self.get(13),12)
            self.assertGreaterEqual(self.word('seconds_log',255),2)

    def test_calibrated_zero_to_three_boundary(self):
        self.mode_run(0); events=self.simulate(61,[(25,3)])
        self.assertEqual(len(events),1)
        self.assertTrue(60*128<=events[0][0]<60*128+10)
        self.assertEqual((self.get(22),self.word('minute_log',191)),(706,0))

    def test_audit_calibrated_reference_geometry(self):
        self.audit_start(); tick=self.audit_low_markers()
        coordinate=4320-self.minute_offset
        self.put(22,coordinate//6); self.setword('minute_log',191,coordinate%6)
        self.cpu.mem_write(0x48000408,struct.pack('<I',1<<14))
        for i in range(3): self.call('audit_sample_minute',tick+8*(i+1))
        self.assertEqual((self.a(0),self.a(9)),(2,0))

    def test_audit_only_at_midnight(self):
        self.put(22,690); self.put(16,11); self.put(15,30)
        self.call('audit_tick',100,7)
        self.assertEqual((self.a(1),self.a(2)),(0,0))
        self.put(16,12); self.put(15,6)
        self.call('audit_tick',200,7)
        self.assertEqual(self.a(1),0)
        self.put(16,23); self.put(15,30)
        self.call('audit_tick',300,7)
        self.assertEqual((self.a(1),self.a(2)),(1,1))
        self.put(16,0); self.put(15,6)
        self.call('audit_tick',400,7)
        self.assertEqual(self.a(1),0)

    def test_confirmed_mismatch_latches_missing_does_not(self):
        self.audit_start(); tick=self.audit_low_markers()
        self.put(22,4248//6); self.setword('minute_log',191,4248%6)
        self.cpu.mem_write(0x48000408,struct.pack('<I',1<<14))
        for i in range(3): self.call('audit_sample_minute',tick+8*(i+1))
        self.put(16,0); self.put(15,6); self.call('audit_tick',500,7)
        self.assertEqual(self.word('minute_log',203),1)
        self.assertEqual(self.get(2),0) # Sensor audit itself commands no motion.
        self.call('audit_tick',600,7)
        self.assertEqual(self.word('minute_log',203),1)
        self.setUp(); self.audit_start(); self.audit_low_markers()
        self.put(16,0); self.put(15,6); self.call('audit_tick',500,7)
        self.assertEqual(self.word('minute_log',203),0)

    def test_seconds_mismatch_flags_only_during_nightly_check(self):
        self.setword('seconds_log',254,920)
        self.call('audit_seconds_reference')
        self.assertEqual(self.word('minute_log',203),0)
        self.audit_start(); self.call('audit_seconds_reference')
        self.assertEqual(self.word('minute_log',203),2)

    def test_minute_probes_stop_after_qualified_result(self):
        self.mode_run(0); self.audit_start(); self.a(19,1)
        self.a(16,1); self.setword('second_active',0,0)
        self.call('audit_tick',500,7)
        self.assertEqual(self.a(16),1) # No reselecting minute sensor.

    def test_rec_precedes_scheduled_recovery(self):
        self.running(); self.setword('minute_log',203,1)
        self.setword('minute_log',204,1)
        self.setword('minute_log',229,1); self.setword('minute_log',227,2)
        for _ in range(12):
            self.tick()
            if self.get(2)==1: break
        self.assertEqual(self.get(2),1)
        self.assertEqual(self.word('minute_log',229),1)
        self.assertEqual(self.word('minute_log',204),0)

    def test_manual_wake_does_not_consume_pending_recovery(self):
        self.running(); self.setword('minute_log',203,1)
        self.setword('minute_log',228,1) # M.SET's manual wake request.
        self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',0),2)
        self.assertEqual(self.word('minute_log',204),0)

    def test_scheduled_matching_time_keeps_blue_confirmation_on_recovery(self):
        self.running(); self.setword('minute_log',203,1)
        self.setword('daily_log',3,self.now_stamp())
        self.call('parallel_poll_once')
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log',0),3)
        self.assertEqual(self.get(28),2)
        for _ in range(10):
            self.tick()
            if self.word('minute_log',204)==3: break
        self.assertEqual(self.word('minute_log',204),3)
        self.assertEqual(self.get(28),2)

    def test_scheduled_wake_queues_only_after_session_and_correction(self):
        self.running(); self.setword('minute_log',203,1)
        self.setword('daily_log',3,self.now_stamp())
        self.call('parallel_poll_once')
        self.assertEqual(self.word('minute_log',204),1)
        self.tick(); self.assertEqual(self.get(2),7)
        self.setword('daily_log',0,7); self.setword('daily_log',13,1)
        self.tick(); self.assertEqual(self.get(2),7)
        self.setword('daily_log',0,3); self.setword('daily_log',13,0)
        for _ in range(10):
            self.tick()
            if self.word('minute_log',204)==3: break
        self.assertEqual((self.get(2),self.word('minute_log',204)),(1,3))
        self.assertEqual(self.get(22),0)
        self.assertEqual(self.word('minute_log',229),0) # Never permanent REC park.

    def test_recovery_preserves_settings_and_completes_real_homing(self):
        self.mode_run(3)
        self.rtc_time(0,0,0); self.setword('rtc_last',0,0)
        self.put(16,0); self.put(15,0); self.put(5,0)
        self.setword('minute_log',192,1); self.setword('minute_log',203,3)
        self.setword('minute_log',204,1); self.setword('daily_log',0,3)
        schedule=self.word('daily_log',3)
        self.tick() # Fine pulse already active: drain, do not truncate.
        self.assertEqual(self.word('minute_log',204),2)
        for elapsed in range(1,6500):
            if elapsed%128==0:
                self.rtc_time(0,0,elapsed//128); self.rtc_poll()
            if self.get(19)==2:
                high=int(self.get(20)+int(bool(self.word('minute_active')))>=73)
            else:
                high=int(246<=self.word('seconds_log',5)+1<=262)
            self.tick(high)
            self.assertEqual(self.get(3),0,(elapsed,self.get(3)))
            if self.word('minute_log',204)==0 and self.get(7) and self.get(8): break
        self.assertEqual((self.get(7),self.get(8)),(1,1))
        self.tick()
        self.assertEqual(self.word('minute_log',203),0)
        self.assertEqual(self.word('minute_log',204),0)
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',189)),(3,3))
        self.assertEqual(self.word('minute_log',192),1)
        self.assertEqual(self.word('minute_log',195),1)
        self.assertEqual(self.word('daily_log',3),schedule)
        self.assertEqual(self.word('minute_log',229),0)


def load_tests(loader, tests, pattern):
    names=[name for name in Tests.__dict__ if name.startswith('test_')]
    names += ['test_audit_all_modes_preserve_edges_and_seconds_references',
              'test_audit_missing_insufficient_cancelled',
              'test_audit_glitch_and_stuck_high_not_pass',
              'test_audit_parked_all_modes_minutes_continue',
              'test_audit_ram_addresses',
              'test_no_time_has_no_parking_or_daily_fallback',
              'test_first_time_controls_schedule_and_optional_parking',
              'test_power_cycle_discards_previous_time_settings',
              'test_timeout_leds_off_and_motion_continues',
              'test_button_clean_exact_protocol_and_ack_while_motors_run']
    return unittest.TestSuite(Tests(name) for name in names)


if __name__=='__main__': unittest.main()
