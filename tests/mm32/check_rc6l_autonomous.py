"""Native RC6L plus documented timer/AF/gate model. No physical motor model."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.analysis_deps'))
from check_rc6k_quartz import Tests as Prior
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6l/build/MM32SPIN05PF_AUTONOMOUS_PWM_RC6L_20261022.axf'
    signature=0x4d505275

    def setUp(self):
        super().setUp()
        self.cpu.mem_map(0x40012000,0x1000)
        self.cpu.mem_map(0x40014000,0x1000)
        self.down=False;self.mt_count=0;self.mt_sr=0;self.bt_count=0
        self.pad=[False,False];self.pad_edges=[];self.overlaps=[]
        def writes(cpu,access,address,size,value,user):
            if address==0x40000424:self.counter=value&65535
            if address==0x40000400 and not value&0x60:self.down=bool(value&16)
            if address==0x40000414 and value&1:self.down=False
            if address==0x40012c24:self.bt_count=value&65535
            if address==0x40012c14 and value&1:self.bt_count=0
            if address==0x40014024:self.mt_count=value&65535
            if address==0x40014014 and value&1:self.mt_count=0;self.mt_sr=1
            if address==0x40014010:self.mt_sr&=value
            self.refresh()
        def reads(cpu,access,address,size,value,user):
            if address==0x40000400:
                old=self.raw(address)
                self.store(address,(old&~16)|(16 if self.down else 0))
            elif address==0x40012c24:self.store(address,self.bt_count)
            elif address==0x40014024:self.store(address,self.mt_count)
            elif address==0x40014010:self.store(address,self.mt_sr)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,writes)
        self.cpu.hook_add(UC_HOOK_MEM_READ,reads)

    def raw(self,address):return int.from_bytes(self.cpu.mem_read(address,4),'little')
    def store(self,address,value):self.cpu.mem_write(address,(value&0xffffffff).to_bytes(4,'little'))
    def gate(self):
        return (self.raw(0x40012c04)&0x70)==0x40 and self.bt_count<self.raw(0x40012c34)
    def refresh(self):
        if not hasattr(self,'pad'):return
        for pin,port,bit,ch in ((0,0x48000000,128,2),(1,0x48000400,1,3)):
            shift=28 if pin==0 else 0
            mode=(self.raw(port)>>shift)&15
            af=(self.raw(port+0x20)>>shift)&15
            if mode in (9,10,11) and af==1:
                enabled=bool(self.raw(0x40000420)&(1<<(4*(ch-1))))
                cm=self.raw(0x40000418 if ch==2 else 0x4000041c)
                oc=(cm>>(12 if ch==2 else 4))&7
                compare=self.raw(0x40000438 if ch==2 else 0x4000043c)
                pwm1=self.counter<=compare if self.down else self.counter<compare
                level=enabled and (oc==5 or oc==6 and pwm1 or oc==7 and not pwm1)
            else:
                level=bool((self.a_output if pin==0 else self.output)&bit)
            if level!=self.pad[pin]:
                self.pad[pin]=level
                self.pad_edges.append((self.timer_time,pin,bool(level)))
        if all(self.pad):self.overlaps.append(self.timer_time)

    def next_gap(self):
        middle=self.reg(0x34);top=self.reg(0x2c);c=self.counter
        return (c-middle if c>middle else c+middle) if self.down else (middle-c if c<middle else 2*top-c-middle)

    def advance_timer(self,counts,dispatch=True):
        if not hasattr(self,'bt_count') or not self.word('seconds_log',218):
            return super().advance_timer(counts)
        while counts:
            active=bool(self.reg(0)&1) and self.gate()
            nexts=[]
            if active:
                top=self.reg(0x2c)
                nexts.append((self.counter if self.down else top-self.counter,'bound'))
                for channel in range(4):
                    ccr=self.reg(0x34+4*channel)
                    delta=self.counter-ccr if self.down else ccr-self.counter
                    if delta>0 and ccr<=top:nexts.append((delta,channel))
            if self.raw(0x40014000)&1:
                nexts.append((((self.raw(0x40014034)-self.mt_count)&65535) or 65536,'minute'))
            step=min([counts]+[d for d,k in nexts if d>0])
            events=[k for d,k in nexts if d==step]
            if active:self.counter+=-step if self.down else step
            if self.raw(0x40014000)&1:self.mt_count=(self.mt_count+step)&65535
            self.timer_time+=step;counts-=step
            if active:
                if 'bound' in events:self.down=not self.down;self.sr|=1
                for channel in range(4):
                    if channel in events:
                        self.sr|=2<<channel
                        if channel==0 and (self.reg(4)&0x70)==0x30:
                            # MMS3 emits a pulse even if CC1IF is already set.
                            if self.raw(0x40012c00)&1 and self.raw(0x40012c08)&0x77==0x27:
                                self.bt_count=(self.bt_count+1)&65535
            if 'minute' in events:self.mt_sr|=2
            self.refresh()
            if dispatch:
                if self.sr&self.reg(0x0c)&2:self.call('TIM3_Handler')
                if self.mt_sr&self.raw(0x4001400c)&2:self.call('TIM14_Handler')

    def tick(self,high=0):
        if not hasattr(self,'bt_count') or not self.word('seconds_log',218):
            return super().tick(high)
        self.seconds_input=high
        self.store(0x48000408,high<<14)
        cycles=self.word('rtc_pace',1)+1-self.borrowed_cycles
        self.borrowed_cycles=0
        self.remainder+=max(cycles,0)
        counts,self.remainder=divmod(self.remainder,16)
        self.advance_timer(counts)
        self.call('SysTick_Handler')
        for _ in range(8):
            if not self.word('seconds_log',214):return
            candidates=[]
            if self.gate():candidates.append(self.next_gap())
            if self.raw(0x4001400c)&2:
                candidates.append(((self.raw(0x40014034)-self.mt_count)&65535) or 65536)
            self.assertTrue(candidates)
            step=min(candidates);self.borrowed_cycles+=step*16
            self.advance_timer(step)
        self.fail('deferred clock tick stuck')

    def start_pwm(self,mode=3):
        self.mode_run(mode)
        self.assertEqual(self.word('seconds_log',218),1)
        self.assertEqual(self.get(3),0)
        self.pad_edges=[];self.overlaps=[]

    def test_hardware_generates_and_stops_960_without_any_interrupt(self):
        self.start_pwm()
        p=self.word('minute_log',181);width=self.word('minute_log',182)
        self.assertEqual((self.reg(0x28),self.reg(4),self.reg(8)),(15,0x30,5))
        self.assertEqual(self.raw(0x40012c08),0x27)
        self.assertEqual(self.raw(0x40012c04),0x40)
        self.advance_timer(p*970,dispatch=False)
        rises=[e for e in self.pad_edges if e[2]];falls=[e for e in self.pad_edges if not e[2]]
        self.assertEqual((len(rises),len(falls),self.bt_count),(960,960,960))
        self.assertEqual({b[0]-a[0] for a,b in zip(rises,rises[1:])},{p})
        self.assertEqual({b[0]-a[0] for a,b in zip(rises,falls)},{width})
        self.assertTrue(all(a[1]!=b[1] for a,b in zip(rises,rises[1:])))
        self.assertEqual(self.pad,[False,False]);self.assertFalse(self.overlaps)
        last=len(self.pad_edges);self.advance_timer(p*20,dispatch=False)
        self.assertEqual(len(self.pad_edges),last)
        self.assertEqual(self.get(12),0) # CPU bookkeeping did not generate them.

    def complete_lap(self):
        for pulse in range(1,961):
            self.setword('second_highs',0,6 if 889<=pulse<=900 else 0)
            self.advance_timer(self.next_gap())
            self.assertEqual(self.get(3),0,(pulse,self.get(3)))
        self.assertEqual(self.get(30),1)
        self.assertEqual(self.word('seconds_log',248),960)

    def test_full_lap_reference_hold_and_restart_preserves_polarity(self):
        self.start_pwm();polarity=self.word('second_polarity')
        self.complete_lap()
        self.assertEqual(self.word('second_polarity'),polarity)
        last=len(self.pad_edges);self.advance_timer(50000)
        self.assertEqual(len(self.pad_edges),last)
        self.put(5,0);self.setword('rtc_boundary',0,1);self.tick()
        self.assertEqual(self.get(3),0)
        self.assertTrue(self.gate())
        self.advance_timer(self.next_gap())
        self.assertEqual(self.bt_count,1)

    def test_minutes_continue_while_seconds_parked(self):
        self.start_pwm();self.call('pwm_drain');self.advance_timer(self.next_gap())
        self.put(30,1)
        before=len(self.pad_edges)
        self.setword('request_pulses',0,6);self.call('pwm_minutes_queue')
        self.advance_timer(self.word('minute_log',184)*7)
        self.assertEqual(self.get(13),6)
        self.assertEqual(self.word('minute_log',191),0)
        self.assertEqual(len(self.pad_edges),before)
        self.assertEqual(self.get(3),0)

    def test_rec_drain_and_stop_return_gpio_ownership(self):
        self.start_pwm();self.advance_timer(10000)
        self.call('pwm_drain')
        self.advance_timer(self.next_gap())
        self.assertFalse(self.gate());self.assertEqual(self.get(3),0)
        self.call('fine_stop')
        self.assertEqual((self.raw(0x48000000)>>28)&15,1)
        self.assertEqual(self.raw(0x48000400)&15,1)
        self.assertEqual(self.pad,[False,False])
        self.assertEqual(self.reg(0x20),0)

    def test_delayed_bookkeeping_does_not_move_pwm_edges_and_faults_safely(self):
        self.start_pwm();p=self.word('minute_log',181)
        self.advance_timer(p*4,dispatch=False)
        rises=[e[0] for e in self.pad_edges if e[2]]
        self.assertEqual({b-a for a,b in zip(rises,rises[1:])},{p})
        self.call('TIM3_Handler')
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.pad,[False,False])

    def test_normal_modes_remain_same_waveforms(self):
        Prior.setUpClass()
        for mode in (0,1):
            old=Prior();old.setUp();self.setUp()
            for t in (old,self):
                t.mode_run(mode);t.setword('request_pulses',0,6)
                t.edges=[];t.advance_timer(t.word('minute_log',181)*20)
                self.assertEqual(t.get(3),0)
            self.assertEqual(self.edges,old.edges)

    def test_catchup_and_runtime_handover_preserve_seconds_af(self):
        self.start_pwm();self.advance_timer(10000)
        self.assertTrue(any(self.pad))
        before=list(self.pad)
        self.call('catchup_begin',self.get(4))
        self.assertEqual(self.pad,before)
        self.assertEqual((self.raw(0x48000000)>>28)&15,9)
        self.assertEqual(self.raw(0x48000400)&15,9)
        self.put(2,11);self.put(22,(self.get(16)%12)*60+self.get(15))
        self.setword('minute_active',0,0);self.setword('catchup_pulses',0,0)
        self.tick()
        self.assertEqual(self.get(2),7)
        self.assertEqual(self.get(3),0)
        self.assertEqual((self.raw(0x48000000)>>28)&15,9)
        self.assertEqual(self.raw(0x48000400)&15,9)

    def test_timer_stall_watchdog_releases_coils(self):
        self.start_pwm();self.advance_timer(10000)
        self.assertTrue(any(self.pad))
        # Simulate a stopped timer domain while SysTick still executes.
        for _ in range(20):
            self.call('SysTick_Handler')
            if self.get(3):break
        self.assertEqual(self.get(3),10)
        self.assertEqual(self.pad,[False,False])

    def test_native_rec_drain_enters_homing(self):
        self.start_pwm();self.advance_timer(10000)
        self.setword('minute_log',227,2) # Qualified REC park request.
        self.setword('minute_log',229,1) # Permanent REC lockout.
        for _ in range(32):
            self.tick()
            if self.get(2)==1:break
        self.assertEqual(self.get(2),1)
        self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('seconds_log',218),0)
        self.assertEqual((self.raw(0x48000000)>>28)&15,1)
        self.assertEqual(self.raw(0x48000400)&15,1)

    def test_boundary_mode_switches_enter_and_leave_pwm(self):
        self.mode_run(0)
        self.advance_timer((self.reg(0x38)-self.counter)&65535)
        self.call('fine_stop');self.put(30,1)
        self.setword('minute_log',188,3);self.setword('rtc_boundary',0,1)
        self.put(5,0);self.tick()
        self.assertEqual(self.word('minute_log',189),3)
        self.assertEqual(self.word('seconds_log',218),1)
        self.complete_lap()
        self.setword('minute_log',188,0);self.setword('rtc_boundary',0,1)
        self.put(5,0);self.tick()
        self.assertEqual(self.word('minute_log',189),0)
        self.assertEqual(self.word('seconds_log',218),0)
        self.assertEqual(self.reg(0x28),31)
        self.assertEqual(self.get(3),0)

    def test_safe_fault_drains_before_gpio_parking(self):
        self.start_pwm();self.advance_timer(10000)
        self.call('fail',8)
        self.assertEqual(self.get(2),14)
        for _ in range(32):
            self.tick()
            if not self.word('seconds_log',218):break
        self.assertEqual(self.get(2),14)
        self.assertEqual(self.get(3),8)
        self.assertEqual(self.word('seconds_log',218),0)
        self.assertEqual(self.reg(0x20),0)

    def test_quartz_and_calendar_coexist_in_size_optimised_build(self):
        state,updates,resets,cycles=Prior.calendar_and_counter(self)
        self.assertEqual(state,1)
        self.assertGreaterEqual(updates,2)
        self.assertEqual(self.get(3),0)

    def test_parked_audit_can_probe_and_restores_seconds(self):
        self.start_pwm();self.call('pwm_drain');self.advance_timer(self.next_gap())
        self.put(30,1);self.put(16,23);self.put(15,45);self.put(4,1000)
        self.call('audit_tick',1000,7)
        self.assertEqual(self.word('minute_log',176),2)
        self.put(4,1001);self.call('audit_tick',1001,7)
        self.assertEqual(self.word('minute_log',176),1)

    def test_full_hardware_budget_across_rates_and_start_polarities(self):
        for rate in (50000,75000):
            for polarity in (0,1):
                self.setUp()
                self.setword('rtc_pace',1,rate-1)
                self.setword('second_polarity',0,polarity)
                self.start_pwm(2)
                next_polarity=self.word('second_polarity')
                p=self.word('minute_log',181)
                self.advance_timer(p*962,dispatch=False)
                rises=[e for e in self.pad_edges if e[2]]
                self.assertEqual(len(rises),960)
                self.assertEqual(rises[0][1],0 if next_polarity else 1)
                self.assertEqual(self.bt_count,960)
                self.assertFalse(self.overlaps)
                self.assertEqual(self.pad,[False,False])

if __name__=='__main__':
    names=['test_hardware_generates_and_stops_960_without_any_interrupt',
           'test_full_lap_reference_hold_and_restart_preserves_polarity',
           'test_minutes_continue_while_seconds_parked',
           'test_rec_drain_and_stop_return_gpio_ownership',
           'test_delayed_bookkeeping_does_not_move_pwm_edges_and_faults_safely',
           'test_normal_modes_remain_same_waveforms',
           'test_catchup_and_runtime_handover_preserve_seconds_af',
           'test_timer_stall_watchdog_releases_coils',
           'test_native_rec_drain_enters_homing',
           'test_boundary_mode_switches_enter_and_leave_pwm',
           'test_safe_fault_drains_before_gpio_parking',
           'test_quartz_and_calendar_coexist_in_size_optimised_build',
           'test_parked_audit_can_probe_and_restores_seconds',
           'test_full_hardware_budget_across_rates_and_start_polarities']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
