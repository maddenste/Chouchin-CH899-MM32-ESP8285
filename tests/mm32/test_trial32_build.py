"""Compiled daily wake, UART-during-I2C, optical phase and authorized RTC update."""
import struct
import unittest
import test_trial29_build as prior
import test_reference_scan_build as ref
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_PC

class Tests(prior.Tests):
    minute_settle_ticks=55
    minute_gate_ticks=70
    artifact=ref.ROOT/'build/MM32SPIN05PF_DAILY_WAKE_SYNC_TRIAL32_20261008.axf'
    signature=0x4d503332
    defines=prior.Tests.defines+['-DDAILY_WAKE_TEST','-DDAILY_WAKE_REVISED']
    test_run_budget_cannot_get_ahead_of_rtc_and_minutes_do_not_pause_seconds=None
    test_full_homing_release_and_two_minutes_rtc_paced=None

    def setUp(self):
        super().setUp()
        def clear_rx(uc,access,a,size,v,user):
            if a==0x40004414 and v&2:
                csr=struct.unpack('<I',uc.mem_read(0x40004408,4))[0]
                uc.mem_write(0x40004408,struct.pack('<I',csr&~2))
            if a==0x40004414 and v&24: uc.mem_write(0x4000440c,struct.pack('<I',0))
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,clear_rx)
    def setword(self,name,i,v):
        self.cpu.mem_write(self.symbols[name]+4*i,struct.pack('<I',v))
    def running(self):
        self.put(1,1);self.tick();self.seed()
        self.put(2,7);self.put(7,1);self.put(8,1);self.put(26,1)
        self.put(22,705);self.put(18,self.get(4))
        self.call('parallel_seconds_runtime_begin');self.call('parallel_poll_once')
    def due(self):
        self.setword('daily_log',3,self.word('daily_log',3)-120)
        self.call('parallel_poll_once')
    def feed(self,line):
        for b in line:
            self.cpu.mem_write(0x40004408,struct.pack('<I',2))
            self.cpu.mem_write(0x40004404,struct.pack('<I',b))
            self.call('parallel_poll_once')
    def test_request_red_until_real_time_and_counters_untouched(self):
        self.running();self.put(13,12);self.due()
        self.assertEqual(self.get(13),12);self.assertEqual(self.get(28),4)
        for _ in range(200):self.tick()
        self.assertEqual(self.get(28),4);self.assertFalse(not bool(self.output&8))
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.get(28),2);start=self.get(29);flashes=0;last=False
        for _ in range(384):
            self.tick();blue=not bool(self.output&8)
            expected=self.get(4)-start<384 and ((self.get(4)-start)//8)%8==6
            self.assertEqual(blue,expected)
            flashes+=int(blue and not last);last=blue
            # Hold the mock RTC-edge watchdog fresh for this LED-only test.
            self.cpu.mem_write(self.symbols['rtc_edge_tick'],struct.pack('<I',self.get(4)))
        self.assertEqual(flashes,6);self.assertEqual(self.get(28),3)
        self.assertEqual(self.get(13),12)
    def test_timeout_leds_off_and_motion_continues(self):
        self.running();self.due();self.setword('daily_log',14,self.word('daily_log',14)-120)
        self.call('parallel_poll_once');self.assertEqual(self.word('daily_log'),5)
        self.assertEqual((self.get(2),self.get(3)),(7,0));self.assertEqual(self.get(28),0)
    def test_daily_wake_cannot_repeat_today_after_backward_adjustment(self):
        self.running();self.setword('daily_log',1,1);self.due()
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 23:46\r\n')
        now=self.word('daily_log',7);target=self.word('daily_log',3)
        self.assertEqual(target//86400,now//86400+1)
        self.assertEqual(target%86400,23*3600+46*60)
    def test_backward_time_correction_keeps_guard_active_for_other_jumps(self):
        self.running();self.due()
        self.feed(b'+TIME:Wed Oct  7 23:45:18 2026 +0100 09:00\r\n')
        self.put(30,1);self.call('parallel_poll_once')
        self.assertEqual(self.get(5),18);self.assertEqual(self.get(3),0)
        self.rtc_time(23,45,30);self.tick();self.tick();self.call('parallel_poll_once')
        if '-DRELEASE_HARDENING' in self.defines:
            # The clock is still in correction/catch-up, not trusted stage7.
            self.assertEqual((self.get(2),self.get(3)),(6,9))
            self.assertEqual(self.word('release_state',0),2)
            self.released()
        else:
            self.assertEqual((self.get(2),self.get(3)),(6,9))
    def test_clean_response_can_recover_from_prior_uart_error(self):
        self.running();self.due()
        self.cpu.mem_write(0x4000440c,struct.pack('<I',8))
        self.feed(b'damaged\r\n')
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log'),3);self.assertEqual(self.get(3),0)
    def test_i2c_reads_service_incoming_uart_burst(self):
        self.running();self.due();data=iter(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        state={'reads':0,'sent':0}
        def receive(uc,access,a,size,v,user):
            if a==0x40004408:
                state['reads']+=1
                # Arrivals during the RTC transaction, every fourth service slot.
                if state['reads']%4==0:
                    b=next(data,None)
                    if b is not None:
                        state['sent']+=1;uc.mem_write(0x40004404,struct.pack('<I',b))
                        uc.mem_write(a,struct.pack('<I',2))
        handle=self.cpu.hook_add(UC_HOOK_MEM_READ,receive)
        self.tick();self.tick();self.call('parallel_poll_once')
        self.cpu.hook_del(handle)
        self.assertEqual(state['sent'],44)
        self.assertEqual(self.word('daily_log'),3)
        self.assertEqual(self.word('uart_probe_uart_errors'),0)
    def test_authorized_correction_waits_at_12_and_reseeds_guard(self):
        self.running();self.due()
        self.feed(b'+TIME:Wed Oct  7 23:46:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log'),7);self.assertEqual(self.word('daily_log',8),0)
        self.put(30,1);self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log'),3);self.assertEqual(self.word('daily_log',8),1)
        self.assertEqual(self.get(2),10);self.assertEqual(self.get(3),0)
        self.assertEqual(self.get(15),46);self.assertEqual(self.get(26),0)
        self.tick();self.tick();self.call('parallel_poll_once')
        self.assertEqual(self.get(3),0)
    def test_phase_debt_gets_complete_pulses_not_skipped_frames(self):
        self.running();self.setword('rtc_pace',2,10)
        for _ in range(56):self.tick()
        self.assertGreaterEqual(self.get(12),8)
        self.assertEqual(self.get(3),0)
    def test_catchup_preserves_six_tick_pulses_and_released_gap(self):
        self.running();self.setword('rtc_pace',2,10)
        active=False;start=None;end=None;widths=[]
        for _ in range(80):
            self.tick();now=bool(self.word('second_active'))
            if now and not active:
                if end is not None:self.assertGreaterEqual(self.get(4)-end,1)
                start=self.get(4)
            if active and not now:
                end=self.get(4);widths.append(end-start)
            active=now
        self.assertTrue(widths);self.assertTrue(all(w==6 for w in widths))
    def test_minute_waits_for_physical_12_then_moves_without_stopping_seconds(self):
        self.running();self.put(22,704)
        self.setword('seconds_log',248,880);self.setword('rtc_pace',2,55)
        for _ in range(16):self.tick()
        self.assertEqual(self.get(13),0) # RTC 23:45 but physical seconds near55.
        self.setword('seconds_log',248,959);self.setword('seconds_log',251,892)
        self.setword('seconds_log',252,1);self.setword('seconds_log',253,16)
        self.setword('seconds_log',254,960);self.setword('rtc_pace',2,60)
        self.put(5,0)
        for _ in range(self.minute_gate_ticks):self.tick()
        self.assertEqual(self.get(13),6);self.assertEqual(self.get(22),705)
        self.assertGreater(self.get(12),1);self.assertEqual(self.get(3),0)
    def test_missing_runtime_reference_stops_bounded(self):
        self.running();self.setword('seconds_log',248,1099);self.setword('rtc_pace',2,80)
        for _ in range(12):self.tick()
        self.assertEqual((self.get(2),self.get(3)),(6,5));self.released()
    def test_ram_headroom(self):self.assertLessEqual(self.ram_end,0x20000c00)
    def test_uart_irq_vector_and_buffer_during_main_loop_work(self):
        image=next(data for addr,data,_ in self.loads if addr==0x08000000)
        self.assertEqual(struct.unpack_from('<I',image,44*4)[0],self.symbols['UART2_Handler'])
        self.running();self.due();wire=b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n'
        for i,b in enumerate(wire):
            self.cpu.mem_write(0x40004408,struct.pack('<I',2))
            self.cpu.mem_write(0x40004404,struct.pack('<I',b))
            self.call('UART2_Handler')
            if i%8==7:self.call('parallel_poll_once')
        self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log'),3)
        self.assertEqual(self.word('uart_probe_overflow'),0)
    def test_uart_interrupt_can_preempt_motor_tick_with_stack_headroom(self):
        self.running();state={'stopped':False}
        def pause(uc,access,a,size,v,user):
            if a==0x48000410 and v==1 and not state['stopped']:
                state['stopped']=True;uc.emu_stop()
        handle=self.cpu.hook_add(UC_HOOK_MEM_WRITE,pause)
        self.call('SysTick_Handler');self.cpu.hook_del(handle)
        self.assertTrue(state['stopped'])
        context=self.cpu.context_save();stack=self.cpu.reg_read(UC_ARM_REG_SP)
        self.cpu.reg_write(UC_ARM_REG_SP,stack-32) # Cortex-M0 exception frame.
        low={'sp':stack-32}
        def monitor(uc,a,size,user):low['sp']=min(low['sp'],uc.reg_read(UC_ARM_REG_SP))
        handle=self.cpu.hook_add(UC_HOOK_CODE,monitor)
        self.cpu.mem_write(0x40004408,struct.pack('<I',2))
        self.cpu.mem_write(0x40004404,struct.pack('<I',ord('X')))
        self.call('UART2_Handler');self.cpu.hook_del(handle)
        self.assertGreaterEqual(low['sp'],self.ram_end)
        self.cpu.context_restore(context)
        self.cpu.emu_start(self.cpu.reg_read(UC_ARM_REG_PC)|1,0x08007000,count=2000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),0x20000ff8)
        self.assertEqual(self.get(3),0)
        self.call('uart_probe_poll_once');self.assertEqual(self.word('uart_probe_last_byte'),ord('X'))
    def test_ring_overflow_drops_damage_and_recovers_next_clean_time(self):
        self.running();self.due()
        for _ in range(40):
            self.cpu.mem_write(0x40004408,struct.pack('<I',2))
            self.cpu.mem_write(0x40004404,struct.pack('<I',ord('x')))
            self.call('UART2_Handler')
        self.call('parallel_poll_once');self.feed(b'\r\n')
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        self.assertEqual(self.word('daily_log'),3);self.assertGreater(self.word('uart_probe_overflow'),0)
    def test_time_survives_following_tick_record(self):
        self.running();self.due()
        # Capture without allowing the daily handler to finish until both lines arrived.
        for wire in (b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n',b'+TICK:23:45:24\r\n'):
            for b in wire:
                self.cpu.mem_write(0x40004408,struct.pack('<I',2))
                self.cpu.mem_write(0x40004404,struct.pack('<I',b))
                self.call('uart_probe_poll_once')
        self.call('parallel_poll_once');self.assertEqual(self.word('daily_log'),3)
    def test_correction_ages_time_across_year_rollover(self):
        self.running();self.due()
        self.feed(b'+TIME:Thu Dec 31 23:59:59 2026 +0000 09:00\r\n')
        for second in (24,25):
            self.rtc_time(23,45,second)
            self.tick();self.tick();self.call('parallel_poll_once')
        self.put(30,1);self.call('parallel_poll_once')
        self.assertEqual(self.bus.data[2:9],[1,0,0,1,5,1,0x27])
        self.assertEqual(self.word('daily_log'),3);self.assertEqual(self.get(3),0)
    def test_two_physical_revolutions_follow_jittered_rtc_edges(self):
        self.running();self.put(22,720-15)
        offset=getattr(self,'seconds_offset',68)
        # Start at 23:45:00 with seconds at home; retain the seeded date.
        self.rtc_time(23,45,0)
        self.cpu.mem_write(self.symbols['rtc_last'],struct.pack('<I',23*3600+45*60))
        self.cpu.mem_write(self.symbols['rtc_edge_tick'],struct.pack('<I',self.get(4)))
        self.put(5,0);self.setword('rtc_pace',2,0)
        self.setword('daily_log',3,self.word('daily_log',3)+86400)
        for elapsed in range(1,121):
            for _ in range((127,129,129,127)[(elapsed-1)%4]):
                p=self.word('seconds_log',248)+1
                self.tick(int(959-offset<=p<=974-offset))
                self.assertNotEqual(self.get(2),6,(elapsed,self.get(3),p))
            sod=23*3600+45*60+elapsed
            self.rtc_time(sod//3600,(sod//60)%60,sod%60)
            self.call('parallel_poll_once')
        for _ in range(self.minute_settle_ticks):self.tick()
        self.assertEqual(self.word('seconds_log',255),2)
        self.assertEqual(self.get(13),12);self.assertEqual(self.get(22),707)
        # Seconds continue during the configurable minute-burst settling
        # tail; its upper bound includes those extra observation ticks.
        self.assertGreaterEqual(self.get(12),1920)
        self.assertLessEqual(self.get(12),1920+self.minute_settle_ticks//7+1)
    def test_home_then_runtime_keeps_seconds_sensor_selected_after_catchup(self):
        self.put(1,1);self.tick()
        self.feed(b'+TIME:Thu Oct  8 12:00:23 2026 +0100 09:00\r\n')
        released=None
        for t in range(1,128*180):
            if self.get(2)==1:
                high=int(246<=self.word('seconds_log',5)+1<=262) if self.get(19)==1 else int(self.word('minute_log',5)+1>=13)
            else:
                p=self.word('seconds_log',248)+1;high=int(891<=p<=906)
            self.tick(high)
            if t%128==0:
                sod=12*3600+23+t//128;self.rtc_time(sod//3600,(sod//60)%60,sod%60)
                self.call('parallel_poll_once')
            self.assertNotEqual(self.get(2),6,(t,self.get(3)))
            if self.get(26) and released is None:released=t
            if released is not None and t-released>=128*121:
                self.assertEqual(self.get(2),7)
                self.assertTrue(self.output&(1<<13));self.assertFalse(self.output&(1<<15))
                self.assertGreaterEqual(self.word('seconds_log',255),2)
                break
        self.assertIsNotNone(released)
    def test_five_second_physical_lag_recovers_and_minutes_wait_for_12(self):
        self.running();self.put(5,55);self.put(22,705)
        self.rtc_time(23,45,55)
        self.cpu.mem_write(self.symbols['rtc_last'],struct.pack('<I',23*3600+45*60+55))
        self.cpu.mem_write(self.symbols['rtc_edge_tick'],struct.pack('<I',self.get(4)))
        self.setword('rtc_pace',2,55);self.setword('seconds_log',248,880)
        self.setword('daily_log',3,self.word('daily_log',3)+86400)
        for elapsed in range(1,71):
            for _ in range(128):
                slip=80 if self.word('seconds_log',255)==0 else 0
                physical=self.word('seconds_log',248)+1-slip
                self.tick(int(891<=physical<=906))
                self.assertEqual(self.get(3),0,(elapsed,physical))
                if self.get(13):self.assertGreaterEqual(self.word('seconds_log',255),1)
            sod=23*3600+45*60+55+elapsed
            self.rtc_time(sod//3600,(sod//60)%60,sod%60)
            self.call('parallel_poll_once')
        self.assertEqual(self.word('seconds_log',255),2)
        self.assertEqual(self.get(13),12);self.assertEqual(self.get(22),707)
        self.assertEqual(self.get(31),0) # Second revolution is back in phase.
        self.assertLess(abs(self.word('seconds_log',248)-5*16),18)

if __name__=='__main__':unittest.main()
