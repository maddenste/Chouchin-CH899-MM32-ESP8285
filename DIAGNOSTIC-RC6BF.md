# MM32 RC6BF — isolated wake diagnostic

This is a test build for the MM32 movement board, not a new public release.
It has NOT been installed by Codex. ESP R13 does not need changing.

## What changes

- Scheduled Wi-Fi wake begins three seconds after the selected time:
  a 10:00 setting activates ESP at approximately 10:00:03.
- M.SET stays immediate. Normal initial power-on/homing access is unchanged.
- The motor waveform, pulse widths, speeds, ramp and phase ownership are unchanged.
- Boot diagnostics retain the original reset flags, then clear historical
  hardware flags once so a later reset has fresh evidence.
- A deliberate settings/CLEAN software restart records its reason.
- Boot records survive ordinary motor rehoming. They are not a promise
  of persistent SRAM after power loss.

For an early DST wake the session starts three seconds later too, leaving
three seconds less acquisition lead. The displayed daily setting is unchanged.
This is a diagnostic test, not a claimed cure for the unexplained restart.
The first boot after flashing may still record programmer/reset history.
The recorder saves that value and clears it; a subsequent reset is the
useful fresh-cause test. Codex will check that the clear took effect.

## Install when ready

1. Extract the whole ZIP. Keep Install-MM32-RC6BF.uvprojx beside the build folder.
2. Open Install-MM32-RC6BF.uvprojx in Keil uVision.
3. Select the correct CMSIS-DAP programmer, SWD and MM32SPIN05PF.
4. Use Flash > Download and check Programming Done / Verify OK.
5. Restart normally and allow homing and time setting to complete.

Do not use Debug to begin the test. Its automatic flashing is disabled,
but opening a debug session can still interfere with a running clock.
Codex can read this build's diagnostics without stopping it once installed.
Use the previously saved RC6BE installer or the unchanged v1.5.1 GitHub
release to roll back. Do not flash the HC32 board with this package.

## Safety and original firmware

Install at your own risk. Factory MM32 firmware is read-protected and cannot
be backed up or recovered from the chip after replacement. Use the existing
3.3V wiring/power instructions. Do not change the ESP for this test.

## Developer source

source/ contains the complete MM32 build inputs and historical model helpers.
Use Arm Compiler 6.24 and source/firmware/mm32/build.ps1 to rebuild; this script
never flashes. Tests use Python 3.12 with source/tests/requirements.txt.
Run source/tests/mm32/check_rc6bf_wake_diagnostic.py; do not use broad test
discovery or standalone historical entry points. See VALIDATION.md.

Signature: 0x4D5052A3. Diagnostic words are seconds_log[80..87]:
0 magic 0x52424631;1 boot RCC_CSR;2 CSR after clear;3 previous validated
software-request reason (1 settings,2 CLEAN);4 scheduled due stamp;
5 delayed activation stamp;6/7 current software-request reason/cookie.
The actual addresses are recorded in VALIDATION.md. These words are not
commands and must not be edited while the clock runs.
