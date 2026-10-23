param(
    [string]$Compiler='C:\Users\Steve\AppData\Local\Keil_v5\ARM\ARMCLANG\bin\armclang.exe',
    [string]$Python='C:\Users\Steve\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$NodeModules='C:\Users\Steve\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules',
    [string]$Workspace=''
)
$ErrorActionPreference='Stop'
if($Workspace){$env:MM32_TEST_WORKSPACE=(Resolve-Path -LiteralPath $Workspace).Path}
$sketch=Join-Path $PSScriptRoot '..\arduino\CH899_Clock'
$common=@('--target=arm-arm-none-eabi','-mcpu=cortex-m0','-mthumb','-O2',"-I$sketch")
foreach($item in @(@('clock_calendar.c','calendar.o'),@('clock_ntp_packet.c','ntp.o'))) {
    & $Compiler @common -std=c11 -c (Join-Path $sketch $item[0]) -o (Join-Path $PSScriptRoot $item[1])
    if($LASTEXITCODE){throw "C compilation failed: $($item[0])"}
}
& $Compiler @common -std=c11 -c (Join-Path $PSScriptRoot 'calendar_fixture.c') -o (Join-Path $PSScriptRoot 'calendar_fixture.o')
if($LASTEXITCODE){throw 'Calendar fixture compilation failed'}
foreach($name in @('backend','transport','network','uart','api')) {
    $objects=@()
    if($name -in @('backend','transport')) {
        $objects=@((Join-Path $PSScriptRoot 'calendar.o'),(Join-Path $PSScriptRoot 'ntp.o'))
    }
    if($name -eq 'backend'){$objects+=Join-Path $PSScriptRoot 'calendar_fixture.o'}
    $entry=@{backend='storageCase';transport='ntpScenario';network='networkCase';uart='uartCase';api='apiCase'}[$name]
    & $Compiler @common -std=c++11 -fno-exceptions -fno-rtti "-Wl,--entry=$entry" '-Wl,--no_remove' '-Wl,--ro-base=0x08000000' '-Wl,--rw-base=0x20000000' `
        (Join-Path $PSScriptRoot "${name}_fixture.cpp") @objects -o (Join-Path $PSScriptRoot "${name}_fixture.axf")
    if($LASTEXITCODE){throw "Fixture compilation failed: $name"}
}
& $Python (Join-Path $PSScriptRoot 'test_backend.py')
if($LASTEXITCODE){throw 'Backend/model regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_dst_early.py')
if($LASTEXITCODE){throw 'Early DST/boundary regression failed'}
& node (Join-Path $PSScriptRoot 'test_web_ui.cjs') $NodeModules
if($LASTEXITCODE){throw 'Browser regression failed'}
