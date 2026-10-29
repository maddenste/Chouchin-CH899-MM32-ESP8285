# WiFi Clock v1.5.2 build identity

Release pair: **MM32 RC6BG + unchanged ESP R13**, 29 October 2026. [User downloads](../DOWNLOADS.md).

| Item | Identity |
| --- | --- |
| MM32 build | `MM32SPIN05PF_CLEAN_WAKE_RC6BG_20261029.hex` |
| MM32 signature | `0x4D5052A4` |
| MM32 flash | 31,544 / 32,768 bytes; 1,224 bytes free |
| MM32 HEX SHA-256 | `90988DAC189E34B2F7334DF86946CA497CEF3E1D2B51BA4A854F2DE01B9397B6` |
| ESP build | `Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin` |
| ESP displayed build | `ESP8285 MM32 v1.5 R13 20261024` |
| ESP BIN size | 375,744 bytes |
| ESP BIN SHA-256 | `34A11A31DE0A7231C2B32B82DBB751DF900071B09E9DB2A943FEFAB2F5640C8F` |
| ESP target | ESP8285, ESP8266 Arduino Core 3.1.2, 80 MHz, DOUT/40 MHz, automatic/no-FS map |

MM32 flash base is `0x08000000`; ESP application offset is `0x0` with the tested 1 MB override. Do not interchange the files.

The installation ZIP uses friendly names: `firmware/WiFi-Clock-MM32.hex`, `WiFi-Clock-ESP.bin` and `Install-MM32.uvprojx`. These are the exact bytes identified above. Firmware binaries are release assets, not committed source. Previous release assets were saved privately before removal; historical Git tags remain for source history.

## Scope

Against RC6BE, application source differs only in the three-second scheduled ESP wake delay and build identity. M.SET wake remains immediate. RC6BF's temporary reset recorder, reset cookies and wake timestamp stores have been removed. Existing fault handling and operational counters remain. Motor, RTC and UART implementation files and ESP R13 application source are unchanged.

All 54 SRAM objects keep their prior addresses and sizes. Static allocation remains 2,944 bytes, including existing operational telemetry. The 1,152-byte stack has a conservative bound of 888 bytes ordinarily or 1,008 with an additional fault path. The build enforces a further 128-byte allowance. These are static bounds, not measured runtime maxima.

See [testing and evidence limits](TESTING.md) and [publication checks](REPOSITORY_CHECKS.md). One successful delayed daily wake is not proof of the earlier restart's root cause or a completed endurance qualification.
