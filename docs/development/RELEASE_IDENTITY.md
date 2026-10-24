# WiFi Clock v1.5 build identity

Release pair: **MM32 RC6BC + ESP R13**, 24 October 2026. [User downloads](../DOWNLOADS.md).

| Item | Identity |
| --- | --- |
| MM32 HEX | `MM32SPIN05PF_DEADLINE_GUARD_RC6BC_20261024.hex` |
| MM32 signature | `0x4D5052A0` |
| MM32 flash | 31,724 / 32,768 bytes |
| MM32 HEX SHA-256 | `73AF2420F37744605B22B687398548D857226D3AC35B146E19C21117A66A40D5` |
| ESP BIN | `Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin` |
| ESP displayed build | `ESP8285 MM32 v1.5 R13 20261024` |
| ESP BIN size | 375,744 bytes |
| ESP BIN SHA-256 | `34A11A31DE0A7231C2B32B82DBB751DF900071B09E9DB2A943FEFAB2F5640C8F` |
| ESP target | ESP8285, ESP8266 Arduino Core 3.1.2, 80 MHz, DOUT/40 MHz, automatic/no-FS map |

MM32 flash base is `0x08000000`; ESP application offset is `0x0` with the tested 1 MB override. Do not interchange the files.

RC6BC retains the seconds waveform and corrects minute-scheduler deadline handling. Its cleaned source produces the identical HEX. ESP R13 changes the footer link, password/custom-rule field limits, trailing-dot NTP acceptance and displayed build ID. EEPROM format and UART/NTP/SLEEP policies are unchanged.

The source packages were rebuilt and compared with these identities. Repository-specific results are in [REPOSITORY_CHECKS.md](REPOSITORY_CHECKS.md). Binaries and private board captures are not committed to Git; prepared installation files and checksums are release assets.

The owner reports consistently smooth seconds movement. Read-only daytime samples recorded no fault or PWM rebuild. **A completed overnight parking/06:00 resume, live DST transition or 24–48-hour endurance pass is not claimed.** See [testing](TESTING.md).

## Installation package

The end-user download is `WiFi-Clock-v1.5.zip`. Inside it, `firmware/WiFi-Clock-MM32.hex` and `WiFi-Clock-ESP.bin` are byte-identical to the build-named files above. `Install-MM32.uvprojx` selects the included HEX under `firmware`; it does not require users to assemble a build folder. The tag and original individual downloads remain unchanged for reproducibility. Documentation and packaging updates are on the main branch.
