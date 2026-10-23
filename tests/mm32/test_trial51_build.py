"""RAM modes: 0 Sweep default, 1 Burst, 3 Hold&Start. Boundary-safe switches."""
import unittest
import test_trial50_build as prior


class Tests(prior.Tests):
    artifact=prior.ref.ROOT/'build/MM32SPIN05PF_RAM_MODES_TRIAL51_20261009.axf'
    signature=0x4d503531
    defines=prior.Tests.defines+['-DFINE_RAM_MODES']

    def setUp(self):
        super().setUp()
        self.boot_modes=(self.word('minute_log',188),self.word('minute_log',189))
        # Retain every Trial50 regression in its proven Hold&Start configuration.
        self.setword('minute_log',188,3); self.setword('minute_log',189,3)

    def mode_run(self,mode):
        self.setword('minute_log',188,mode); self.setword('minute_log',189,mode)
        self.fine_run()

    def tick(self,high=0):
        # PSC31 normal modes run the compare clock four times faster.
        if hasattr(self,'counter') and self.reg(0)&1 and self.reg(0x28)==31:
            self.remainder+=3*(self.word('rtc_pace',1)+1)
        super().tick(high)

    def simulate(self,seconds,edits=()):
        last=0; events=[]
        for elapsed in range(1,seconds*128+1):
            if elapsed%128==0:
                sec=elapsed//128
                if sec in dict(edits): self.setword('minute_log',188,dict(edits)[sec])
                sod=11*3600+45*60+sec
                self.rtc_time(sod//3600,sod//60%60,sod%60);self.rtc_poll()
            p=self.word('seconds_log',248)+1
            self.tick(int(891<=p<=906))
            self.assertEqual(self.get(3),0,(elapsed,self.get(3)))
            active=self.word('minute_log',189)
            if active!=last: events.append((elapsed,active));last=active
        return events

    def test_default_sweep_and_ram_addresses(self):
        self.assertEqual(self.boot_modes,(0,0))
        self.assertEqual(self.symbols['minute_log']+4*188,0x20000504)
        self.assertEqual(self.symbols['minute_log']+4*189,0x20000508)

    def test_real_homing_then_default_sweep_runtime(self):
        self.setword('minute_log',188,0);self.setword('minute_log',189,0)
        prior.Tests.test_home_then_runtime_keeps_seconds_sensor_selected_after_catchup(self)

    def test_sweep_has_six_spread_steps_and_whole_marker(self):
        self.mode_run(0);self.simulate(61)
        starts=[t for t,a,v in self.edges if a==0x48000410 and v in (2,4)]
        self.assertEqual(len(starts),6)
        self.assertTrue(all(abs((b-a)-2500000)<4000 for a,b in zip(starts,starts[1:])),starts)
        self.assertEqual((self.get(13),self.get(22),self.word('minute_log',191)),(6,706,0))
        s=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        self.assertEqual(set(b-a for a,b in zip(s,s[1:])),{15625})

    def test_burst_has_complete_marker_at_00_and_continuous_seconds(self):
        self.mode_run(1);self.simulate(61)
        starts=[t for t,a,v in self.edges if a==0x48000410 and v in (2,4)]
        self.assertEqual(len(starts),6)
        self.assertEqual(set(b-a for a,b in zip(starts,starts[1:])),{15625})
        s=[t for t,a,v in self.edges if (a==0x48000410 and v==1) or (a==0x48000010 and v==128)]
        self.assertEqual(set(b-a for a,b in zip(s,s[1:])),{15625})
        self.assertEqual((self.get(13),self.get(22)),(6,706))

    def test_switch_sweep_to_hold_finishes_old_marker(self):
        self.mode_run(0);events=self.simulate(61,[(25,3)])
        self.assertEqual(len(events),1,events)
        self.assertTrue(60*128<=events[0][0]<60*128+10,events)
        self.assertEqual((self.get(13),self.get(22),self.word('minute_log',191)),(6,706,0))
        self.assertEqual(self.word('minute_log',189),3)

    def test_switch_hold_to_sweep_does_not_double_advance(self):
        self.mode_run(3);self.simulate(71,[(25,0)])
        self.assertEqual(self.word('minute_log',189),0)
        self.assertEqual((self.get(13),self.get(22),self.word('minute_log',191)),(7,706,1))

    def test_invalid_request_is_ignored(self):
        self.mode_run(3)
        for value in (2,4,0xffffffff):
            self.setword('minute_log',188,value);self.tick()
            self.assertEqual(self.word('minute_log',189),3)
            self.assertEqual(self.word('minute_log',190),0)

    def test_all_six_mode_changes_at_00_leave_whole_marker(self):
        for old,new in ((0,1),(0,3),(1,0),(1,3),(3,0),(3,1)):
            with self.subTest(old=old,new=new):
                self.setUp();self.mode_run(old)
                self.simulate(61,[(25,new)])
                self.assertEqual(self.word('minute_log',189),new)
                self.assertEqual((self.get(13),self.get(22),self.word('minute_log',191)),(6,706,0))
                self.assertEqual(self.word('minute_log',190),0)

    def test_last_request_wins_and_cancel_keeps_old_mode(self):
        self.mode_run(0);self.simulate(61,[(15,3),(25,1),(35,0)])
        self.assertEqual(self.word('minute_log',189),0)
        self.assertEqual((self.get(13),self.get(22),self.word('minute_log',191)),(6,706,0))

    def test_sweep_time_correction_cannot_commit_between_markers(self):
        self.mode_run(0)
        self.setword('minute_log',191,5);self.put(30,1)
        self.reg(0x0c,0);self.setword('second_active',0,0)
        self.due()
        self.feed(b'+TIME:Wed Oct  7 11:45:01 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log',0),7)
        self.assertEqual(self.word('daily_log',13),1)
        for _ in range(16):self.tick()
        self.assertEqual(self.word('minute_log',191),0)
        self.assertEqual(self.get(22),706)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',13),3)
        self.assertEqual(self.get(3),0)


if __name__=='__main__':unittest.main()
