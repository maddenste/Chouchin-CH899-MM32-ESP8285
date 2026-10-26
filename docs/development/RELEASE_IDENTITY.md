# WiFi Clock v1.5.1 build identity

Release pair: **MM32 RC6BE + unchanged ESP R13**, 26 October 2026. [User downloads](../DOWNLOADS.md).

| Item | Identity |
| --- | --- |
| MM32 HEX | `MM32SPIN05PF_SESSION_SLEEP_RC6BE_20261026.hex` |
| MM32 signature | `0x4D5052A2` |
| MM32 flash | 31,824 / 32,768 bytes (944 bytes free) |
| MM32 HEX SHA-256 | `45741989E1386054B5E849703E591B25A82FBC4770BEF932AB488C4B22FDBBFA` |
| ESP BIN | `Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin` |
| ESP displayed build | `ESP8285 MM32 v1.5 R13 20261024` |
| ESP BIN size | 375,744 bytes |
| ESP BIN SHA-256 | `34A11A31DE0A7231C2B32B82DBB751DF900071B09E9DB2A943FEFAB2F5640C8F` |
| ESP target | ESP8285, ESP8266 Arduino Core 3.1.2, 80 MHz, DOUT/40 MHz, automatic/no-FS map |

MM32 flash base is `0x08000000`; ESP application offset is `0x0` with the tested 1 MB override. Do not interchange the files.

RC6BE includes the deferred-TIME promotion fix from RC6BD and allows Wi-Fi acquisition to complete after safely retaining fresh TIME during hand setting. Pending time remains available afterward; M.SET/web access, active correction and REC/CLEAN ownership remain protected. Motor waveform, UART protocol and ESP application source are unchanged from v1.5. The rebuilt HEX matches the installed bench candidate exactly.

Static allocation including fixed diagnostics remains 2,944 bytes. The separate 1,152-byte stack has a conservative nested bound of 888 bytes ordinarily, or 1,008 including an additional fault handler. The build enforces a further 128-byte margin; these are static bounds rather than measured runtime maxima.

## Installation package

`WiFi-Clock-v1.5.1.zip` contains the firmware under friendly names: `firmware/WiFi-Clock-MM32.hex` and `WiFi-Clock-ESP.bin`. `Install-MM32.uvprojx` selects the included HEX. The identities above apply to those exact bytes. Binaries are release assets, not committed into the source tree. The v1.5 tag and assets remain available unchanged for rollback; v1.5.1 source corresponds to the new tag.

## Qualification limits

The development board showed the pending-session fix working during hand setting and the normal M.SET access window closing. This is not a completed RC6BE endurance qualification. An unexpected restart observed on RC6BC during a daily-wake period remains unexplained; RC6BE is not claimed to fix it. No reset recorder or motor timing experiment is included. See [TESTING.md](TESTING.md) and [REPOSITORY_CHECKS.md](REPOSITORY_CHECKS.md).
