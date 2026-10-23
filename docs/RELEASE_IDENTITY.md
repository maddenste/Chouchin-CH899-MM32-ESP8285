# Candidate identity — not a stable release

Public-facing version: **WiFi Clock v1.5**. Candidate pair: **MM32 RC6BB + ESP R12**, built 23 October 2026. The source was prepared for this repository on 24 October. No new version was silently substituted.

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

The development packages were independently rebuilt from their supplied source and matched the listed HEX/BIN hashes. Repository rearrangement must be checked separately; see [testing](TESTING.md). Exact ESP binary reproduction may depend on sketch/build paths; a changed hash must be investigated, not quietly added as a second equivalent file.

RC6BB's selected offline ARM model suite passed 69 checks before repository preparation. Initial physical observations were smooth and read-only counters were clean. Overnight parking/resume, post-daily-wake smoothness and sustained endurance are still under qualification. No 24–48-hour pass or release readiness is claimed.

There are deliberately **no candidate binary files or stock backups in the Git tree** and no stable download links. A future firmware release must attach the qualified matched pair, verify source-to-binary identities and supply a SHA256SUMS manifest. Do not retag unqualified candidates as stable.
