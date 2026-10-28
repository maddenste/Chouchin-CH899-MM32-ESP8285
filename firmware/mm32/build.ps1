param(
    [string]$CompilerPath = 'C:\Users\Steve\AppData\Local\Keil_v5\ARM\ARMCLANG\bin\armclang.exe'
)
$ErrorActionPreference = 'Stop'
$compiler = (Resolve-Path -LiteralPath $CompilerPath -ErrorAction Stop).Path
$artifactDir = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
$axf = Join-Path $artifactDir 'MM32SPIN05PF_WAKE_DIAGNOSTIC_RC6BF_20261028.axf'
$hex = [System.IO.Path]::ChangeExtension($axf, '.hex')
Push-Location (Join-Path $PSScriptRoot 'src\target')
try {
    & $compiler --target=arm-arm-none-eabi -mcpu=cortex-m0 -mthumb -std=gnu11 -Os -Wall -Wextra -Werror `
        '-Wl,--scatter=mm32spin05.sct' '-Wl,--entry=Reset_Handler' `
        '-Wl,--callgraph' '-Wl,--info=stack' '-Wl,--map' "-Wl,--list=$artifactDir\linker-report.txt" `
        startup.c parallel_home_main.c parallel_minute_component.c parallel_seconds_component.c `
        ../mm32_uart.c parallel_leds.c rtc.c -o $axf
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed' }
    # Equal-priority motor handlers cannot nest one another; UART can nest
    # over one. Allow an additional NMI/HardFault entry and fault-handler
    # chain, plus alignment on all three exception frames. Keep 128 B spare.
    $report = Get-Content -LiteralPath (Join-Path $artifactDir 'linker-report.txt') -Raw
    $reservation = [regex]::Match($report,
        'Execution Region ARM_LIB_STACK \(Base: 0x([0-9a-fA-F]+), Size: 0x([0-9a-fA-F]+)')
    if (!$reservation.Success -or
        [Convert]::ToUInt32($reservation.Groups[1].Value,16) -ne 0x20000B80 -or
        [Convert]::ToUInt32($reservation.Groups[2].Value,16) -ne 1152) {
        throw 'Expected B80..FFF stack reservation is missing or changed'
    }
    function Get-StackBytes([string]$Name) {
        $match = [regex]::Match($report, "Maximum Stack Usage for $Name 0x([0-9a-fA-F]+) bytes")
        if (!$match.Success) { throw "Missing stack annotation for $Name" }
        return [Convert]::ToInt32($match.Groups[1].Value, 16)
    }
    $motorStack = (@('SysTick_Handler','PendSV_Handler','TIM3_Handler','TIM14_Handler','DMA1_Channel2_3_Handler') |
        ForEach-Object { Get-StackBytes $_ } | Measure-Object -Maximum).Maximum
    $ordinaryStack = (Get-StackBytes 'Reset_Handler') + $motorStack +
        (Get-StackBytes 'UART2_Handler') + 2 * 36
    $faultStack = $ordinaryStack + (Get-StackBytes 'Default_Handler') + 36
    if ($faultStack + 128 -gt 1152) { throw "Stack budget exceeded: $faultStack + 128 > 1152" }
    Write-Host "Stack budget: ordinary $ordinaryStack B; with additional fault $faultStack B; reserved 1152 B."
    & (Join-Path (Split-Path $compiler) 'fromelf.exe') --i32 "--output=$hex" $axf
    if ($LASTEXITCODE -ne 0) { throw 'HEX export failed' }
    Get-FileHash -Algorithm SHA256 -LiteralPath $hex
} finally { Pop-Location }
