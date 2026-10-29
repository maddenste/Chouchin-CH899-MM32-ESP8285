"""Dependency-free publication checks. Never connects to a clock or network."""
from pathlib import Path
import hashlib
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
problems = []
required = ('README.md', 'LICENSE', 'NOTICE.md', 'THIRD_PARTY_NOTICES.md',
            'docs/GETTING_STARTED.md', 'docs/MM32.md', 'docs/FLASHING.md',
            'docs/USER_GUIDE.md', 'docs/TROUBLESHOOTING.md',
            'docs/DOWNLOADS.md', 'docs/development/README.md',
            'docs/development/RELEASE_IDENTITY.md', 'docs/development/TESTING.md')
for name in required:
    if not (ROOT / name).is_file():
        problems.append(f'Missing required file: {name}')

def source_digest(path):
    # Git checkout line-ending conversion must not create false mismatches.
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()

manifest = ROOT / 'source-manifest.sha256'
if not manifest.exists():
    problems.append('Missing source-manifest.sha256')
else:
    recorded = set()
    for line in manifest.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        digest, name = line.split('  ', 1)
        file = ROOT / name
        recorded.add(name)
        if not file.is_file() or source_digest(file) != digest:
            problems.append(f'Source identity mismatch: {name}')
    for directory in ('firmware/mm32/src', 'firmware/esp/arduino'):
        for file in (ROOT / directory).rglob('*'):
            if file.is_file() and file.relative_to(ROOT).as_posix() not in recorded:
                problems.append(f'Unrecorded firmware source: {file.relative_to(ROOT)}')

docs = (list(ROOT.glob('*.md')) + list((ROOT / 'docs').rglob('*.md')) +
        list((ROOT / 'firmware').glob('*.md')) + list((ROOT / 'tests').glob('*.md')) +
        list((ROOT / '.github').rglob('*.md')))
for file in docs:
    body = file.read_text(encoding='utf-8')
    links = re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"\n]*")?\)', body)
    links += re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', body)
    for link in links:
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', link) or link.startswith('#'):
            continue
        target = unquote(link.split('#', 1)[0])
        if target and not (file.parent / target).exists():
            problems.append(f'Broken local link in {file.relative_to(ROOT)}: {link}')

main = (ROOT / 'firmware/mm32/src/target/parallel_home_main.c').read_text()
if '0x4d5052a4u' not in main:
    problems.append('MM32 source is not RC6BG')
auto = (ROOT / 'firmware/mm32/src/target/autonomous_stop2go.h').read_text()
irq = (ROOT / 'firmware/mm32/src/target/fine_stop2go.h').read_text()
if auto.count('pwm_try_resume();') != 0 or irq.count('pwm_try_resume();') != 1:
    problems.append('Warm release no longer has exactly one timer-owned caller')
html = (ROOT / 'firmware/esp/arduino/CH899_Clock/web/index.html').read_text(encoding='utf-8-sig')
esp_main = (ROOT / 'firmware/esp/arduino/CH899_Clock/CH899_Clock.ino').read_text()
if 'ESP8285 MM32 v1.5 R13 20261024' not in esp_main:
    problems.append('ESP source is not R13')
header = (ROOT / 'firmware/esp/arduino/CH899_Clock/web_ui.h').read_text(encoding='utf-8-sig')
if '\n' + html + '\n)CH899_WEB";' not in header:
    problems.append('Generated webpage header is stale')

try:
    files = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard'],
        text=True, stderr=subprocess.DEVNULL).splitlines()
except (OSError, subprocess.CalledProcessError):
    files = []  # Link/source checks also work before local git initialization.
for name in files:
    lower = name.lower()
    if Path(lower).suffix in ('.bin', '.hex', '.axf', '.elf', '.exe', '.dll', '.flm', '.sr'):
        problems.append(f'Compiled/private artifact staged: {name}')
    if any(part in ('private', 'captures', 'backups', '.analysis_deps') for part in Path(lower).parts):
        problems.append(f'Private directory staged: {name}')
if problems:
    print('\n'.join(problems), file=sys.stderr)
    raise SystemExit(1)
print(f'PASS repository checks: {len(docs)} Markdown documents, source identities, webpage, ownership and staged-file boundaries')
