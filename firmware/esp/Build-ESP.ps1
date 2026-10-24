param(
    [string]$ArduinoCli = 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
)
$ErrorActionPreference = 'Stop'
$cli = (Resolve-Path -LiteralPath $ArduinoCli -ErrorAction Stop).Path
$cores = & $cli core list
if ($LASTEXITCODE -ne 0 -or ($cores -join "`n") -notmatch 'esp8266:esp8266\s+3\.1\.2\s') {
    throw 'Install ESP8266 Arduino Core 3.1.2 before building this candidate.'
}
& (Join-Path $PSScriptRoot 'arduino\CH899_Clock\tools\embed_web_ui.ps1')
$cache = Join-Path ([IO.Path]::GetTempPath()) 'CH899-MM32-ESP-UI-R13-build'
& $cli compile --fqbn 'esp8266:esp8266:esp8285:eesz=autoflash' `
    --build-path $cache (Join-Path $PSScriptRoot 'arduino\CH899_Clock')
if ($LASTEXITCODE -ne 0) { throw 'ESP compilation failed; do not flash an older BIN.' }
$out = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$bin = Join-Path $out 'Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin'
Copy-Item -LiteralPath (Join-Path $cache 'CH899_Clock.ino.bin') -Destination $bin
Get-FileHash -Algorithm SHA256 -LiteralPath $bin
