"""Actual RC6AG ARM parser/TX/restart checks with UART and timer models."""
import unittest
from pathlib import Path
from check_rc6ae_correction_resume import Tests as Prior, ButtonTests as ButtonPrior, RTCTests as RTCPrior
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

ARTIFACT=Path(__file__).parent/'release_candidate_rc6ag/build/MM32SPIN05PF_TIME_ECHO_RC6AG_20261022.axf'

class Tests(Prior):
    artifact=ARTIFACT
    signature=0x4d50528a

    def setUp(self):
        super().setUp()
        self.sent=[];self.echo_samples=[]
        self.tx_ready=True
        # Historical RX fixtures publish only RXAVL; model independent TXEPT
        # without erasing their pending received-byte flag.
        def ready(c,a,address,size,value,u):
            if self.tx_ready:self.store(address,self.raw(address)|1)
        self.cpu.hook_add(UC_HOOK_MEM_READ,ready,begin=0x40004408,end=0x40004408)
        def tx(c,a,address,size,value,u):
            self.sent.append(value&255)
            self.echo_samples.append((self.word('uart_echo_active'),self.word('minute_log',190)))
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,tx,begin=0x40004400,end=0x40004400)
        self.store(0x40004408,1) # SPIN05 TXEPT bit0; bit3 is deliberately clear.

    def wire_record(self,style=3,ending='\r\n'):
        return f'+TIME:Thu Oct 22 14:20:30 2026 +0100 10:00 {style}0{ending}'.encode()

    def consume(self,data):
        for b in data:self.call('uart_probe_consume',b)

    def prepare_echo(self):
        self.start_pwm(3)
        self.setword('minute_log',211,1)
        self.sent=[];self.echo_samples=[]

    def test_echo_exact_complete_record_only_after_settings_processed(self):
        for ending in ('\r\n',):
            self.setUp();self.prepare_echo();wire=self.wire_record(3,ending)
            self.consume(wire[:-1]);self.assertEqual(self.sent,[])
            before=self.word('uart_probe_good_time')
            self.consume(wire[-1:])
            self.assertEqual(bytes(self.sent),b'\n'+wire)
            self.assertEqual(self.word('uart_probe_good_time'),before+1)
            self.assertEqual(self.word('uart_echo_active'),0)
            self.assertTrue(all(active for active,restart in self.echo_samples))
            self.assertEqual(self.word('minute_log',194),1)

    def test_changed_style_is_echoed_before_restart_handover(self):
        self.prepare_echo();wire=self.wire_record(0)
        frozen=self.frozen();writes,hook=self.trace()
        self.consume(wire)
        self.cpu.hook_del(hook)
        self.assertEqual(bytes(self.sent),b'\n'+wire)
        self.assertTrue(all(active==1 and restart==1 for active,restart in self.echo_samples))
        self.assertEqual(self.frozen(),frozen)
        self.assertEqual(self.word('minute_log',190),1)
        self.assertFalse([(a,v) for a,v in writes if 0x40000400<=a<=0x40000440 or a==0xe000ed0c])
        # ISR restart service cannot remove power while the echo owns TX.
        self.setword('uart_echo_active',0,1)
        self.call('mode_restart_service',self.get(4))
        self.assertEqual(self.word('minute_log',190),1)
        self.assertEqual(self.word('minute_log',211),1)
        self.setword('uart_echo_active',0,0)
        self.tick()
        self.assertNotEqual(self.word('seconds_log',220),0) # Normal safe drain begins.

    def test_pending_correction_snapshot_stays_immutable_but_settings_echo(self):
        self.prepare_echo();self.setword('daily_log',0,7)
        addr=self.symbols['uart_probe_time_event'];snapshot=bytes(self.cpu.mem_read(addr,20))
        wire=self.wire_record(3);self.consume(wire)
        self.assertEqual(bytes(self.sent),b'\n'+wire)
        self.assertEqual(bytes(self.cpu.mem_read(addr,20)),snapshot)
        self.assertEqual(self.word('minute_log',194),1)

    def test_bad_incomplete_and_non_time_lines_do_not_echo(self):
        for wire in (b'SLEEP\r\n',b'+TICK\r\n',b'USER_OK\r\n',
                     b'+TIME:garbage\r\n',self.wire_record(3,'\n'),
                     self.wire_record().replace(b'Oct',b'Bad'),
                     b'x'*100+b'\n',b'+TIME:\x00USER\n'):
            self.setUp();self.prepare_echo();self.consume(wire)
            self.assertEqual(self.sent,[],wire)

    def test_fault_rec_clean_and_unpowered_sessions_do_not_echo(self):
        for state in ('fault','parking_fault','rec','clean','off'):
            self.setUp();self.prepare_echo()
            if state=='fault':self.put(2,6)
            if state=='parking_fault':self.put(2,14)
            if state=='rec':self.setword('minute_log',229,1)
            if state=='clean':self.setword('minute_log',230,1)
            if state=='off':self.setword('minute_log',211,0)
            self.consume(self.wire_record())
            self.assertEqual(self.sent,[],state)
            self.assertEqual(self.word('uart_echo_active'),0)

    def test_stalled_uart_is_bounded_and_does_not_trap_restart(self):
        self.prepare_echo();self.tx_ready=False;self.store(0x40004408,0)
        reads=[]
        h=self.cpu.hook_add(UC_HOOK_MEM_READ,
            lambda c,a,address,size,value,u:reads.append(address),begin=0x40004408,end=0x40004408)
        self.consume(self.wire_record(0));self.cpu.hook_del(h)
        self.assertEqual(self.sent,[])
        self.assertGreater(len(reads),100);self.assertLessEqual(len(reads),65537)
        self.assertEqual(self.word('uart_echo_active'),0)
        self.assertEqual(self.word('minute_log',190),1)
        self.assertEqual(self.get(3),0)

    def test_waits_for_final_transmitter_empty_not_just_last_write(self):
        self.prepare_echo();self.tx_ready=False;wire=self.wire_record();reads=[0]
        self.store(0x40004408,1)
        def status(c,a,address,size,value,u):
            if len(self.sent)==len(wire)+1:
                reads[0]+=1;self.store(address,1 if reads[0]>12 else 0)
        h=self.cpu.hook_add(UC_HOOK_MEM_READ,status,begin=0x40004408,end=0x40004408)
        self.consume(wire);self.cpu.hook_del(h)
        self.assertEqual(bytes(self.sent),b'\n'+wire)
        self.assertEqual(reads[0],13)
        self.assertEqual(self.word('uart_echo_active'),0)

    def test_uart_wait_also_obeys_four_tick_deadline(self):
        self.prepare_echo();self.tx_ready=False;self.store(0x40004408,0)
        before=self.get(4);reads=[]
        def progress(c,a,address,size,value,u):
            reads.append(address);self.put(4,self.get(4)+1)
        h=self.cpu.hook_add(UC_HOOK_MEM_READ,progress,begin=0x40004408,end=0x40004408)
        self.consume(self.wire_record(0));self.cpu.hook_del(h)
        self.assertEqual(len(reads),4)
        self.assertEqual(self.get(4)-before,4)
        self.assertEqual(self.word('uart_echo_active'),0)
        self.assertEqual(self.word('minute_log',190),1)

class ButtonTests(ButtonPrior):
    artifact=ARTIFACT
    signature=0x4d50528a
    def setUp(self):
        super().setUp()
        self.cpu.hook_add(UC_HOOK_MEM_READ,lambda c,a,p,s,v,u:
            c.mem_write(p,(int.from_bytes(c.mem_read(p,4),'little')|1).to_bytes(4,'little')),
            begin=0x40004408,end=0x40004408)

class RTCTests(RTCPrior):
    artifact=ARTIFACT
    signature=0x4d50528a
    def setUp(self):
        super().setUp()
        self.cpu.hook_add(UC_HOOK_MEM_READ,lambda c,a,p,s,v,u:
            c.mem_write(p,(int.from_bytes(c.mem_read(p,4),'little')|1).to_bytes(4,'little')),
            begin=0x40004408,end=0x40004408)

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_actual_daily_correction_retains_waveform_then_resumes_all_styles',
            'test_exact_corrected_zero_resumes_with_minute_marker_all_styles',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_timer_stall_watchdog_releases_coils']
    suite=unittest.TestSuite([Tests(n) for n in names]+[
        ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'),
        ButtonTests('test_sleep_closes_lease_without_reply_or_motor_change'),
        RTCTests('test_uart_receives_during_calendar_write_with_compact_storage')])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
