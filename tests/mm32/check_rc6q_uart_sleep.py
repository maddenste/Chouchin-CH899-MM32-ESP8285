"""Focused native ARM SLEEP protocol checks; no firmware flashing."""
import unittest
from pathlib import Path
from check_rc6p_all_pwm import Tests as Prior
from unicorn import UC_HOOK_MEM_WRITE

class Tests(Prior):
    artifact=Path(__file__).parent/'release_candidate_rc6q/build/MM32SPIN05PF_UART_SLEEP_RC6Q_20261022.axf'
    signature=0x4d50527a

    def wake_fixture(self):
        self.start_pwm(3)
        self.setword('minute_log',211,1)
        self.setword('minute_log',217,1)
        self.setword('minute_log',218,self.get(4)+100000)
        self.tx=[]
        self.cpu.hook_add(UC_HOOK_MEM_WRITE,
                         lambda cpu,access,address,size,value,user:self.tx.append(value),
                         begin=0x40004400,end=0x40004400)

    def test_sleep_parser_accepts_only_complete_uppercase_command(self):
        for data,valid in [(b'SLEEP\r\n',1),(b'SLEEP\n',1),
                           (b'SLEEP',0),(b'sleep\r\n',0),(b'SLEEPX\r\n',0),
                           (b' SLEEP\r\n',0),(b'SLEEP\r\nX',0)]:
            self.cpu.mem_write(0x20000e00,data)
            self.assertEqual(self.result('mm32_uart_parse_esp_line',0x20000e00,len(data),0x20000e80),valid)
            if valid:
                self.assertEqual(int.from_bytes(self.cpu.mem_read(0x20000e8c,4),'little'),5)

    def test_sleep_closes_lease_without_reply_or_motor_change(self):
        self.wake_fixture()
        before=(self.get(2),self.get(3),self.reg(0x2c),self.reg(0x38),self.reg(0x3c),self.counter)
        self.feed(b'SLEEP\r\n')
        self.assertEqual(self.word('minute_log',157),1)
        self.assertEqual(self.word('minute_log',211),1)
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',157),0)
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.word('minute_log',217),0)
        self.assertEqual(before,(self.get(2),self.get(3),self.reg(0x2c),self.reg(0x38),self.reg(0x3c),self.counter))
        self.assertEqual(self.raw(0x48000414),16)
        self.assertEqual(self.tx,[])
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',158),1)

    def test_complete_time_is_preserved_and_processed_before_poweroff(self):
        self.wake_fixture()
        self.setword('daily_log',0,2)
        self.setword('daily_log',5,self.word('uart_probe_good_time'))
        for b in b'+TIME:Thu Oct 22 09:35:30 2026 +0100 10:00 30\r\n':
            self.call('uart_probe_consume',b)
        time_address=self.symbols['uart_probe_time_event']
        snapshot=bytes(self.cpu.mem_read(time_address,20))
        for b in b'SLEEP\r\n':self.call('uart_probe_consume',b)
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',157),1)
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(bytes(self.cpu.mem_read(time_address,20)),snapshot)
        # Model acceptance of the already stored correction, not motor motion.
        self.setword('daily_log',0,7)
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.word('daily_log',0),7)
        self.assertEqual(bytes(self.cpu.mem_read(time_address,20)),snapshot)
        self.assertEqual(self.tx,[])

    def test_sleep_without_time_finishes_unsuccessful_daily_wake(self):
        self.wake_fixture()
        self.setword('daily_log',0,2)
        self.setword('daily_log',5,self.word('uart_probe_good_time'))
        self.feed(b'SLEEP\n');self.call('esp_sleep_poll')
        self.assertEqual(self.word('daily_log',0),5)
        self.assertEqual(self.word('minute_log',211),0)
        self.assertEqual(self.get(3),0)

    def test_clean_defers_sleep_and_new_wake_discards_old_request(self):
        self.wake_fixture()
        self.setword('minute_log',230,1)
        self.feed(b'SLEEP\r\n');self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',211),1)
        self.assertEqual(self.word('minute_log',157),1)
        self.setword('minute_log',230,0)
        self.call('esp_sleep_poll')
        self.assertEqual(self.word('minute_log',211),0)
        self.setword('minute_log',157,1)
        self.call('radio_on')
        self.assertEqual(self.word('minute_log',157),0)
        self.assertEqual(self.word('minute_log',211),1)

if __name__=='__main__':
    names=['test_sleep_parser_accepts_only_complete_uppercase_command',
           'test_sleep_closes_lease_without_reply_or_motor_change',
           'test_complete_time_is_preserved_and_processed_before_poweroff',
           'test_sleep_without_time_finishes_unsuccessful_daily_wake',
           'test_clean_defers_sleep_and_new_wake_discards_old_request',
           'test_all_modes_select_hardware_pwm',
           'test_normal_waveform_continues_across_three_hardware_wraps_without_cpu']
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Tests(n) for n in names))
    raise SystemExit(not r.wasSuccessful())
