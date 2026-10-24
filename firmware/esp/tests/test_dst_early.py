"""Focused actual calendar/ESP R12 producer -> RC6AY queue/application tests."""
from pathlib import Path
import datetime as dt
import sys
p=Path(__file__).with_name('test_backend.py')
g={'__file__':str(p)}
exec(compile(p.read_text().split('cpu,symbols,call=machine(axf);cases=0')[0],str(p),'exec'),g)
cpu,sy,call=g['machine'](g['axf'])
transport,tsy,tx=g['machine'](p.with_name('transport_fixture.axf'))
sys.path.insert(0,str(g['WORKSPACE']/'tests/mm32'))
from check_rc6bc_deadline_guard import baseline
MM32=baseline.Tests
MM32.setUpClass()
def utc(s):return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())
vectors=[
 ('GMT0BST,M3.5.0/1,M10.5.0/2','2027-03-28T00:59:05',0,60),
 ('GMT0BST,M3.5.0/1,M10.5.0/2','2026-10-25T00:59:05',60,0),
 ('TST-1TDT-2,M10.4.5/13,M10.4.6/13','2026-10-23T11:59:05',60,120),
 ('TST-10TDT-10:30,M10.1.0/2,M4.1.0/2','2026-10-03T15:59:05',600,630),
 ('TST5TDT4,M3.2.0/2,M11.1.0/2','2026-03-08T06:59:05',-300,-240),
 ('TST0TDT-1,M10.4.5/0,M10.4.6/0','2026-10-22T23:59:05',0,60),
 ('TST-1TDT-2,M10.4.5/13:00:30,M10.4.6/13','2026-10-23T12:00:05',60,120),
]
cases=0
for rule,text,before,after in vectors:
 now=utc(text);cpu.mem_write(sy['zone'],rule.encode()+b'\0')
 # Preview window is exactly the old-clock minute before rounded boundary.
 assert call('upcomingCase',now)==1,(rule,text)
 result=bytes(cpu.mem_read(sy['upcoming'],48)).split(b'\0')[0]
 expected=dt.datetime.fromtimestamp(now+after*60,dt.timezone.utc)
 assert expected.strftime('%H:%M:%S %Y').encode() in result,(result,expected)
 suffix=f'{"-" if after<0 else "+"}{abs(after)//60:02}{abs(after)%60:02}'.encode()
 assert result.endswith(suffix),result
 assert call('upcomingCase',now-65)==0
 assert call('upcomingCase',now+60)==0
 assert call('wakeCase',now-120,23,30)==1
 old=dt.datetime.fromtimestamp(now+before*60,dt.timezone.utc)
 early=old.replace(second=0)
 assert list(cpu.mem_read(sy['wake'],2))==[early.hour,early.minute]
 cases+=5
 # Actual normal local conversion stays on the OLD offset before transition.
 assert call('localCase',now)==1
 assert bytes(cpu.mem_read(sy['civil']+5,3))==bytes((old.hour,old.minute,old.second))
 cases+=1
 # Produce a real TIME through the current ESP function, then actual MM32.
 transport.mem_write(tsy['dstZone'],rule.encode()+b'\0')
 address=tx('dstSaveBegin',now)
 wire=bytes(transport.mem_read(address,64)).split(b'\0')[0]
 assert result in wire,wire
 assert wire.endswith(b' DST\r\n'),wire
 # Outside the pre-transition minute the actual producer emits no flag.
 address=tx('dstTransmit',now-120,3,0)
 ordinary=bytes(transport.mem_read(address,64)).split(b'\0')[0]
 assert ordinary.endswith(b'30\r\n') and b' DST' not in ordinary,ordinary
 address=tx('dstTransmit',now+60,3,0)
 after_wire=bytes(transport.mem_read(address,64)).split(b'\0')[0]
 assert after_wire.endswith(b'30\r\n') and b' DST' not in after_wire,after_wire
 # Arm the real confirmation/SLEEP fixture with the flagged record again.
 address=tx('dstSaveBegin',now)
 cases+=3
 c=MM32();c.setUp();c.held_fixture(3);c.put(2,7)
 c.put(16,old.hour);c.put(15,old.minute);c.put(5,old.second)
 c.put(22,(old.hour*60+old.minute)%720)
 bcd=lambda n:n//10*16+n%10
 c.bus.data[5:9]=[bcd(old.day),(old.weekday()+1)%7,bcd(old.month),bcd(old.year-2000)]
 c.rtc_time(old.hour,old.minute,old.second)
 c.setword('minute_log',211,1)
 c.consume(wire)
 assert bytes(c.cpu.mem_read(c.symbols['uart_probe_time_event']+19,1))==b'\x01'
 c.sent=[];c.consume(wire)
 assert bytes(c.sent)==b'\n'+wire,(bytes(c.sent),wire)
 transport.mem_write(0x2000e000,bytes(c.sent)[1:-2]+b'\0')
 assert tx('bridgeEcho',0x2000e000)==1
 cases+=3
 source=now+before*60-946684800;due=source+60-source%60
 c.setword('seconds_log',227,source)
 c.setword('daily_log',0,2);c.setword('daily_log',12,1)
 c.setword('daily_log',5,c.word('uart_probe_good_time')-1)
 c.call('daily_poll');assert c.word('minute_log',150)==due
 writes=list(c.bus.calendar_writes)
 received_tick=c.get(4)
 c.put(4,(received_tick+(due-1-source)*128)&0xffffffff)
 c.setword('seconds_log',227,due-1);c.call('daily_poll')
 assert c.bus.calendar_writes==writes
 c.put(4,(received_tick+(due-source)*128)&0xffffffff)
 c.setword('seconds_log',227,due);c.call('daily_poll')
 assert c.result('rtc_motion_stamp')==due+(after-before)*60
 assert c.get(3)==0
 cases+=4
for rule in ('GMT0','IST-5:30'):
 cpu.mem_write(sy['zone'],rule.encode()+b'\0')
 assert call('upcomingCase',utc('2026-10-23T11:59:05'))==0
 assert call('wakeCase',utc('2026-10-23T11:59:05'),10,20)==0
 cases+=2
print(f'PASS {cases} focused early-DST checks, including 7 actual ESP R12 TIME -> RC6AY old-boundary application cases')
