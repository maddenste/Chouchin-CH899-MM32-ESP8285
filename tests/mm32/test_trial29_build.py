"""RTC-paced compiled movement regression and clock discipline tests."""
import struct
import unittest
import test_trial22_build as old
import test_reference_scan_build as ref
from test_trial28_build import RTC
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
class Tests(unittest.TestCase):
    setUpClass=classmethod(old.ParallelTests.setUpClass.__func__)
    get=old.ParallelTests.get
    put=old.ParallelTests.put
    tick=old.ParallelTests.tick
    word=old.ParallelTests.word
    released=old.ParallelTests.released
    artifact=ref.ROOT/'build/MM32SPIN05PF_RTC_PACED_HANDS_TRIAL29B_20261008.axf'
    signature=0x4d503239
    defines=['-DWIFI_SET_TIME','-DWIFI_EARLY_SECONDS','-DWIFI_HOME_LEDS','-DRTC_PACED','-DRTC_MOTION']
    extra_sources=['parallel_leds.c','wifi_rtc_set_trial28.c']
    # Legacy software-time tests do not apply to the RTC build.
    test_home_and_three_continuous_minutes=None
    def setUp(self):
        old.ParallelTests.setUp(self); self.bus=RTC()
        self.a_output=0
        def write(uc,access,a,size,v,user):
            self.bus.write(a,v)
            if a==0x48000010: self.a_output=(self.a_output|(v&65535))&~(v>>16)
        def read(uc,access,a,size,v,user):
            if a==0x48000408:
                scl,sda=self.bus.levels()
                high=struct.unpack('<I',uc.mem_read(a,4))[0]&0x4000
                uc.mem_write(a,struct.pack('<I',high|(scl<<8)|(sda<<9)))
            elif a==0x48000404: uc.mem_write(a,struct.pack('<I',self.bus.crh))
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,write); self.cpu.hook_add(UC_HOOK_MEM_READ,read)
        self.cpu.mem_write(0x48000404,struct.pack('<I',self.bus.crh))
        self.cpu.ctl_remove_cache(0x08000000,0x08008000)
    def call(self,name):
        sentinel=getattr(self,'return_sentinel',0x08007000)
        self.cpu.reg_write(ref.UC_ARM_REG_LR,sentinel|1)
        self.cpu.emu_start(self.symbols[name],sentinel,count=2000000)
    def pace_put(self,i,v): self.cpu.mem_write(self.symbols['rtc_pace']+4*i,struct.pack('<I',v))
    def rtc_time(self,h,m,s):
        b=lambda x:(x//10)*16+x%10
        self.bus.data[2:5]=[b(s),b(m),b(h)]
    def seed(self,seconds=23):
        old.ParallelTests.seed(self,seconds); self.cpu.mem_write(0x40004408,struct.pack('<I',0))
        self.call('parallel_poll_once')
    def test_wifi_sets_rtc_motor_selector_bits_preserved(self):
        self.put(1,1); self.tick(); self.seed()
        self.assertEqual(self.bus.data[2:5],[0x23,0x45,0x23])
        self.assertEqual(self.get(6),1)
        self.assertEqual(self.bus.crh&0xff,0x44)
        self.assertEqual(self.word('wifi_rtc',2),2)
    def test_clock_only_changes_from_rtc(self):
        self.put(1,1); self.tick(); self.seed()
        for _ in range(130): self.tick()
        self.assertEqual(self.get(5),23)
        self.rtc_time(23,45,24); self.call('parallel_poll_once'); self.tick()
        self.assertEqual(self.get(5),24)
    def test_rtc_loss_stops_motors(self):
        self.put(1,1); self.tick(); self.seed(); self.tick(); self.tick()
        self.bus.ack=False; self.call('parallel_poll_once')
        self.assertEqual((self.get(2),self.get(3)),(6,8)); self.released()
    def test_stalled_rtc_stops_motors(self):
        self.put(1,1); self.tick(); self.seed()
        for _ in range(386): self.tick()
        self.assertEqual((self.get(2),self.get(3)),(6,8)); self.released()
    def test_jump_rejected(self):
        self.put(1,1); self.tick(); self.seed(); self.tick(); self.tick()
        self.rtc_time(23,45,30); self.call('parallel_poll_once')
        self.assertEqual((self.get(2),self.get(3)),(6,9)); self.released()
        self.assertEqual(self.word('rtc_pace',10),2)
        self.assertEqual(self.word('rtc_pace',14),1)
    def test_runtime_uses_nxp_seven_calendar_bytes_and_final_nack(self):
        self.put(1,1); self.tick(); self.seed(); self.tick(); self.tick()
        self.bus.received=[]; self.bus.master_acks=[]
        self.call('parallel_poll_once')
        self.assertEqual(self.bus.received,[0xa2,0,0xa3,0xa2,2,0xa3])
        self.assertEqual(self.bus.master_acks,[True,False]+[True]*6+[False])
    def test_capture_rollover_bad_snapshot_is_discarded_and_recovered(self):
        self.put(1,1); self.tick(); self.seed(); self.tick(); self.tick()
        self.cpu.mem_write(self.symbols['rtc_last'],struct.pack('<I',2579))
        self.rtc_time(0,43,0)
        self.bus.calendar_snapshots=[{2:0x59,3:0x43},{}]
        self.call('parallel_poll_once'); self.tick()
        self.assertEqual((self.get(16),self.get(15),self.get(5)),(0,43,0))
        self.assertEqual(self.get(3),0)
        self.assertEqual([self.word('rtc_pace',i) for i in [9,10,11,12,13]],[1,1,1,2639,2579])
    def test_two_suspect_snapshots_get_only_two_confirmation_reads(self):
        self.put(1,1); self.tick(); self.seed(); self.tick(); self.tick()
        self.rtc_time(23,45,24)
        self.bus.calendar_snapshots=[{2:0x30},{2:0x31},{}]
        self.call('parallel_poll_once'); self.tick()
        self.assertEqual(self.get(5),24); self.assertEqual(self.get(3),0)
        self.assertEqual(self.word('rtc_pace',10),2); self.assertEqual(self.word('rtc_pace',11),1)
    def test_bad_read_followed_by_unchanged_time_does_not_publish_false_edge(self):
        self.put(1,1); self.tick(); self.seed(); self.tick(); self.tick()
        self.bus.calendar_snapshots=[{2:0x30},{}]
        edges=self.word('rtc_pace',2); self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',2),edges)
        self.assertEqual(self.get(5),23); self.assertEqual(self.get(3),0)
    def test_vl_or_stopped_rtc_is_not_used_for_pacing(self):
        for r,v in [(2,0x80),(0,0x28)]:
            self.setUp(); self.put(1,1); self.tick(); self.seed(); self.tick(); self.tick()
            self.bus.data[r]=v; self.call('parallel_poll_once')
            self.assertEqual((self.get(2),self.get(3)),(6,8)); self.released()
    def test_midnight_is_a_single_rtc_edge(self):
        self.put(1,1); self.tick(); self.seed()
        self.cpu.mem_write(self.symbols['rtc_last'],struct.pack('<I',86399))
        self.rtc_time(0,0,0); self.tick(); self.tick(); self.call('parallel_poll_once'); self.tick()
        self.assertEqual((self.get(16),self.get(15),self.get(5)),(0,0,0))
        self.assertEqual(self.word('rtc_pace',2),1); self.assertEqual(self.get(3),0)
    def test_reload_calibrates_fast_hclk_against_eight_rtc_seconds(self):
        self.put(1,1); self.tick(); self.seed()
        for edge in range(1,10):
            for _ in range(130): self.tick()
            self.rtc_time(23,45,23+edge); self.call('parallel_poll_once')
        self.assertEqual(self.word('rtc_pace',4),1)
        self.assertEqual(self.word('rtc_pace',1),63475)
    def test_run_budget_cannot_get_ahead_of_rtc_and_minutes_do_not_pause_seconds(self):
        self.put(1,1); self.tick(); self.seed()
        self.put(2,7); self.put(7,1); self.put(8,1); self.put(26,1)
        self.put(18,self.get(4)); self.put(12,954)
        self.pace_put(2,59)
        for _ in range(300):
            self.tick()
            if self.get(2)==6: break
        self.assertLessEqual(self.get(12),960)
        self.assertEqual(self.get(13),6)
        self.assertEqual(self.get(3),0)
    def test_full_homing_release_and_two_minutes_rtc_paced(self):
        self.put(1,1); self.tick()
        for b in b'+TIME:Thu Oct  8 12:00:23 2026 +0100 09:00\r\n':
            self.cpu.mem_write(0x40004408,struct.pack('<I',2))
            self.cpu.mem_write(0x40004404,struct.pack('<I',b)); self.call('parallel_poll_once')
        self.cpu.mem_write(0x40004408,struct.pack('<I',0)); self.call('parallel_poll_once')
        release=None; overlap=False
        for t in range(1,128*180+1):
            high=0
            if self.get(19)==1: high=int(246<=self.word('seconds_log',5)+1<=262)
            elif self.get(19)==2: high=int(self.word('minute_log',5)+1>=13)
            self.tick(high)
            overlap |= bool(self.output&6 and (self.output&1 or self.a_output&128))
            if t%128==0:
                now=12*3600+23+t//128
                self.rtc_time(now//3600,(now//60)%60,now%60); self.call('parallel_poll_once')
            self.assertNotEqual(self.get(2),6,(t,self.get(3)))
            if self.get(26) and release is None:
                release=t; self.assertEqual(self.get(5),0)
                self.assertEqual((self.get(7),self.get(8)),(1,1))
            if release is not None and t-release==128*120:
                self.assertEqual(self.get(2),7)
                self.assertEqual(self.get(12),1920)
                self.assertEqual(self.get(13),12)
                break
        self.assertIsNotNone(release); self.assertTrue(overlap)

if __name__=='__main__': unittest.main()
