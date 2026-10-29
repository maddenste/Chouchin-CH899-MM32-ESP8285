# Publication checks — v1.5.2

The publication tree supplies MM32 RC6BG and unchanged ESP R13. Installation remains one ZIP with a preconfigured programming project; no compilation is required by users.

- The publication-source MM32 build reproduces the exact installed RC6BG HEX recorded in [RELEASE_IDENTITY.md](RELEASE_IDENTITY.md).
- The installation ZIP is checked for valid XML, correct firmware placement, disabled flash-before-debug and exact embedded firmware hashes. Downloaded GitHub assets are checked against local hashes after publication.
- MM32 cleanup validation passed 100 compiled model cases. After removal of one redundant reset-path barrier, seven targeted startup/wake/rehome/reset checks passed again on the final image. The broader regression image differed only by that barrier; validation is not represented as a full second regression run.
- Packaged source independently rebuilt the final HEX. All 54 SRAM objects retained their previous layout.
- ESP R13 application source and release binary are unchanged. No new radio, browser or broad timezone qualification is claimed for this release. The producer/parser fixture now selects RC6BG for future runs.
- Repository checks validate local Markdown links, normalized source identities, generated webpage, build signature and timer-owned warm release. CI runs these host-side checks without licensed compilation or hardware access.
- Private captures, probe identifiers, credentials, factory backups and vendor tools are excluded from the public tree and installation ZIP.

Before replacement, both previous releases and all their assets were saved locally and hash-checked. Historical source tags are retained. The only release offered for installation is v1.5.2.

## Physical evidence

The diagnostic predecessor ran overnight with PWM epoch 1 retained across parking and morning operation. On 29 October, a continuous 09:56–10:02 read-only capture observed scheduled ESP activation at 10:00:03, a fresh time record and ESP shutdown by 10:00:09. Uptime stayed continuous, reset flags stayed clear, PWM epoch stayed 1, and no fault, RTC error, UART overflow or UART recovery was recorded. There were 120 boot framing observations. The largest sample gap was 1.25 seconds.

RC6BG was then installed by the owner. A live check identified signature `0x4D5052A4`, normal running, both hands homed, PWM epoch 1 and no new UART/RTC errors. It was a short post-installation observation, not an endurance test.

The earlier daily-wake restart's root cause remains unproven. A completed 24–48-hour run on the exact final pair, physical smoothness in every mode and long-term battery performance are not claimed. No running clock was altered during release publication.
