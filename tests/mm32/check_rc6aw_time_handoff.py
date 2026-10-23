"""Actual RC6AW ARM plus independent-correction/timer models, not motor physics."""
import unittest
import datetime as dt
import struct
from pathlib import Path
from check_rc6ak_restart_ramp import Tests as Prior, ButtonTests as ButtonPrior
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PRIMASK

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6aw/build/MM32SPIN05PF_TIME_HANDOFF_RC6AW_20261023.axf'
    signature=0x4d50529a

    def queue_correction(self,style=3,delta=3600,second=5,stage=7,saver=0,hour=14,minute=20,dst=True):
        self.held_fixture(style)
        self.setword('minute_log',192,saver)
        self.put(2,stage);self.put(16,hour);self.put(15,minute);self.put(5,second)
        self.put(22,(hour*60+minute)%720)
        self.bus.data[5:9]=[0x22,4,0x10,0x26]
        self.rtc_time(hour,minute,second)
        target_time=dt.datetime(2026,10,22,hour,minute,second)+dt.timedelta(seconds=delta)
        wire=(target_time.strftime('+TIME:%a %b %d %H:%M:%S %Y')+f' +0100 10:00 {style}{saver}'+(' DST' if dst else '')+'\r\n').encode()
        if stage==1:self.put(6,0)
        self.consume(wire)
        if stage==1:self.put(6,1)
        target=self.result('rtc_event_stamp',self.symbols['uart_probe_time_event'])
        self.setword('seconds_log',227,target-delta)
        self.setword('daily_log',0,2);self.setword('daily_log',12,1)
        self.setword('daily_log',5,self.word('uart_probe_good_time')-1)
        self.call('daily_poll')
        source=self.word('daily_log',7)
        return source,(source if not dst and abs(delta)>60 else source+60-source%60)

    def test_seconds_resume_during_minute_catchup_all_styles(self):
        for style in range(4):
            self.setUp();source,due=self.queue_correction(style)
            writes,hook=self.trace();before=len(self.pad_edges)
            self.setword('seconds_log',227,due);self.call('daily_poll')
            self.assertEqual((self.get(2),self.word('daily_log',13)),(10,3))
            self.assertEqual(self.word('minute_log',151),1)
            for _ in range(32):
                self.tick();self.advance_timer(3906)
                if any(e[2] for e in self.pad_edges[before:]):break
            self.cpu.hook_del(hook)
            self.assertTrue(any(e[2] for e in self.pad_edges[before:]))
            self.assertEqual(self.get(2),10)
            self.assertLess(self.get(22),self.get(24))
            self.assertEqual(self.get(3),0)
            if style < 2:
                self.tick();self.advance_timer(3906)
                self.assertEqual(self.raw(0x40012c2c),959)
            self.assertFalse([(a,v) for a,v in writes if a in
                (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428)])

    def test_seconds_parking_policy_still_applies(self):
        for saver,hour in ((2,14),(1,1)):
            self.setUp();source,due=self.queue_correction(saver=saver,hour=hour)
            before=len(self.pad_edges)
            self.setword('seconds_log',227,due);self.call('daily_poll')
            for _ in range(32):self.tick();self.advance_timer(3906)
            self.assertFalse(any(e[2] for e in self.pad_edges[before:]))
            self.assertEqual(self.get(3),0)

    def handoff_fixture(self,delta=-3600,web=True):
        source,due=self.queue_correction(delta=0)
        self.setword('minute_log',211,1)
        self.setword('minute_log',217,int(web))
        self.setword('minute_log',218,self.get(4)+7680)
        self.setword('minute_log',208,self.word('uart_probe_good_time'))
        self.call('parallel_poll_once') # This iteration's web handler already ran.
        target=dt.datetime(2000,1,1)+dt.timedelta(seconds=source+delta)
        wire=(target.strftime('+TIME:%a %b %d %H:%M:%S %Y')+' +0100 10:00 30\r\n').encode()
        self.sent=[];self.consume(wire+b'SLEEP\r\n')
        self.assertEqual(bytes(self.sent),b'\n'+wire)
        return source

    def test_time_sleep_after_web_poll_cannot_drop_automatic_time(self):
        for web in (False,True):
            self.setUp();source=self.handoff_fixture(web=web)
            writes,hook=self.trace()
            self.call('esp_sleep_poll')
            self.assertEqual(self.word('daily_log',0),2)
            self.assertEqual(self.word('minute_log',211),1)
            self.assertEqual(self.word('minute_log',157),1)
            self.call('parallel_poll_once')
            self.assertEqual(self.word('daily_log',6),source-3600)
            self.assertEqual(self.word('daily_log',0),7)
            self.call('esp_sleep_poll')
            self.assertEqual(self.word('minute_log',211),0)
            self.call('daily_poll')
            self.assertEqual(self.result('rtc_motion_stamp'),source-3600)
            self.assertEqual(self.word('minute_log',204),1)
            self.assertEqual(self.get(3),0)
            self.cpu.hook_del(hook)
            self.assertFalse([(a,v) for a,v in writes if a in
                (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428,0xe000ed0c)])

    def test_runtime_update_does_not_require_web_lease_or_sleep(self):
        source=self.handoff_fixture(delta=3600,web=False)
        self.setword('minute_log',157,0)
        self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',0),7)
        self.assertEqual(self.word('daily_log',6),source+3600)
        self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),source+3600)

    def test_published_time_survives_stage_change_without_being_consumed(self):
        source=self.handoff_fixture(web=False)
        count=self.word('uart_probe_good_time')
        self.put(2,10);self.setword('minute_log',217,1)
        self.call('runtime_time_poll')
        self.assertNotEqual(self.word('minute_log',208),count)
        self.put(4,self.get(4)+10*128);self.put(2,7)
        self.setword('seconds_log',227,source+10)
        self.rtc_time(14,20,15)
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('daily_log',0),2)
        self.call('daily_poll')
        self.assertEqual(self.word('daily_log',6),source-3600+10)

    def test_aligned_sleep_after_web_poll_does_not_create_hold(self):
        for delta in (-1,0,1):
            self.setUp();self.handoff_fixture(delta=delta,web=False)
            self.call('esp_sleep_poll')
            self.assertEqual(self.word('minute_log',211),0)
            self.assertEqual(self.word('daily_log',13),0)
            self.assertNotEqual(self.word('daily_log',0),2)

    def test_dst_skew_keeps_zero_and_releases_all_styles_without_pwm_rebuild(self):
        for style in range(4):
            for skew in (-2,-1,1,2):
                self.setUp();source,due=self.queue_correction(style=style,delta=3600+skew)
                before=len(self.pad_edges);writes,hook=self.trace()
                self.setword('seconds_log',227,due);self.call('daily_poll')
                self.assertEqual(self.result('rtc_motion_stamp'),due+3600,(style,skew))
                self.assertEqual(self.get(5),0)
                for _ in range(32):
                    self.tick();self.advance_timer(3906)
                    if any(e[2] for e in self.pad_edges[before:]):break
                self.cpu.hook_del(hook)
                self.assertTrue(any(e[2] for e in self.pad_edges[before:]),(style,skew))
                self.assertEqual(self.get(2),10)
                self.assertEqual(self.get(3),0)
                self.assertFalse([(a,v) for a,v in writes if a in
                    (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428)])

    def test_dst_backward_half_hour_and_midnight_phase(self):
        for delta,hour,minute in ((-3601,14,20),(-3599,14,20),
                (1799,14,20),(1801,14,20),(-1801,14,20),
                (3601,23,59),(-3601,0,0)):
            self.setUp();source,due=self.queue_correction(delta=delta,hour=hour,minute=minute,second=59)
            self.setword('seconds_log',227,due);self.call('daily_poll')
            whole=(1 if delta>0 else -1)*((abs(delta)+30)//60)*60
            self.assertEqual(self.result('rtc_motion_stamp'),due+whole,(delta,hour,minute))
            self.assertEqual(self.get(5),0)
            self.assertEqual(self.word('minute_log',204),int(delta < -60))
            self.assertEqual(self.get(3),0)

    def test_late_dst_application_preserves_actual_old_seconds_not_fake_zero(self):
        source,due=self.queue_correction(delta=3601)
        self.setword('seconds_log',227,due+2);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),due+3602)
        self.assertEqual(self.get(5),2)
        self.assertEqual(self.word('minute_log',187),0)
        self.assertEqual(self.word('minute_log',152),1)

    def test_calendar_phase_alignment_rollovers_and_range_guards(self):
        for text,second in (('2026-01-01T00:00:01',0),('2026-01-01T00:00:00',59),
                ('2026-12-31T23:59:59',0),('2028-03-01T00:00:00',59),
                ('2026-03-01T00:00:00',59),('2026-02-28T23:59:59',0),
                ('2028-02-28T23:59:59',0),('2028-02-29T23:59:59',0)):
            value=dt.datetime.fromisoformat(text);e=bytearray(20)
            struct.pack_into('<Hh',e,0,value.year,60)
            e[4:9]=bytes((value.month,value.day,value.hour,value.minute,value.second));e[19]=1
            ptr=self.symbols['uart_probe_time_event'];self.cpu.mem_write(ptr,bytes(e))
            shift=second-value.second
            if shift>30:shift-=60
            if shift < -30:shift+=60
            expected=value+dt.timedelta(seconds=shift)
            self.assertEqual(self.result('rtc_event_align_seconds',ptr,second),1)
            self.assertEqual(self.result('rtc_event_stamp',ptr),int((expected-dt.datetime(2000,1,1)).total_seconds()))
            self.assertEqual(bytes(self.cpu.mem_read(ptr+19,1)),b'\x01')
        for year,month,day,hour,minute,second,phase in ((2000,1,1,0,0,0,59),
                (2099,12,31,23,59,59,0),(2026,1,1,0,0,0,60)):
            e=bytearray(20);struct.pack_into('<H',e,0,year)
            e[4:9]=bytes((month,day,hour,minute,second));self.cpu.mem_write(ptr,bytes(e))
            self.assertEqual(self.result('rtc_event_align_seconds',ptr,phase),0)

    def test_dst_suffix_strict_and_event_abi_unchanged(self):
        self.cpu.mem_map(0x20002000,4096)
        base=b'+TIME:Thu Oct 22 14:20:30 2026 +0100 10:00'
        for suffix,valid,dst in ((b'30\r\n',1,0),(b'30 DST\r\n',1,1),
                (b' 3 0 DST\r\n',1,1),(b' DST\r\n',1,1),
                (b'30 DSTX\r\n',0,0),(b'30 DST DST\r\n',0,0),
                (b'30 DS\r\n',0,0),(b'30 DST\n',0,0),(b'30 dst\r\n',0,0)):
            wire=base+suffix;self.cpu.mem_write(0x20002000,wire)
            self.cpu.mem_write(0x20002100,b'\xa5'*24)
            self.assertEqual(self.result('mm32_uart_parse_esp_line',0x20002000,len(wire),0x20002100),valid,wire)
            out=bytes(self.cpu.mem_read(0x20002100,24))
            if valid:
                self.assertEqual(out[19],dst);self.assertEqual(out[20:],b'\xa5'*4)
            else:self.assertEqual(out,b'\xa5'*24)

    def test_unflagged_threshold_and_dst_boundary_all_styles(self):
        for style in range(4):
            for delta,dst in ((3600,False),(-3600,False),(61,False),(-61,False),
                              (60,False),(-60,False),(3600,True)):
                self.setUp();source,due=self.queue_correction(style=style,delta=delta,dst=dst)
                self.assertEqual(self.word('minute_log',150),due)
                before=list(self.bus.calendar_writes)
                self.setword('seconds_log',227,source);self.call('daily_poll')
                if due>source:self.assertEqual(self.bus.calendar_writes,before)
                else:
                    self.assertEqual(self.result('rtc_motion_stamp'),source+delta)
                    self.assertEqual(self.word('minute_log',204),int(delta < -60))
                self.assertEqual(self.get(3),0)

    def test_immediate_correction_still_finishes_powered_pulse(self):
        source,due=self.queue_correction(dst=False)
        self.setword('minute_active',0,1);before=list(self.bus.calendar_writes)
        self.call('daily_poll');self.assertEqual(self.bus.calendar_writes,before)
        self.setword('minute_active',0,0);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),source+3600)

    def test_catchup_save_echo_sleep_retains_latest_and_ages_it(self):
        source,due=self.queue_correction(delta=0)
        self.put(2,10);self.setword('daily_log',13,3);self.setword('minute_log',211,1)
        count=self.word('uart_probe_good_time');before=self.frozen()
        for delta in (-7200,-3600):
            target=dt.datetime(2000,1,1)+dt.timedelta(seconds=source+delta)
            wire=(target.strftime('+TIME:%a %b %d %H:%M:%S %Y')+' +0100 10:00 30\r\n').encode()
            self.sent=[];self.consume(wire)
            self.assertEqual(bytes(self.sent),b'\n'+wire)
        self.assertEqual(self.word('uart_probe_good_time'),count)
        self.assertTrue(self.word('minute_log',155)&0x80000000)
        self.consume(b'SLEEP\r\n');self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',211),0)
        self.assertTrue(self.word('minute_log',155)&0x80000000)
        self.assertEqual(self.frozen(),before)
        self.put(4,self.get(4)+15*128);self.put(2,7);self.setword('daily_log',13,0)
        self.setword('seconds_log',227,source+15)
        self.rtc_time(14,20,20)
        self.call('pending_time_poll')
        self.assertEqual(self.word('daily_log',0),2)
        self.assertEqual(self.word('minute_log',155),0)
        self.call('daily_poll')
        self.assertEqual(self.word('daily_log',6),source-3600+15)
        self.assertEqual(self.word('minute_log',150),source+15)
        self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),source-3600+15)
        self.assertEqual(self.word('minute_log',204),1)
        self.assertEqual(self.get(3),0)

    def test_mailbox_survives_native_backward_rehome(self):
        source,due=self.queue_correction(delta=-3600)
        self.consume(self.wire_record())
        mailbox=[self.word('minute_log',i) for i in range(153,157)]
        self.assertTrue(mailbox[2]&0x80000000)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        for _ in range(32):
            self.tick()
            if self.get(2)==1:break
        self.assertEqual(self.get(2),1)
        self.assertEqual([self.word('minute_log',i) for i in range(153,157)],mailbox)

    def test_aligned_deferred_retry_does_not_start_another_correction(self):
        source,due=self.queue_correction(delta=0)
        self.put(2,10);self.setword('daily_log',13,3)
        target=dt.datetime(2000,1,1)+dt.timedelta(seconds=source)
        self.consume((target.strftime('+TIME:%a %b %d %H:%M:%S %Y')+' +0100 10:00 30\r\n').encode())
        self.put(2,7);self.setword('daily_log',13,0)
        self.call('pending_time_poll')
        self.assertEqual(self.word('minute_log',155),0)
        self.assertNotEqual(self.word('daily_log',0),2)
        self.assertEqual(self.word('daily_log',13),0)

    def test_pending_flag_offset_schedule_midnight_and_tick_wrap(self):
        self.queue_correction(delta=0)
        self.put(2,11);self.setword('daily_log',13,3);self.put(4,0xffffff80)
        self.setword('minute_log',211,1)
        wire=b'+TIME:Thu Oct 22 23:59:59 2026 -0530 23:5930 DST\r\n'
        pending_at_echo=[]
        hook=self.cpu.hook_add(UC_HOOK_MEM_WRITE,
            lambda c,a,address,size,value,u:pending_at_echo.append(self.word('minute_log',155)),
            begin=0x40004400,end=0x40004400)
        self.consume(wire);self.cpu.hook_del(hook)
        self.assertTrue(pending_at_echo)
        self.assertTrue(all(v&0x80000000 for v in pending_at_echo))
        self.put(4,256);self.put(2,7);self.setword('daily_log',13,0)
        self.call('pending_time_poll')
        e=bytes(self.cpu.mem_read(self.symbols['uart_probe_time_event'],20))
        self.assertEqual(e[2:4],(-330).to_bytes(2,'little',signed=True))
        self.assertEqual(e[4:11],bytes((10,23,0,0,2,23,59)))
        self.assertEqual(e[19],1)
        self.assertEqual(self.word('minute_log',155),0)

    def test_corrected_nonzero_seconds_wait_all_styles(self):
        for style in range(4):
            for delta in (3601,3602,3599,-1):
                self.setUp();source,due=self.queue_correction(style=style,delta=delta,dst=False)
                self.setword('seconds_log',227,due);self.call('daily_poll')
                before=len(self.pad_edges)
                self.assertEqual(self.word('minute_log',152),1)
                for _ in range(16):self.tick();self.advance_timer(3906)
                self.assertFalse(any(e[2] for e in self.pad_edges[before:]),(style,delta))
                self.assertEqual(self.get(30),1)
                # A stale boundary/grace cannot release at nonzero seconds,
                # including after minute catch-up relinquishes ownership.
                self.setword('daily_log',13,0)
                self.setword('minute_log',151,0)
                self.setword('minute_log',187,1)
                for _ in range(4):self.tick();self.advance_timer(3906)
                self.assertFalse(any(e[2] for e in self.pad_edges[before:]))
                self.assertEqual(self.word('minute_log',152),1)
                # Only the next real corrected-calendar :00 releases it.
                self.put(5,0);self.fixture_clock()
                self.setword('rtc_boundary',0,1)
                for _ in range(32):
                    self.tick();self.advance_timer(3906)
                    if any(e[2] for e in self.pad_edges[before:]):break
                self.assertTrue(any(e[2] for e in self.pad_edges[before:]),(style,delta))
                self.assertEqual(self.word('minute_log',152),0)
                self.assertEqual(self.get(3),0)

    def test_seconds_use_corrected_zero_for_non_minute_offset(self):
        source,due=self.queue_correction(delta=21630,dst=False)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        before=len(self.pad_edges)
        for _ in range(16):self.tick();self.advance_timer(3906)
        self.assertFalse(any(e[2] for e in self.pad_edges[before:]))
        # Six-hour minute catch-up is still busy when corrected seconds reach00.
        self.put(15,22);self.put(5,0);self.fixture_clock()
        self.rtc_time(20,22,0);self.setword('rtc_boundary',0,1)
        for _ in range(32):
            self.tick();self.advance_timer(3906)
            if any(e[2] for e in self.pad_edges[before:]):break
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.get(2),10)
        self.assertTrue(any(e[2] for e in self.pad_edges[before:]))

    def test_catchup_completion_clears_owner_without_reparking_seconds(self):
        source,due=self.queue_correction()
        self.setword('seconds_log',227,due);self.call('daily_poll')
        corrected=self.result('rtc_motion_stamp');writes,hook=self.trace()
        for elapsed in range(3200):
            if elapsed and elapsed%128==0:
                sod=(corrected+elapsed//128)%86400
                self.rtc_time(sod//3600,sod//60%60,sod%60);self.rtc_poll()
            self.tick();self.advance_timer(3906)
            self.assertEqual(self.get(3),0,(elapsed,self.get(3)))
            if self.get(2)==7:break
        self.cpu.hook_del(hook)
        self.assertEqual(self.get(2),7)
        self.assertEqual(self.get(26),1)
        self.assertEqual(self.word('daily_log',13),0)
        self.assertEqual(self.word('minute_log',151),0)
        self.assertGreater(sum(bool(e[2]) for e in self.pad_edges),100)
        self.assertFalse([(a,v) for a,v in writes if a in
            (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428)])

    def test_small_backward_seconds_resume_without_rehome(self):
        source,due=self.queue_correction(delta=-60)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        before=len(self.pad_edges)
        for _ in range(32):
            self.tick();self.advance_timer(3906)
            if any(e[2] for e in self.pad_edges[before:]):break
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('minute_log',204),0)
        self.assertTrue(any(e[2] for e in self.pad_edges[before:]))

    def web_time_fixture(self,delta=-3600,wake='10:00'):
        source,due=self.queue_correction(delta=0)
        self.setword('minute_log',217,1)
        self.setword('minute_log',218,self.get(4)+7680)
        self.setword('minute_log',211,1)
        self.setword('minute_log',208,self.word('uart_probe_good_time'))
        target=dt.datetime(2000,1,1)+dt.timedelta(seconds=source+delta)
        wire=(target.strftime('+TIME:%a %b %d %H:%M:%S %Y')+f' +0100 {wake} 30\r\n').encode()
        self.sent=[];self.consume(wire)
        return source,(source if abs(delta)>60 else due),wire

    def test_web_save_backward_queues_before_sleep_then_rehomes(self):
        source,due,wire=self.web_time_fixture()
        before=self.frozen();writes,hook=self.trace()
        entered=[]
        h=self.cpu.hook_add(UC_HOOK_CODE,lambda c,a,s,u:entered.append(self.word('daily_log',0)),
            begin=self.symbols['daily_poll']&~1,end=self.symbols['daily_poll']&~1)
        self.consume(b'SLEEP\r\n')
        self.call('parallel_poll_once');self.cpu.hook_del(h)
        self.assertIn(2,entered)
        self.assertEqual(self.word('daily_log',0),7)
        self.assertEqual(self.frozen(),before)
        self.assertEqual(bytes(self.sent),b'\n'+wire)
        self.assertEqual(self.word('minute_log',150),due)
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.word('daily_log',0),7)
        # Unflagged large changes are admitted now, not at the old :00.
        self.assertEqual(due,source)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),due-3600)
        self.assertEqual(self.word('minute_log',204),1)
        self.cpu.hook_del(hook)
        self.assertFalse([(a,v) for a,v in writes if a in
            (0x40000400,0x40000408,0x40000414,0x40000424,0x40000428,0xe000ed0c)])

    def test_web_save_forward_uses_independent_seconds_policy(self):
        source,due,wire=self.web_time_fixture(3600)
        self.call('parallel_poll_once')
        self.setword('seconds_log',227,due);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),due+3600)
        self.assertEqual(self.word('daily_log',13),3)
        self.assertEqual(self.word('minute_log',204),0)
        self.assertEqual(self.get(26),1)

    def test_repeated_aligned_web_times_do_not_park_clock(self):
        for delta in (-2,-1,0,1,2):
            self.setUp();self.web_time_fixture(delta)
            self.call('parallel_poll_once')
            self.assertEqual(self.word('daily_log',0),3)
            self.assertEqual(self.word('minute_log',150),0)
            self.assertEqual(self.word('daily_log',13),0)

    def test_schedule_only_web_save_refreshes_schedule(self):
        self.web_time_fixture(0,'11:20')
        self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',0),3)
        self.assertEqual([self.word('daily_log',i) for i in (10,11)],[11,20])
        self.assertNotEqual(self.word('daily_log',3),0)
        self.assertEqual(self.word('minute_log',150),0)

    def test_web_pending_correction_snapshot_remains_immutable(self):
        source,due,wire=self.web_time_fixture()
        self.call('parallel_poll_once')
        before=[self.word('daily_log',i) for i in (6,7)]
        snapshot=bytes(self.cpu.mem_read(self.symbols['uart_probe_time_event'],20))
        self.consume(self.wire_record())
        self.call('parallel_poll_once')
        self.assertEqual([self.word('daily_log',i) for i in (6,7)],before)
        self.assertEqual(bytes(self.cpu.mem_read(self.symbols['uart_probe_time_event'],20)),snapshot)

    def test_large_backward_rehomes_all_styles_and_parking_preserving_settings(self):
        for style in range(4):
            for saver in (0,1,2):
                self.setUp();source,due=self.queue_correction(style,delta=-3600,saver=saver)
                self.setword('seconds_log',227,due);self.call('daily_poll')
                self.assertEqual(self.word('minute_log',204),1)
                self.assertEqual(self.word('daily_log',13),0)
                corrected=self.result('rtc_motion_stamp')
                schedule=self.word('daily_log',3)
                settings=[self.word('minute_log',i) for i in (188,189,192,195)]
                count=self.word('uart_probe_good_time')
                for _ in range(32):
                    self.tick()
                    if self.get(2)==1:break
                self.assertEqual((self.get(2),self.get(3)),(1,0))
                self.assertEqual(self.word('minute_log',204),3)
                self.assertEqual(self.word('minute_log',229),0)
                self.assertEqual([self.word('minute_log',i) for i in (188,189,192,195)],settings)
                self.assertEqual(self.result('rtc_motion_stamp'),corrected)
                self.assertEqual(self.word('daily_log',3),schedule)
                self.assertEqual(self.word('uart_probe_good_time'),count)
                self.assertEqual(self.get(6),1)

    def test_backward_recovery_completes_sensor_homing(self):
        source,due=self.queue_correction(delta=-3600)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        corrected=self.result('rtc_motion_stamp')
        schedule=self.word('daily_log',3)
        for elapsed in range(1,6500):
            if elapsed%128==0:
                sod=(corrected+elapsed//128)%86400
                self.rtc_time(sod//3600,sod//60%60,sod%60)
                self.rtc_poll()
            if self.get(19)==2:
                high=int(self.get(20)+int(bool(self.word('minute_active')))>=73)
            else:
                high=int(246<=self.word('seconds_log',5)+1<=262)
            self.tick(high)
            self.assertEqual(self.get(3),0,(elapsed,self.get(3)))
            if self.word('minute_log',204)==0 and self.get(7) and self.get(8):break
        self.assertEqual((self.get(7),self.get(8)),(1,1))
        self.assertEqual(self.word('minute_log',204),0)
        self.assertEqual(self.word('daily_log',3),schedule)
        self.assertEqual(self.word('minute_log',229),0)

    def test_backward_threshold_small_holds_large_rehomes(self):
        for delta in (-1,-60,-61):
            self.setUp();source,due=self.queue_correction(delta=delta,dst=False)
            self.setword('seconds_log',227,due);self.call('daily_poll')
            self.assertEqual(self.result('rtc_motion_stamp'),due+delta)
            self.assertEqual(self.word('minute_log',204),int(delta < -60))
            self.assertEqual(self.word('daily_log',13),0 if delta < -60 else 3)
            self.assertEqual(self.get(3),0)

    def test_startup_backward_does_not_schedule_extra_rehome(self):
        source,due=self.queue_correction(delta=-3600,stage=1)
        self.put(2,7);self.call('daily_poll')
        self.assertEqual(self.word('minute_log',204),0)
        self.assertEqual(self.result('rtc_motion_stamp'),source-3600)

    def test_rec_has_priority_over_backward_rehome(self):
        source,due=self.queue_correction(delta=-3600)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        self.setword('minute_log',229,1);self.setword('minute_log',227,2)
        for _ in range(32):
            self.tick()
            if self.get(2)==1:break
        self.assertEqual(self.word('minute_log',229),1)
        self.assertNotEqual(self.word('minute_log',204),3)
        self.assertEqual(self.get(3),0)

    def test_runtime_waits_old_boundary_all_styles_and_parking(self):
        for style in range(4):
            for saver in (0,1,2):
                self.setUp();source,due=self.queue_correction(style,saver=saver)
                self.assertEqual(self.word('minute_log',150),due)
                self.assertEqual(self.word('daily_log',13),1)
                before=list(self.bus.calendar_writes);frozen=self.frozen()
                for now in (source,source+10,due-1):
                    self.setword('seconds_log',227,now);self.call('daily_poll')
                    self.assertEqual(self.bus.calendar_writes,before)
                    self.assertEqual(self.frozen(),frozen)
                    self.assertEqual(self.get(3),0)
                self.setword('seconds_log',227,due);self.call('daily_poll')
                self.assertEqual(self.get(3),0)
                self.assertEqual(self.word('daily_log',13),3)
                self.assertEqual(self.word('minute_log',150),0)
                self.assertEqual(self.result('rtc_motion_stamp'),due+3600)
                self.assertEqual(self.frozen(),frozen)

    def test_backward_change_ages_snapshot_to_boundary(self):
        source,due=self.queue_correction(delta=-3600,second=59)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),due-3600)
        self.assertEqual(self.word('daily_log',13),0)
        self.assertEqual(self.word('minute_log',204),1)
        self.assertEqual(self.get(3),0)

    def test_old_clock_midnight_boundary(self):
        source,due=self.queue_correction(delta=-3600,second=59,hour=23,minute=59)
        self.assertEqual(due%86400,0)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),due-3600)
        self.assertEqual(self.get(3),0)

    def test_late_poll_does_not_miss_boundary(self):
        source,due=self.queue_correction()
        self.setword('seconds_log',227,due+2);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),due+3602)
        self.assertEqual(self.get(3),0)

    def test_motor_busy_still_defers_after_boundary(self):
        source,due=self.queue_correction();self.setword('minute_active',0,1)
        before=list(self.bus.calendar_writes)
        self.setword('seconds_log',227,due);self.call('daily_poll')
        self.assertEqual(self.bus.calendar_writes,before)
        self.setword('minute_active',0,0);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),due+3600)

    def test_timeout_budget_starts_at_boundary(self):
        source,due=self.queue_correction(second=0)
        self.assertEqual(due-source,60)
        self.put(30,0)
        self.setword('seconds_log',227,due+69);self.call('daily_poll')
        self.assertEqual(self.get(3),0)
        self.setword('seconds_log',227,due+71);self.call('daily_poll')
        self.assertEqual(self.get(3),5)

    def test_startup_pending_correction_has_no_new_boundary_wait(self):
        source,due=self.queue_correction(stage=1)
        self.assertEqual(self.word('minute_log',150),0)
        self.call('daily_poll');self.assertEqual(self.word('daily_log',13),1)
        self.put(2,7);self.call('daily_poll')
        self.assertEqual(self.result('rtc_motion_stamp'),source+3600)
        self.assertEqual(self.get(3),0)

    def test_matching_time_does_not_queue_boundary(self):
        self.queue_correction(delta=0)
        self.assertEqual(self.word('daily_log',0),3)
        self.assertEqual(self.word('minute_log',150),0)

    def uart_fixture(self):
        self.prepare_echo();self.put(4,512)
        self.store(0x48000008,8);self.store(0x40004408,1)
        self.call('uart_link_configure')
        self.assertEqual(self.raw(0x40004420),13)
        self.assertEqual(self.raw(0x40004424),4)

    def test_boot_burst_counted_rejected_but_never_arms_recovery(self):
        self.uart_fixture();self.setword('minute_log',148,512)
        for tick in (512,520,639):
            self.put(4,tick)
            for _ in range(40):self.error(0x20)
        self.assertEqual(self.word('minute_log',140),120)
        self.assertEqual(self.word('minute_log',149),120)
        self.assertEqual(self.word('minute_log',145),0)
        self.assertEqual(self.word('rx_fault'),1)
        self.put(4,700);self.call('uart_recovery_poll')
        self.assertEqual(self.word('minute_log',146),0)

    def test_post_boot_errors_recover_without_extending_window(self):
        self.uart_fixture();self.setword('minute_log',148,512)
        self.put(4,639);self.error(0x20)
        self.assertEqual(self.word('minute_log',145),0)
        self.put(4,640)
        for _ in range(8):self.error(0x20)
        self.put(4,644);self.call('uart_recovery_poll')
        self.assertEqual(self.word('minute_log',146),1)
        self.assertEqual(self.word('minute_log',148),512)
        self.error(0x20)
        self.assertEqual(self.word('minute_log',145),1)

    def test_boot_window_tick_wrap(self):
        self.uart_fixture();self.setword('minute_log',148,0xffffffc0)
        self.put(4,63);self.error(0x20)
        self.assertEqual(self.word('minute_log',145),0)
        self.put(4,64);self.error(0x20)
        self.assertEqual(self.word('minute_log',145),1)

    def test_early_valid_time_is_accepted_and_echoed(self):
        self.uart_fixture();self.setword('minute_log',148,512)
        before=self.word('uart_probe_good_time');wire=self.wire_record()
        self.consume(wire)
        self.assertEqual(self.word('uart_probe_good_time'),before+1)
        self.assertEqual(bytes(self.sent),b'\n'+wire)

    def test_only_real_power_wake_starts_window(self):
        self.uart_fixture();self.setword('minute_log',211,0)
        self.put(4,700);self.call('radio_on')
        self.assertEqual(self.word('minute_log',148),700)
        self.put(4,720);self.call('radio_on')
        self.assertEqual(self.word('minute_log',148),700)
        self.setword('minute_log',211,0)
        self.put(4,900);self.call('radio_on')
        self.assertEqual(self.word('minute_log',148),900)

    def error(self,flags):
        self.store(0x4000440c,flags);self.store(0x40004408,1)
        self.call('UART2_Handler')
        self.store(0x4000440c,0)

    def test_separate_hardware_error_observations(self):
        self.uart_fixture()
        for flag in (0x08,0x10,0x20,0x38):self.error(flag)
        self.assertEqual(self.word('uart_probe_uart_errors'),4)
        self.assertEqual([self.word('minute_log',i) for i in (140,141,142)],[2,2,2])
        self.assertEqual(self.word('minute_log',143),0x38)
        self.assertEqual(self.word('minute_log',145),4)
        self.assertEqual(self.word('minute_log',144),512)

    def pending_recovery(self):
        self.uart_fixture()
        for _ in range(10):self.error(0x20)
        self.assertEqual(self.word('minute_log',145),8)
        self.put(4,516)

    def test_idle_recovery_reconfigures_uart_not_motor_or_clocks(self):
        self.pending_recovery();frozen=self.frozen();writes,hook=self.trace()
        self.call('uart_recovery_poll');self.cpu.hook_del(hook)
        self.assertEqual(self.word('minute_log',146),1)
        self.assertEqual(self.word('minute_log',145),0)
        self.assertEqual(self.word('minute_log',147),516)
        self.assertEqual((self.raw(0x40004420),self.raw(0x40004424)),(13,4))
        self.assertEqual(self.frozen(),frozen)
        self.assertFalse([(a,v) for a,v in writes if 0x40000400<=a<=0x40000450 or
                          0x40012c00<=a<=0x40012c50 or 0x40021000<=a<=0x40021024 or
                          a in (0xe000ed0c,0x48000414)])

    def test_recovery_defers_in_unsafe_or_busy_conditions(self):
        for condition in ('recent','tx','rx','low','echo','restart','rec','clean','fault','faultpark','off','cooldown'):
            self.setUp();self.pending_recovery()
            if condition=='recent':self.put(4,515)
            if condition=='tx':self.tx_ready=False;self.store(0x40004408,0)
            if condition=='rx':self.store(0x40004408,3)
            if condition=='low':self.store(0x48000008,0)
            if condition=='echo':self.setword('uart_echo_active',0,1)
            if condition=='restart':self.setword('minute_log',190,1)
            if condition=='rec':self.setword('minute_log',229,1)
            if condition=='clean':self.setword('minute_log',230,1)
            if condition=='fault':self.put(2,6)
            if condition=='faultpark':self.put(2,14)
            if condition=='off':self.setword('minute_log',211,0)
            if condition=='cooldown':self.setword('minute_log',147,500)
            self.call('uart_recovery_poll')
            self.assertEqual(self.word('minute_log',146),0,condition)

    def test_clean_time_cancels_pending_recovery_and_echoes(self):
        self.pending_recovery();wire=self.wire_record()
        self.consume(wire)
        self.assertEqual(self.word('minute_log',145),0)
        self.assertEqual(bytes(self.sent),b'\n'+wire)
        self.call('uart_recovery_poll')
        self.assertEqual(self.word('minute_log',146),0)

    def test_after_recovery_accepts_next_whole_record_and_still_rejects_corruption(self):
        self.pending_recovery();self.call('uart_recovery_poll')
        before=self.word('uart_probe_good_time')
        self.consume(b'+TIME:broken\r\n')
        self.assertEqual(self.word('uart_probe_good_time'),before)
        wire=self.wire_record();self.consume(wire)
        self.assertEqual(self.word('uart_probe_good_time'),before+1)
        self.assertEqual(bytes(self.sent),b'\n'+wire)

    def test_rate_limit_and_tick_rollover(self):
        self.pending_recovery();self.call('uart_recovery_poll')
        for _ in range(8):self.error(0x08)
        self.put(4,643);self.call('uart_recovery_poll')
        self.assertEqual(self.word('minute_log',146),1)
        self.put(4,644);self.call('uart_recovery_poll')
        self.assertEqual(self.word('minute_log',146),2)
        self.setword('minute_log',145,8)
        self.setword('minute_log',144,0xfffffffe)
        self.setword('minute_log',147,0xffffff00)
        self.setword('minute_log',148,0xffffff00)
        self.put(4,2);self.call('uart_recovery_poll')
        self.assertEqual(self.word('minute_log',146),3)

    def test_existing_irq_mask_is_preserved_without_recovery(self):
        self.pending_recovery()
        self.cpu.reg_write(UC_ARM_REG_PRIMASK,1)
        self.call('uart_recovery_poll')
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),1)
        self.assertEqual(self.word('minute_log',146),0)
        self.cpu.reg_write(UC_ARM_REG_PRIMASK,0)

    def test_actual_wake_initializes_matching_baud_without_motor_rebuild(self):
        self.uart_fixture();writes,hook=self.trace();before=self.frozen()
        self.call('radio_on');self.cpu.hook_del(hook)
        self.assertEqual((self.raw(0x40004420),self.raw(0x40004424)),(13,4))
        self.assertEqual(self.raw(0x4000441c),0x30)
        self.assertEqual(self.raw(0x40004418),0x19)
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(self.frozen(),before)
        self.assertFalse([(a,v) for a,v in writes if 0x40000400<=a<=0x40000450 or
                          0x40012c00<=a<=0x40012c50])

class ButtonTests(ButtonPrior):
    artifact=Tests.artifact
    signature=Tests.signature

if __name__=='__main__':
    names=[n for n in Tests.__dict__ if n.startswith('test_')]
    names+=['test_echo_exact_complete_record_only_after_settings_processed',
            'test_sleep_closes_lease_without_reply_or_motor_change',
            'test_powered_pulses_finish_then_esp_off_then_exactly_one_reset',
            'test_bad_incomplete_and_non_time_lines_do_not_echo',
            'test_stop_modes_first_pulse_normal_then32_safe_updates',
            'test_daily_correction_resumes_all_styles_without_rebuilding_timer']
    suite=unittest.TestSuite(Tests(n) for n in names)
    suite.addTest(ButtonTests('test_mset_wakes_during_each_correction_stage_without_motor_changes'))
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not r.wasSuccessful())
