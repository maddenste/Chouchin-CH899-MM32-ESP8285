"""Compiled MM32 optional TIME settings and independent overnight parking."""
import unittest
import struct
from unicorn.arm_const import UC_ARM_REG_PRIMASK
import test_trial51_build as prior


class Tests(prior.Tests):
    artifact=prior.prior.ref.ROOT/'build/MM32SPIN05PF_UART_SETTINGS_TRIAL52_20261009.axf'
    signature=0x4d503532
    defines=prior.Tests.defines+['-DFINE_UART_SETTINGS']

    def message(self,suffix=b'',time=b'11:45:00'):
        return b'+TIME:Wed Oct  7 '+time+b' 2026 +0100 09:17'+suffix+b'\r\n'

    def wire(self,line):
        for byte in line:
            self.cpu.mem_write(0x40004408,struct.pack('<I',2))
            self.cpu.mem_write(0x40004404,struct.pack('<I',byte))
            self.call('uart_probe_poll_once')

    def test_invalid_request_is_ignored(self):
        self.mode_run(3)
        for value in (4,0xffffffff):
            self.setword('minute_log',188,value);self.tick()
            self.assertEqual(self.word('minute_log',189),3)
            self.assertEqual(self.word('minute_log',190),0)

    def test_suffix_all_modes_formats_and_legacy_preserves(self):
        for mode in range(4):
            for park in range(3):
                for suffix in (f'{mode}{park}',f' {mode}{park}',f'{mode} {park}',f' {mode} {park}'):
                    self.wire(self.message(suffix.encode()))
                    self.assertEqual(self.word('minute_log',188),mode)
                    self.assertEqual(self.word('minute_log',192),park)
        count=self.word('minute_log',194)
        self.wire(self.message())
        self.assertEqual(self.word('minute_log',194),count)
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',192)),(3,2))

    def test_bad_suffix_cannot_partly_apply_time_or_settings(self):
        for suffix in (b'4 1',b'33',b'3',b'3 ',b'31X',b'  31',b'3  1',b'X1',b'31\x00'):
            count=self.word('minute_log',194);good=self.word('uart_probe_good_time',0)
            self.wire(self.message(suffix))
            self.assertEqual(self.word('minute_log',194),count,suffix)
            self.assertEqual(self.word('uart_probe_good_time',0),good,suffix)

    def test_uart_mode_is_pending_not_immediate(self):
        self.mode_run(0);self.simulate(25)
        self.wire(self.message(b'30'))
        self.tick()
        self.assertEqual(self.word('minute_log',189),0)
        self.assertEqual(self.word('minute_log',190),1)

    def test_mode2_sweeps_minutes_and_holds_seconds(self):
        self.mode_run(2);self.simulate(61)
        starts=[t for t,a,v in self.edges if a==0x48000410 and v in (2,4)]
        self.assertEqual(len(starts),6)
        self.assertEqual((self.get(22),self.word('minute_log',191)),(706,0))
        self.assertEqual(self.get(3),0)

    def test_mode2_transitions_complete_markers(self):
        for old,new in ((0,2),(1,2),(2,0),(2,1),(2,3),(3,2)):
            with self.subTest(old=old,new=new):
                self.setUp();self.mode_run(old);self.simulate(61,[(25,new)])
                self.assertEqual(self.word('minute_log',189),new)
                self.assertEqual((self.get(22),self.word('minute_log',191)),(706,0))

    def night_run(self,mode=0,hour=0,minute=0):
        self.setword('minute_log',192,1)
        self.mode_run(mode)
        self.rtc_time(hour,minute,0);self.put(16,hour);self.put(15,minute);self.put(5,0)
        self.setword('rtc_last',0,hour*3600+minute*60)
        self.put(22,(hour*60+minute)%720)
        self.put(30,1);self.reg(0x0c,self.reg(0x0c)&~6)

    def night_simulate(self,seconds,hour=0,minute=0,second=0):
        base=hour*3600+minute*60+second
        for elapsed in range(1,seconds*128+1):
            if elapsed%128==0:
                sod=(base+elapsed//128)%86400
                self.rtc_time(sod//3600,sod//60%60,sod%60);self.rtc_poll()
            p=self.word('seconds_log',248)+1
            self.tick(int(891<=p<=906))
            self.assertEqual(self.get(3),0,(elapsed,self.get(3)))

    def test_overnight_minutes_continue_all_modes(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp();self.night_run(mode);pulses=self.get(12)
                self.night_simulate(61)
                self.assertEqual(self.get(12),pulses)
                self.assertEqual(self.get(22),1)
                self.assertEqual(self.word('minute_log',193),1)

    def test_night_resume_at_0600(self):
        for mode in range(4):
            with self.subTest(mode=mode):
                self.setUp();self.night_run(mode,5,59);pulses=self.get(12)
                self.night_simulate(59,5,59)
                self.assertEqual(self.get(12),pulses)
                self.rtc_time(6,0,0);self.rtc_poll()
                for _ in range(64):self.tick()
                self.assertGreater(self.get(12),pulses)
                self.assertEqual(self.word('minute_log',193),0)
                self.assertEqual(self.get(22),360)

    def test_midnight_entry_finishes_lap_then_parks(self):
        self.mode_run(0);self.setword('minute_log',192,1)
        self.rtc_time(23,59,0);self.put(16,23);self.put(15,59)
        self.setword('rtc_last',0,23*3600+59*60);self.put(22,719)
        self.night_simulate(61,23,59)
        count=self.get(12)
        self.assertEqual(self.word('minute_log',193),1)
        self.assertEqual(self.get(22),0)
        for _ in range(128):self.tick()
        self.assertEqual(self.get(12),count)

    def test_disable_night_waits_for_next_00(self):
        self.night_run(0);self.night_simulate(20)
        count=self.get(12);self.wire(self.message(b'00',b'00:00:20'))
        self.night_simulate(39,second=20)
        self.assertEqual(self.get(12),count)
        self.night_simulate(2,second=59)
        self.assertGreater(self.get(12),count)
        self.assertEqual(self.get(3),0)

    def test_night_settings_change_while_parked(self):
        self.night_run(0);self.night_simulate(25)
        self.wire(self.message(b'31',b'00:00:25'))
        count=self.get(12)
        self.night_simulate(36,second=25)
        self.assertEqual(self.word('minute_log',189),3)
        self.assertEqual(self.get(12),count)
        self.assertEqual(self.get(22),1)

    def test_time_correction_while_night_parked(self):
        self.night_run(0);self.tick();self.due()
        self.assertEqual(self.word('daily_log',0),2)
        self.assertEqual(self.word('minute_log',211),1)
        self.feed(self.message(b'01',b'00:00:01'))
        self.call('parallel_poll_once')
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('daily_log',8),1)
        self.assertEqual(self.word('minute_log',192),1)

    def test_permanent_park_daytime_and_release(self):
        self.night_run(1,11,45);self.setword('minute_log',192,2)
        count=self.get(12);self.night_simulate(61,11,45)
        self.assertEqual(self.get(12),count)
        self.assertEqual(self.get(22),706)
        self.assertEqual(self.word('minute_log',193),1)
        self.wire(self.message(b'10',b'11:46:01'))
        self.night_simulate(60,11,46,1)
        self.assertGreater(self.get(12),count)
        self.assertEqual(self.get(22),707)

    def test_aligned_start_parking_window_all_hours(self):
        for hour in range(24):
            for parking in (0,1,2):
                with self.subTest(hour=hour,parking=parking):
                    self.setUp();self.running()
                    self.setword('minute_log',188,0);self.setword('minute_log',189,0)
                    self.setword('minute_log',192,parking)
                    self.setword('second_active',0,0)
                    self.put(5,0);self.put(15,0);self.put(16,hour)
                    self.put(22,(hour*60)%720)
                    self.setword('rtc_pace',4,1)
                    self.tick()
                    expected=parking==2 or (parking==1 and hour<6)
                    self.assertEqual(bool(self.word('minute_log',193)),expected)
                    self.assertEqual(bool(self.reg(0x0c)&2),not expected)

    def test_settings_can_update_without_replacing_pending_time(self):
        self.mode_run(0);self.due()
        self.feed(self.message(b'10',b'11:45:01'))
        snapshot=bytes(self.cpu.mem_read(self.symbols['uart_probe_time_event'],20))
        self.wire(self.message(b'32',b'11:45:09'))
        self.assertEqual(bytes(self.cpu.mem_read(self.symbols['uart_probe_time_event'],20)),snapshot)
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',192)),(3,2))

    def test_ram_layout(self):
        self.assertEqual(self.symbols['minute_log']+4*192,0x20000514)
        self.assertEqual(self.symbols['minute_log']+4*193,0x20000518)
        self.assertEqual(self.symbols['minute_log']+4*194,0x2000051c)

    def test_uart_change_completes_at_next_00(self):
        self.mode_run(0);self.simulate(25)
        # Calibrated subclasses run at 23:45 to exercise the nightly audit.
        # Continue that same clock rather than injecting a false 12-hour jump.
        hour,minute,second=self.get(16),self.get(15),self.get(5)
        self.wire(self.message(b'30',f'{hour:02}:{minute:02}:{second:02}'.encode()))
        self.night_simulate(36,hour,minute,second)
        self.assertEqual(self.word('minute_log',189),3)
        self.assertEqual((self.get(22),self.word('minute_log',191)),(706,0))

    def test_damaged_calendar_with_suffix_is_atomic(self):
        before=self.word('minute_log',194)
        self.wire(self.message(b'32').replace(b'Oct  7',b'Feb 30'))
        self.assertEqual(self.word('minute_log',194),before)
        self.assertEqual((self.word('minute_log',188),self.word('minute_log',192)),(3,0))

    def test_settings_preserve_prior_interrupt_mask(self):
        for mask in (0,1):
            self.cpu.reg_write(UC_ARM_REG_PRIMASK,mask)
            self.wire(self.message(b'31'))
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),mask)


if __name__=='__main__':unittest.main()
