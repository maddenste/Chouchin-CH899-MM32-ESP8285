"""Startup/catch-up parking regressions against actual ARM and timer models."""
import unittest
from pathlib import Path
from check_rc6ac_normal_resume import Tests as Prior, ButtonTests as ButtonPrior, RTCTests as RTCPrior
from audit_rc6ac_final import Findings as OriginalFindings
from unicorn import UC_HOOK_MEM_WRITE

ARTIFACT=Path(__file__).parent/'release_candidate_rc6ad/build/MM32SPIN05PF_STARTUP_PARK_RC6AD_20261022.axf'

class Tests(Prior):
    artifact=ARTIFACT
    signature=0x4d505287

    def acquisition(self,saver,style=3):
        OriginalFindings.acquisition(self,saver,style)
        # Real cold-start minute timing must not depend on a previous launch.
        self.setword('minute_log',183,0);self.setword('minute_log',184,0)
        self.store(0x40000428,0) # Seconds timer reset prescaler, never launched.
        self.pad_edges=[]

    def launch_trace(self):
        launches=[]
        def write(cpu,access,address,size,value,user):
            if address==0x40000414 and value==1:launches.append(self.get(4))
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,write)
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
        return launches

    def test_always_parked_never_launches_seconds_during_catchup_all_styles(self):
        for style in range(4):
            self.setUp();self.acquisition(2,style);launches=self.launch_trace()
            for _ in range(256):
                self.tick()
                self.assertEqual(self.get(3),0)
                self.assertEqual(self.reg(0)&1,0)
            self.assertEqual(launches,[])
            self.assertEqual(self.pad_edges,[])
            self.assertEqual(self.get(2),10)
            self.assertGreater(self.get(23),0) # Minute catch-up is still moving.
            self.assertGreater(self.word('minute_log',183),0)

    def test_always_parked_runtime_minute_width_is_valid_without_seconds_launch(self):
        for style in range(4):
            self.setUp()
            self.setword('minute_log',183,0);self.setword('minute_log',184,0)
            self.initial_release(style,2,5)
            # initial_release uses a warm helper; clear and initialise again
            # to enforce genuinely unseeded minute width/period here.
            self.call('fine_stop')
            self.store(0x40000428,0)
            self.setword('minute_log',183,0);self.setword('minute_log',184,0)
            self.call('fine_runtime_tick',self.get(4),7,0)
            self.assertEqual(self.reg(0)&1,0)
            period=self.word('minute_log',184);width=self.word('minute_log',183)
            self.assertEqual((period,width),(31250,15625))
            events=[]
            def write(cpu,access,address,size,value,user):
                if address==0x48000410 and (value&6 or value&(6<<16)):
                    events.append((self.timer_time,value))
            hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,write,begin=0x48000410,end=0x48000410)
            self.cpu.ctl_remove_cache(0x08000000,0x08008000)
            self.setword('request_pulses',0,6);self.call('pwm_minutes_queue')
            before=self.get(13);self.advance_timer(period*7)
            self.cpu.hook_del(hook)
            rises=[t for t,v in events if v&6];falls=[t for t,v in events if v&(6<<16)]
            self.assertEqual((len(rises),len(falls)),(6,6))
            self.assertEqual({b-a for a,b in zip(rises,falls)},{width})
            self.assertEqual(self.get(13)-before,6)
            self.assertEqual(self.get(3),0);self.assertEqual(self.reg(0)&1,0)

    def test_always_parked_finishes_full_catchup_and_runs_minutes_without_seconds(self):
        for style in (0,3):
            self.setUp();self.acquisition(2,style);launches=self.launch_trace()
            for _ in range(18000):
                self.tick()
                self.assertEqual(self.get(3),0,(style,self.get(2),self.get(4)))
                self.assertEqual(self.reg(0)&1,0)
                if (self.get(2)==7 and self.get(13)>0 and
                    not self.word('minute_active') and not self.word('request_pulses') and
                    not self.word('release_state',2)):
                    break
            self.assertEqual(self.get(2),7)
            self.assertGreater(self.get(13),0)
            self.assertEqual(launches,[]);self.assertEqual(self.pad_edges,[])
            self.assertEqual(self.get(22),(self.get(16)%12)*60+self.get(15))
            expected_steps=self.get(5)//10 if style==0 else 0
            self.assertEqual(self.word('minute_log',191),expected_steps)

    def test_overnight_parks_after_first_lap_and_resumes_during_catchup_without_rebuild(self):
        for style in range(4):
            self.setUp();self.acquisition(1,style);launches=self.launch_trace()
            self.tick();self.complete_lap()
            self.assertEqual(self.get(2),10)
            self.assertEqual(self.word('seconds_log',255),1)
            self.assertEqual(len(launches),1)
            self.assertEqual(self.bt_count,960)
            frozen=(self.counter,self.down,self.reg(0x2c),self.reg(0x38),self.reg(0x3c))
            edge_count=len(self.pad_edges);minute_before=self.get(23)
            for _ in range(512):self.tick()
            self.assertEqual(self.get(3),0)
            self.assertEqual(len(launches),1);self.assertEqual(len(self.pad_edges),edge_count)
            self.assertGreater(self.get(23),minute_before)
            self.assertEqual(self.get(2),10)
            # 06:00 occurs before the minute catch-up has completed.
            self.put(16,6);self.put(15,0);self.put(5,0);self.fixture_clock()
            self.setword('rtc_boundary',0,1)
            for _ in range(16):
                self.tick()
                self.assertEqual(self.get(3),0)
                if self.gate():break
            self.assertTrue(self.gate())
            self.assertEqual(self.get(2),10)
            self.assertEqual(len(launches),1)
            self.assertEqual(self.word('seconds_log',58),1)
            self.assertEqual((self.counter,self.down,self.reg(0x2c),self.reg(0x38),self.reg(0x3c)),frozen)

    def test_daytime_stop2go_catchup_uses_phase_resume_not_rebuild(self):
        self.acquisition(0,3);launches=self.launch_trace();self.tick();self.complete_lap()
        for _ in range(512):
            self.tick()
            if self.gate():break
        self.assertEqual(self.get(3),0);self.assertTrue(self.gate())
        self.assertEqual(self.get(2),10);self.assertEqual(len(launches),1)
        self.assertEqual(self.word('seconds_log',58),1)

class ButtonTests(ButtonPrior):
    artifact=ARTIFACT
    signature=0x4d505287

class RTCTests(RTCPrior):
    artifact=ARTIFACT
    signature=0x4d505287

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_normal_overnight_lap_and_morning_release_preserve_waveform',
            'test_correction_drain_keeps_prior_release_path',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_all_saver_transitions_in_all_styles_request_restart_without_live_change',
            'test_unexpected_timer_stop_is_not_treated_as_first_launch']
    suite=unittest.TestSuite([Tests(n) for n in names]+[
        ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'),
        ButtonTests('test_sleep_closes_lease_without_reply_or_motor_change'),
        RTCTests('test_slave_held_sda_recovers_then_verifies_calendar')])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
