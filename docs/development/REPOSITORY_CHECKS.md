# Publication-tree verification — 24 October 2026

The publication tree contains cleaned MM32 RC6BC source and ESP R13. It does not contain private RAM dumps, Wi-Fi credentials, original device backups, compiled vendor tools or firmware binaries.

## Identity

- MM32 source cleanup removes an unused RTC helper and redundant homing checks; rebuilt HEX is byte-identical to RC6BC.
- ESP R13 source and canonical/generated HTML match the reviewed package.
- Source manifest normalizes CRLF to LF for Git checkout compatibility.
- Release SHA256SUMS records actual downloadable file bytes separately.
- The programming project has no developer-specific probe serial binding and names the matching RC6BC HEX and disables automatic flashing when entering Debug.
- Source, build, export and flash remain separate operations.

## Checks

Repository MM32 and ESP builds reproduced the exact release hashes. All **81 MM32 checks passed from this publication tree**: focused 12 (51.324 s), handover 5 (24.534 s), general halves 28 each (173.774 s / 173.300 s), and motor 8 (112.934 s). Three additional historical BB comparison cases passed during development; they are not included in the public suite because the old binary is not shipped.

ESP compiled adapters and desktop/mobile browser checks passed from this tree: 18,809 settings/HTTP/protocol/calendar cases, all 1,440 daily update choices, retained network/UART/session tests, R13 expanded input round-trip/limits, fractional NTP and whole-second send windows, 116 focused DST assertions and actual RC6BC handoffs. Some inherited console labels retain older build names; fixture imports and signature checks select the actual RC6BC image.

The programming ZIP was checked for readable contents and an exact embedded HEX match. The release includes both standalone firmware files, that ZIP and a SHA256SUMS manifest. No vendor device pack or flash algorithm is redistributed.

The CI workflow checks document links, source manifest, identifiers, generated HTML and accidental private/binary files. It does not build with the licensed Arm compiler, contact a clock or certify physical smoothness.

## Physical limits

The owner reports smooth seconds. Daytime RAM captures observed progression without a fault or PWM rebuild. Night parking, 06:00 resume, this night's actual DST change and a completed 24–48h endurance run are not recorded as passes. Sparse counters cannot prove physical movement quality or exact subsecond accuracy.
