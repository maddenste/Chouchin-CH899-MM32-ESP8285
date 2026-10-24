# Candidate identity — not a stable release

Technical build record for **WiFi Clock v1.5**. Candidate pair: **MM32 RC6BB + ESP R12**, built 23 October 2026. The source was prepared for this repository on 24 October. Users looking for installation files should see [downloads and release status](../DOWNLOADS.md).

| Item | Identity |
| --- | --- |
| MM32 HEX | `MM32SPIN05PF_HANDOVER_RC6BB_20261023.hex` |
| MM32 signature | `0x4D50529F` |
| MM32 flash | 31,500 / 32,768 bytes |
| MM32 HEX SHA-256 | `51AA55088DD185D39BB42DDC0F766AEEA73774683DAA2A60C24283ADA8A5B922` |
| ESP BIN | `Chouchin-899-MM32-ESP-v1.5-R12-20261023.bin` |
| ESP displayed build | `ESP8285 MM32 v1.5 R12 20261023` |
| ESP BIN size | 375,776 bytes |
| ESP BIN SHA-256 | `4005096A46CF17D24C4813EB98204673A4561D7D5D662EE4870B82932934F206` |
| ESP target | ESP8285, ESP8266 Arduino Core 3.1.2, 80 MHz, DOUT/40 MHz, automatic/no-FS map |

MM32 programming uses the matching device-pack algorithm at flash base `0x08000000`. ESP application programming uses offset `0x0`, with the tested 1 MB override. These are different address conventions for different chips; do not interchange their files.

## Evidence and limits

The development packages and the initial repository tree were rebuilt from source and matched the listed HEX/BIN hashes; see [the verification record](REPOSITORY_CHECKS.md). Recheck after changes to source, build settings or tooling. A differing binary hash needs investigation before distribution.

RC6BB's selected offline ARM model suite passed 69 checks before repository preparation. Initial physical observations were smooth and read-only counters were clean. Overnight parking/resume, post-daily-wake smoothness and sustained endurance are still under qualification. No 24–48-hour pass or release readiness is claimed.

Candidate binaries and stock backups are not committed to Git. A firmware release must attach the qualified matched pair, verify source-to-binary identities and supply a SHA256SUMS manifest. Candidates remain pre-release until the physical qualification is complete.
