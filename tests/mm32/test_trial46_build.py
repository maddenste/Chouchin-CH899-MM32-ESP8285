"""Production configured daily schedule; all 1440 HH:MM combinations."""
import unittest
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
import test_trial45_build as prior
import test_reference_scan_build as ref


class Tests(prior.Tests):
    artifact = ref.ROOT/'build/MM32SPIN05PF_DAILY_SCHEDULE_TRIAL46_20261009.axf'
    signature = 0x4d503436
    defines = prior.Tests.defines + ['-DCONFIGURED_DAILY_WAKE']
    test_daily_wake_cannot_repeat_today_after_backward_adjustment = None

    def due(self):
        # Force a due deadline for inherited protocol tests, not now+120.
        self.setword('daily_log', 3, 1)
        self.call('parallel_poll_once')

    def now_stamp(self):
        self.call('rtc_motion_stamp')
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def schedule(self, now):
        self.cpu.reg_write(UC_ARM_REG_R0, now)
        self.cpu.reg_write(UC_ARM_REG_R1, 1)  # Old accelerated request ignored.
        self.call('daily_schedule')
        return self.word('daily_log', 3)

    def test_all_1440_times_parse_and_schedule_without_rounding(self):
        self.running(); now = self.now_stamp(); today = now-now%86400
        for hour in range(24):
            for minute in range(60):
                wire = f'+TIME:Wed Oct  7 23:45:23 2026 +0100 {hour:02}:{minute:02}\r\n'.encode()
                self.cpu.mem_write(0x20000c00, wire)
                self.cpu.reg_write(UC_ARM_REG_R0, 0x20000c00)
                self.cpu.reg_write(UC_ARM_REG_R1, len(wire))
                self.cpu.reg_write(UC_ARM_REG_R2, 0x20000d00)
                self.call('mm32_uart_parse_esp_line')
                self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 1)
                self.assertEqual(bytes(self.cpu.mem_read(0x20000d09, 2)), bytes((hour,minute)))
                self.setword('daily_log', 10, hour); self.setword('daily_log', 11, minute)
                expected = today+hour*3600+minute*60
                if expected<=now: expected+=86400
                self.assertEqual(self.schedule(now), expected)

    def test_initial_deadline_uses_configured_time_not_two_minutes(self):
        self.running(); now = self.now_stamp()
        self.assertEqual(self.word('daily_log', 3), now-now%86400+86400+9*3600)
        self.assertEqual(self.word('daily_log', 1), 0)
        self.poll_at(self.get(4)+120*128)
        self.assertEqual(self.word('daily_log', 1), 0)
        self.assertFalse(self.output & 16)

    def test_scheduled_wake_at_non_hour_minute_and_success(self):
        self.running(); self.setword('daily_log', 10, 23); self.setword('daily_log', 11, 46)
        now = self.now_stamp(); self.schedule(now)
        # Model real RTC :59 -> :00; no artificial daily deadline manipulation.
        self.rtc_time(23,45,59); self.setword('rtc_last',0,23*3600+45*60+59)
        self.put(5,59); self.tick(); self.tick(); self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',1), 0)
        self.rtc_time(23,46,0); self.tick(); self.tick(); self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',1), 1)
        self.assertEqual(self.word('daily_log'), 2)
        self.assertTrue(self.output & 16); self.assertEqual(self.get(28),4)
        self.feed(b'+TIME:Wed Oct  7 23:46:00 2026 +0100 23:46\r\n')
        self.assertEqual((self.get(2),self.get(3)), (7,0))
        self.assertFalse(self.output & 16); self.assertEqual(self.get(28),2)
        self.assertEqual(self.word('daily_log'),3)
        self.assertEqual(self.word('daily_log',3), now-now%86400+86400+23*3600+46*60)
        for _ in range(5): self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',1),1)

    def test_midnight_and_exact_time_roll_forward(self):
        self.running(); now = self.now_stamp(); today = now-now%86400
        self.setword('daily_log',10,0); self.setword('daily_log',11,0)
        self.assertEqual(self.schedule(today+86399),today+86400)
        self.assertEqual(self.schedule(today),today+86400)
        self.setword('daily_log',10,23); self.setword('daily_log',11,59)
        self.assertEqual(self.schedule(today+86339),today+86340)
        self.assertEqual(self.schedule(today+86340),today+86400+86340)

    def test_second_and_third_days_are_not_skipped_before_due_hour(self):
        self.running(); now = self.now_stamp(); today = now-now%86400
        self.setword('daily_log',10,9); self.setword('daily_log',11,17)
        self.setword('daily_log',1,5)  # Attempt count must not force an extra day.
        self.setword('minute_log',209,today//86400-1)
        self.assertEqual(self.schedule(today+8*3600),today+9*3600+17*60)
        self.setword('minute_log',209,today//86400)
        self.assertEqual(self.schedule(today+8*3600),today+9*3600+17*60)

    def test_previous_automatic_attempt_does_not_block_future_time(self):
        # Replaces the old once-per-day restriction: a future configured time
        # on this date remains eligible regardless of previous attempt count.
        self.running(); self.setword('daily_log',1,7); self.due()
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 23:46\r\n')
        now = self.word('daily_log',7)
        self.assertEqual(self.word('daily_log',3),now-now%86400+23*3600+46*60)

    def test_another_configured_time_same_day_can_wake_again(self):
        self.running(); self.due()
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 23:46\r\n')
        self.assertEqual(self.word('daily_log',1),1)
        self.rtc_time(23,46,0); self.setword('rtc_last',0,23*3600+46*60)
        self.put(15,46); self.put(5,0)
        self.setword('rtc_edge_tick',0,self.get(4)); self.tick(); self.tick()
        self.call('parallel_poll_once')
        self.assertEqual(self.word('daily_log',1),2)
        self.assertEqual(self.word('daily_log'),2)
        self.feed(b'+TIME:Wed Oct  7 23:46:00 2026 +0100 23:47\r\n')
        now = self.word('daily_log',7)
        self.assertEqual(self.word('daily_log',3),now-now%86400+23*3600+47*60)
        self.assertEqual((self.get(2),self.get(3)),(7,0))

    def test_manual_request_updates_schedule_without_consuming_daily_wake(self):
        self.running(); self.hold(2)
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 23:59\r\n')
        now = self.now_stamp()
        self.assertEqual(self.word('daily_log',1),0)
        self.assertEqual(self.word('minute_log',209),0)
        self.assertEqual(self.word('daily_log',3),now-now%86400+23*3600+59*60)

    def test_later_time_in_open_webpage_session_updates_schedule_only(self):
        self.running(); self.hold(2)
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 09:00\r\n')
        state = (self.get(2),self.get(5),self.get(15),self.get(16),self.get(22))
        writes = len(self.bus.calendar_writes)
        self.feed(b'+TIME:Wed Oct  7 23:45:24 2026 +0100 23:57\r\n')
        now = self.now_stamp()
        self.assertEqual((self.word('daily_log',10),self.word('daily_log',11)),(23,57))
        self.assertEqual(self.word('daily_log',3),now-now%86400+23*3600+57*60)
        self.assertEqual((self.get(2),self.get(5),self.get(15),self.get(16),self.get(22)),state)
        self.assertEqual(len(self.bus.calendar_writes),writes)
        self.assertEqual(self.word('daily_log',1),0)
        self.assertTrue(self.output & 16); self.assertEqual(self.get(28),4)

    def test_invalid_schedule_records_cannot_replace_deadline(self):
        self.running(); self.hold(2)
        self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 23:57\r\n')
        before = self.word('daily_log',3)
        for value in (b'24:00',b'00:60',b'-1:00',b'09:99'):
            self.feed(b'+TIME:Wed Oct  7 23:45:23 2026 +0100 '+value+b'\r\n')
            self.assertEqual(self.word('daily_log',3),before)


if __name__ == '__main__': unittest.main()
