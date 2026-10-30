# Publication checks — v1.5.3

The publication tree supplies the exact installed **MM32 RC6BI** and unchanged **ESP R13**. Installation remains one ZIP with a preconfigured project; no compiling or moving firmware files is required.

- Final MM32 source rebuild and an independent copied-source rebuild both reproduce the HEX in [the build identity](RELEASE_IDENTITY.md).
- 106 compiled ARM model case executions passed on the final RC6BI image, with no skipped cases: drive 2, temperature/rate 6, wake 7, session 8, pending-time 4, deadlines 12, handover 5, motor 6 and broader regressions 28 + 28. Inherited cases overlap some focused suites; this is an execution count, not 106 distinct hardware scenarios.
- The differential drive case compared against RC6BH. All 54 SRAM objects retain their addresses/sizes. Flash occupies 32,052 of 32,768 bytes; the existing 1,152-byte stack allocation and enforced budget remain valid.
- ESP R13 application source and BIN are unchanged. Its compiled backend/protocol checks passed against RC6BI, including TIME echo/SLEEP and mode restart; 116 focused early-DST checks and the desktop/mobile mocked-browser suite passed. Two stale fixture entry points were corrected to select RC6BI instead of a historical default. No new physical radio or broad timezone qualification is claimed.
- Installer project XML, selected HEX, file placement, disabled flash-before-debug and all embedded firmware hashes were checked. Public assets are downloaded and hash-checked after publication. Source archives are compared with the verified local source.
- Repository checks validate local document/image links, normalized source hashes, generated webpage and build identity. CI runs those host checks without a licensed compiler or hardware.
- No private captures, probe identifiers, credentials, factory backups, vendor SDKs or programming binaries are distributed.

The previous release and all assets were downloaded and checked against GitHub's SHA-256 digests before replacement. Historical tags remain for source history; **v1.5.3 is the only release offered for installation**.

## Physical evidence

The owner reported sustained smooth seconds-hand movement through the overnight RC6BI trial. A continuous read-only capture on 30 October covered 09:54:03–10:02:09 GMT with 393 samples. Uptime advanced continuously, stage stayed 7, fault stayed 0, PWM epoch stayed 1 and seconds GPIO modes stayed 11. ESP woke near 10:00:03; TIME count increased from 1 to 2 and ESP was asleep again by the 10:00:09 sample. No RTC failure/reject, UART overflow or UART recovery was added. There were 120 framing observations during ESP startup. Largest sample spacing was under 1.242 seconds, with sequential field reads.

This capture establishes a successful observed daily wake, not exact electrical-edge timing or physical smoothness. The latter is the owner's observation. Sticky reset flags were unchanged and do not identify a reset cause by themselves. The root cause of earlier resets remains unproven. Full temperature-range testing, long-term battery performance, every mode on every movement and a completed 24–48-hour final-build endurance test are not claimed. Manufacturer documentation inconsistencies are retained in [the source evidence](SOURCES.md#seconds-output-drive-evidence).

No running clock was altered during publication.
