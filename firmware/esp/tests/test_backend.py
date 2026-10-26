"""Execute actual settings/HTTP/formatter/calendar code with Arduino stubs.
Not an Xtensa, radio, physical-flash or full-MM32 hardware simulation."""
import sys, re, ast, datetime as dt, struct, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=Path(os.environ.get('MM32_TEST_WORKSPACE',str(ROOT.parents[1])))
sys.path.insert(0,str(WORKSPACE/'.analysis_deps'))
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR
from zoneinfo import ZoneInfo
axf=ROOT/'tests/backend_fixture.axf'
def machine(elf_path):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);cpu.mem_map(0x08000000,0x100000);cpu.mem_map(0x20000000,0x10000)
    with elf_path.open('rb') as handle:
        elf=ELFFile(handle);symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        for segment in elf.iter_segments():
            if segment['p_type']=='PT_LOAD':cpu.mem_write(segment['p_vaddr'],segment.data())
    def call(name,*args):
        cpu.reg_write(UC_ARM_REG_SP,0x2000ff00);cpu.reg_write(UC_ARM_REG_LR,0x080ff001)
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):cpu.reg_write(reg,value)
        cpu.emu_start(symbols[name]|1,0x080ff000,count=2000000)
        return cpu.reg_read(UC_ARM_REG_R0)
    return cpu,symbols,call
cpu,symbols,call=machine(axf);cases=0
for scenario in (0,1):
    assert call('expandedInputCase',scenario)==0,('R13 expanded inputs',scenario)
print('PASS R13 trailing-dot NTP, 64-character credential, long POSIX persistence and over-limit rejection')
for hour in range(24):
    for minute in range(60):
        assert call('minuteHttpCase',hour,minute)==0,(hour,minute)
        cases+=1
for mode in range(4):
    for park in range(3):
        for hour,minute in ((0,0),(10,17),(23,59)):
            assert call('storageCase',mode,park,hour,minute)==0,(mode,park,hour,minute);cases+=1
        assert call('httpCase',mode,park,0)==0;cases+=1
for version in (0,1):assert call('legacyCase',version)==0;cases+=1
for variant in range(1,10):assert call('httpCase',0,1,variant)==0,variant;cases+=1
for mode in range(4):
    for park in range(3):
        assert call('extendedLegacyCase',mode,park)==0,(mode,park)
        cases+=1
parser_axf=WORKSPACE/'firmware/mm32/build/MM32SPIN05PF_SESSION_SLEEP_RC6BE_20261026.axf'
parser,_,parse=machine(parser_axf)
for mode in range(4):
    for park in range(3):
        for hour in range(24):
            for minute in range(60):
                length=call('formatCase',mode,park,hour,minute)
                wire=bytes(cpu.mem_read(symbols['wire'],length));parser.mem_write(0x20001000,wire)
                assert parse('mm32_uart_parse_esp_line',0x20001000,length,0x20001100)==1
                event=bytes(parser.mem_read(0x20001100,20))
                assert event[9:11]==bytes((hour,minute)) and event[16:19]==bytes((1,mode,park)),event
                assert wire.endswith(f'{hour:02}:{minute:02}{mode}{park}\r\n'.encode());cases+=1
for args in ((4,1,10,0),(0,3,10,0),(0,1,24,0),(0,1,10,60)):
    assert call('formatCase',*args)==0;cases+=1

def ts(text):return int(dt.datetime.fromisoformat(text).replace(tzinfo=dt.timezone.utc).timestamp())
def rule(text):cpu.mem_write(symbols['zone'],text.encode()+b'\0')
for now,h,m,expected,changed in [
    ('2026-10-24T09:00:00',10,0,(1,59),1),
    ('2026-10-25T00:59:59',10,0,(10,0),0),
    ('2026-10-25T01:00:00',10,0,(10,0),0),
    ('2027-03-27T10:00:00',10,0,(0,59),1),
    ('2027-03-28T01:00:00',10,0,(10,0),0),
    ('2026-10-24T09:00:00',0,0,(0,0),0)]:
    rule('GMT0BST,M3.5.0/1,M10.5.0/2')
    assert call('wakeCase',ts(now),h,m)==changed
    assert tuple(cpu.mem_read(symbols['wake'],2))==expected
    length=call('formatCase',3,1,*expected)
    wire=bytes(cpu.mem_read(symbols['wire'],length))
    parser.mem_write(0x20001000,wire)
    assert parse('mm32_uart_parse_esp_line',0x20001000,length,0x20001100)==1
    assert bytes(parser.mem_read(0x20001109,2))==bytes(expected)
    cases+=1
rule('GMT0BST,M3.5.0/1:00:30,M10.5.0/2:00:30')
assert call('wakeCase',ts('2026-10-24T09:00:00'),10,0)==1
assert tuple(cpu.mem_read(symbols['wake'],2))==(2,0)
assert call('formatCase',3,1,2,0)>0
rule('GMT0')
assert call('wakeCase',ts('2026-10-24T09:00:00'),10,0)==0
assert not call('dstCase',ts('2026-10-24T09:00:00'))
presets=ast.literal_eval(re.search(r'const TIMEZONE_PRESETS = (\[.*?\]);',(ROOT/'arduino/CH899_Clock/web/index.html').read_text(encoding='utf-8'),re.S)[1])
iana=['Etc/GMT+12','Pacific/Pago_Pago','Pacific/Honolulu','America/Anchorage','America/Los_Angeles','America/Phoenix','America/Denver','America/Chicago','America/Mexico_City','America/New_York','America/Lima','America/Halifax','America/Santiago','America/St_Johns','America/Argentina/Buenos_Aires','Atlantic/South_Georgia','Atlantic/Azores','UTC','Europe/London','Europe/Paris','Europe/Athens','Africa/Johannesburg','Europe/Moscow','Asia/Tehran','Asia/Dubai','Asia/Karachi','Asia/Almaty','Asia/Kolkata','Asia/Dhaka','Asia/Yangon','Asia/Bangkok','Asia/Singapore','Asia/Tokyo','Australia/Darwin','Australia/Sydney','Pacific/Guadalcanal','Pacific/Auckland','Pacific/Fiji','Pacific/Apia','Pacific/Kiritimati']
for preset,location in zip(presets,iana):
    if location not in ('Europe/London','America/New_York','Australia/Sydney','Asia/Kolkata'): continue
    rule(preset[3])
    for year in (2026,):
        for month in (1,7):
            epoch=ts(f'{year}-{month:02}-15T12:34:56')
            assert call('localCase',epoch)==1
            b=bytes(cpu.mem_read(symbols['civil'],10))
            yy=struct.unpack_from('<H',b)[0]; offset=struct.unpack_from('<h',b,8)[0]
            expected=dt.datetime.fromtimestamp(epoch,dt.timezone.utc).astimezone(ZoneInfo(location))
            assert (yy,b[2],b[3],b[5],b[6],b[7],offset)==(expected.year,expected.month,expected.day,expected.hour,expected.minute,expected.second,int(expected.utcoffset().total_seconds()/60)),preset[0]
            cases+=1
def ntp(unix):
    p=bytearray(48);p[0]=0x24;p[1]=2;p[24:32]=bytes.fromhex('0102030405060708')
    p[40:44]=((unix+2208988800)&0xffffffff).to_bytes(4,'big')
    return p
for text in ('2026-10-25T01:00:00','2036-02-08T00:00:00'):
    epoch=ts(text);p=ntp(epoch);cpu.mem_write(symbols['packet'],bytes(p))
    assert call('packetCase',48)==1
    assert int.from_bytes(cpu.mem_read(symbols['reply_utc'],4),'little')==epoch
    for i,value in ((0,0xe4),(0,0x23),(1,0),(1,16),(24,0xff)):
        bad=p[:];bad[i]=value;cpu.mem_write(symbols['packet'],bytes(bad))
        assert call('packetCase',48)==0
    cpu.mem_write(symbols['packet'],bytes(p))
    assert call('packetCase',47)==0
print(f'PASS {cases} actual compiled settings/HTTP/MM32-protocol/calendar cases plus NTP rejection/rollover vectors')
transport,transport_symbols,transport_call=machine(ROOT/'tests/transport_fixture.axf')
assert transport_call('optionalSecondaryScenario')==0
print('PASS all 1440 HTTP/EEPROM daily update times and optional secondary disabled/primary retry')
for scenario in range(8):
    assert transport_call('ntpScenario',scenario)==0,('NTP transport',scenario)
for scenario in range(6):
    assert transport_call('sleepScenario',scenario)==0,('SLEEP guards',scenario)
print('PASS 14 real adapter scenarios: five-second fallback, either server wins, invalid responses, retry and guarded SLEEP')
for scenario in range(13):
    assert transport_call('ticketScenario',scenario)==0,('RTC ticket',scenario)
for scenario in range(5):
    assert transport_call('saveSleepScenario',scenario)==0,('Save/restart/NTP/TIME/SLEEP',scenario)
print('PASS 18 RTC-ticket and Save/restart/sync/TIME/SLEEP scenarios')
for scenario in range(8):
    assert transport_call('confirmationScenario',scenario)==0,('exact confirmation gate',scenario)
for scenario in range(2):
    assert transport_call('confirmationBounded',scenario)==0,('bounded confirmation',scenario)
print('PASS 10 exact/recent confirmation, no-echo, mismatch, retry, partial-write and rollover scenarios')
for scenario in (0,1,2,3,4,5,6):
    assert transport_call('announcementScenario',scenario)==0,('actual TIME producer/retry/SLEEP',scenario)
print('PASS 7 actual TIME producer, five-attempt limit, stale echo, partial write and page-deferral scenarios')
network,network_symbols,network_call=machine(ROOT/'tests/network_fixture.axf')
for scenario,elapsed,expected in [(0,9999,0),(0,10000,0x11),(0,50000,0x11),
        (1,5,0x100),(2,5,0x11),(3,5,0x11),(4,5,0),(5,50000,0),(0,0xffffffff,0x11)]:
    assert network_call('networkCase',scenario,elapsed)==expected,(scenario,elapsed)
for configured,connection in ((0,0),(1,0),(1,1),(2,0)):
    assert network_call('wakeCase',configured,connection)==(0x3101|(16 if configured==1 else 0))
source=(ROOT/'arduino/CH899_Clock/CH899_Clock.ino').read_text(encoding='utf-8')
html=(ROOT/'arduino/CH899_Clock/web/index.html').read_text(encoding='utf-8')
for removed in ('ESP8266mDNS','MDNS.','mdnsActive','startMdns','deviceMdnsAddress','mdnsHost'):
    assert removed not in source,removed
assert 'localAddress' not in html and 'mdnsHost' not in html
assert 'WiFi.hostname(hostname.c_str())' in source
assert 'constexpr char AP_NAME[] = "WiFi-Clock-Setup";' in source
assert 'WiFi.macAddress(mac);' in source
assert '"WiFi-Clock-%02X%02X%02X"' in source
assert 'host == normalizeHost(deviceHostname())' in source
assert 'AP_PREFIX' not in source and 'wifi-clock-setup-' not in source
print('PASS 13 network/AP cases without mDNS; mDNS code/UI removed, DHCP hostname retained')
for scenario in range(13):
    assert network_call('retryCase',scenario)==0,('continuous network retry',scenario)
print('PASS 13 continuous-retry scenarios, including 1000 failures, late link, stale proof, page/scan guards and rollover')
for scenario in range(2):
    assert transport_call('prolongedWakeObservation',scenario)==0,('prolonged DNS/NTP outage recovery',scenario)
print('PASS DNS/NTP outages beyond two minutes recover without inventing time or early SLEEP')
_,_,uart_call=machine(ROOT/'tests/uart_fixture.axf')
for scenario in range(9):
    assert uart_call('uartCase',scenario)==0,('UART/CLEAN',scenario)
print('PASS 9 real UART/reset scenarios: invalid settings, binary noise, oversized lines, confirmation, erase retry, restart')
for scenario in range(6):
    assert uart_call('echoUartCase',scenario)==0,('full echo UART parser',scenario)
print('PASS 6 full-length UART echo, mismatch, stale, partial and noise-recovery scenarios')
_,_,api_call=machine(ROOT/'tests/api_fixture.axf')
for scenario in range(19):
    assert api_call('apiCase',scenario)==0,('HTTP host/origin/token/session',scenario)
print('PASS 19 actual HTTP guard/session/name scenarios')
for scenario in range(5):
    assert transport_call('refreshSleepScenario',scenario)==0,('refresh/close grace',scenario)
assert api_call('refreshCloseCase')==0,('close request deadline and stale old page')
print('PASS 6 refresh-grace scenarios: boundary, reconnect/cancel, fresh close, guarded SLEEP, millis wrap, unchanged Save and bounded duplicate close')
for fixture,names in {
    'backend_fixture.cpp':['configChecksum','copyText','safeText','parseScheduleValue','loadConfig','saveConfig','updateConfig'],
    'transport_fixture.cpp':['beginNtpSync','serviceNtp','sendTimeToClock','beginTimeAnnouncement','serviceTimeAnnouncement'],
    'network_fixture.cpp':['startPortal','beginStationConnection','beginNetworkWake','enterNetworkRetry','serviceNetwork'],
    'uart_fixture.cpp':['eraseSavedConfig','hasSavedConfig','prepareFactoryReset','acknowledgeClean','scheduleRestart','serviceRestart','handleUartLine','serviceMm32Uart'],
    'api_fixture.cpp':['deviceHostname','deviceSetupName','normalizeHost','knownHost','responseHeaders','apiRequestAllowed','keepWebSessionAlive','closeWebSession']
}.items():
    fixture_text=(ROOT/'tests'/fixture).read_text()
    for name in names:
        pattern=r'^\w+ '+name+r'\([^\n]*\) \{[\s\S]*?^\}'
        actual=re.search(pattern,source,re.M);extracted=re.search(pattern,fixture_text,re.M)
        assert actual and extracted and actual[0]==extracted[0],(fixture,name,'stale fixture')
for removed in ('ntpTimedOut','requestNtpHost','AUTO_SEND_TIME_TO_MM32'):
    assert removed not in source,removed
print('PASS fixture functions match current firmware source; obsolete NTP scaffolding removed')
for scenario in range(10):
    assert transport_call('ntpPrecisionCase',scenario)==0,('fractional NTP',scenario)
assert transport_call('wholeSecondCase')==0,'whole-second send window'
print('PASS fractional NTP, latency/processing correction, carry/era/invalid-reply guards and whole-second send-window cases')
sys.path.insert(0,str(WORKSPACE/'tests/mm32'))
from check_rc6bc_deadline_guard import baseline
MM32=baseline.Tests
MM32.setUpClass()
assert re.search(r'constexpr uint32_t MM32_BAUD = 38400;',source)
assert 'Serial.begin(MM32_BAUD);' in source
for style in (3,0):
    address=transport_call('bridgeBegin',style)
    wire=bytes(transport.mem_read(address,64)).split(b'\0')[0]
    controller=MM32();controller.setUp();controller.prepare_echo()
    controller.call('radio_on')
    assert controller.raw(0x40004420)==13 and controller.raw(0x40004424)==4
    controller.consume(wire)
    echoed=bytes(controller.sent)
    assert echoed==b'\n'+wire,('ESP -> real MM32 -> echo',style,wire,echoed)
    assert controller.word('minute_log',190)==(style!=3)
    transport.mem_write(0x2000e000,echoed[1:-2]+b'\0')
    assert transport_call('bridgeEcho',0x2000e000)==1,('MM32 echo -> confirmed SLEEP',style)
print('PASS matched 38400-baud settings plus 2 compiled ESP R12 TIME -> actual RC6AY echo -> confirmed SLEEP cases, including mode restart')
