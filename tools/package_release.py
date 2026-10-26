"""Create the end-user ZIP from existing v1.5 builds. Never flashes a device."""
from pathlib import Path
import argparse
import hashlib
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'output/release')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)

identities = {
    'firmware/WiFi-Clock-MM32.hex': (
        ROOT / 'firmware/mm32/build/MM32SPIN05PF_SESSION_SLEEP_RC6BE_20261026.hex',
        '45741989E1386054B5E849703E591B25A82FBC4770BEF932AB488C4B22FDBBFA'),
    'WiFi-Clock-ESP.bin': (
        ROOT / 'firmware/esp/build/Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin',
        '34A11A31DE0A7231C2B32B82DBB751DF900071B09E9DB2A943FEFAB2F5640C8F'),
}
files = {}
for name, (path, expected) in identities.items():
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest().upper() != expected:
        raise SystemExit('Build identity mismatch: ' + str(path))
    files[name] = data

for extension in ('uvprojx', 'uvoptx'):
    path = ROOT / ('firmware/mm32/MM32SPIN05_SessionSleep_RC6BE_Programmer.' + extension)
    text = path.read_text(encoding='utf-8-sig')
    text = text.replace('<TargetName>Target_1</TargetName>',
                        '<TargetName>WiFi Clock v1.5</TargetName>')
    text = text.replace('<OutputDirectory>.\\build\\</OutputDirectory>',
                        '<OutputDirectory>.\\firmware\\</OutputDirectory>')
    text = text.replace('MM32SPIN05PF_SESSION_SLEEP_RC6BE_20261026.hex',
                        'WiFi-Clock-MM32.hex')
    ET.fromstring(text)
    files['Install-MM32.' + extension] = text.encode('utf-8')

project = ET.fromstring(files['Install-MM32.uvprojx'])
assert project.find('.//OutputDirectory').text == '.\\firmware\\'
assert project.find('.//OutputName').text == 'WiFi-Clock-MM32.hex'
assert project.find('.//Device').text == 'MM32SPIN05PF'
assert project.find('.//UpdateFlashBeforeDebugging').text == '0'
assert all(ET.fromstring(files['Install-MM32.' + e]).find('.//TargetName').text
           == 'WiFi Clock v1.5' for e in ('uvprojx', 'uvoptx'))

files['START-HERE.txt'] = '''WiFi Clock v1.5.1
MM32SPIN05PF + ESP8285 / ESP-01F

UPDATING FROM v1.5?
Only update the MM32 movement controller. ESP R13 is unchanged, so skip the
ESP flashing step if already installed. Your saved Wi-Fi settings remain on
the ESP. After the MM32 update, disconnect programming leads and restart normally.

READ BEFORE INSTALLING
Install at your own risk. The factory MM32 movement firmware is read-protected
and cannot be read out for a backup. Once overwritten, it cannot be recovered
from the chip. This replacement MM32 firmware was built from scratch.
Testing is ongoing. Please report bugs or unexpected behaviour:
https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues

1. Extract this entire ZIP to a folder on your PC. Do not open the project
   from inside the ZIP. All firmware files are already in the correct places.
2. Read the installation guide before connecting your clock:
   https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/blob/main/docs/GETTING_STARTED.md
3. Install Keil ÂµVision and MindMotion.MM32SPIN0x_DFP 1.0.8 separately.
   Open Install-MM32.uvprojx, select your CMSIS-DAP programmer and SWD,
   then use Flash > Download. No compiling or file selection is needed.
   MM32 guide:
   https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/blob/main/docs/MM32.md
4. Install WiFi-Clock-ESP.bin using the separate ESP guide. This uses a
   3.3 V USB-to-serial adapter, with MM32 RESET grounded and ESP IO0 grounded
   at power-on. Follow the complete wiring and power instructions:
   https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/blob/main/docs/FLASHING.md
5. Remove temporary programming connections, restart normally, join
   WiFi-Clock-Setup and open http://192.168.4.1/ to save your settings.

Use regulated 3.3 V power/signals; remove batteries while externally powered.
Do not connect adapter/programmer power outputs alongside the external supply.
Never apply 5 V. Other CH899 board variants need different firmware.

The firmware is ready to install; you do not need to edit or build it.
Technical build identifiers: MM32 RC6BE / ESP R13.
Source and test evidence:
https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285
'''.encode('utf-8')
for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
    files[name] = (ROOT / name).read_bytes()
files['SHA256SUMS.txt'] = ''.join(
    hashlib.sha256(files[name]).hexdigest().upper() + '  ' + name + '\n'
    for name in identities).encode('ascii')

archive = args.output / 'WiFi-Clock-v1.5.1.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as out:
    for name, data in files.items():
        entry = zipfile.ZipInfo(name, (2026, 10, 26, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        out.writestr(entry, data)
with zipfile.ZipFile(archive) as out:
    assert out.testzip() is None
    assert set(out.namelist()) == set(files)
    for name, data in files.items():
        assert out.read(name) == data
print(hashlib.sha256(archive.read_bytes()).hexdigest().upper() + '  ' + archive.name)
