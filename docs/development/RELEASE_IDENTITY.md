# WiFi Clock v1.5.3 build identity

Release pair: **MM32 RC6BI + unchanged ESP R13**, 30 October 2026. [User downloads](../DOWNLOADS.md).

| Item | Identity |
| --- | --- |
| MM32 build | `MM32SPIN05PF_DRIVE_TRIAL_RC6BI_20261029.hex` |
| MM32 signature | `0x4D5052A6` |
| MM32 flash | 32,052 / 32,768 bytes; 716 bytes free |
| MM32 HEX SHA-256 | `ABE863D0C6F65D601A3D725018F0CA60E8284A7CA9FEAB759AAAAB5F5BD3ED18` |
| ESP build | `Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin` |
| ESP displayed build | `ESP8285 MM32 v1.5 R13 20261024` |
| ESP BIN size | 375,744 bytes |
| ESP BIN SHA-256 | `34A11A31DE0A7231C2B32B82DBB751DF900071B09E9DB2A943FEFAB2F5640C8F` |
| ESP target | ESP8285, ESP8266 Arduino Core 3.1.2, 80 MHz, DOUT/40 MHz, automatic/no-FS map |

MM32 flash base is `0x08000000`; ESP application offset is `0x0` with the tested 1 MB override. Do not interchange the files.

The installation ZIP uses friendly names: `firmware/WiFi-Clock-MM32.hex`, `WiFi-Clock-ESP.bin` and `Install-MM32.uvprojx`. These are the exact bytes identified above. Firmware binaries are release assets, not committed source. Previous release assets were saved privately before removal; historical Git tags remain for source history.

## Scope

The release uses the exact installed RC6BI image. Its historic internal `DRIVE_TRIAL` filename is retained for reproducible identity; end-user downloads use the friendly names above. Relative to RC6BG, it adds the RC6BH held-lap RTC rate refresh and changes PA7/PB0 runtime alternate-function push-pull MODE from 01 to 11. Homing/coarse GPIO and minute drive remain unchanged. The rate refresh is Stop2Go-only, bounded to 1% per lap with a two-count deadband and accepted-reference guards. Ordinary holds do not rebuild TIM3. See [manufacturer evidence](SOURCES.md#seconds-output-drive-evidence).

No further application cleanup was made for publication: preserving the physically tested image takes precedence over cosmetic source changes. ESP R13 is unchanged.

All 54 SRAM objects keep their prior addresses and sizes. Static allocation remains 2,944 bytes, including existing operational telemetry. The 1,152-byte stack has a conservative bound of 888 bytes ordinarily or 1,008 with an additional fault path. The build enforces a further 128-byte allowance. These are static bounds, not measured runtime maxima.

See [testing and evidence limits](TESTING.md) and [publication checks](REPOSITORY_CHECKS.md). The successful daily wake on 30 October does not establish the root cause of earlier resets or complete endurance qualification.
