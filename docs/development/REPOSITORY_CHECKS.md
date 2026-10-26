# Publication-tree verification — v1.5.1

The publication tree contains MM32 RC6BE source and unchanged ESP R13. No private RAM captures, network credentials, probe identifiers, original device backups, vendor tools or firmware binaries are committed.

## Identity and scope

- Rebuilt MM32 HEX is byte-identical to the installed bench candidate: `45741989E1386054B5E849703E591B25A82FBC4770BEF932AB488C4B22FDBBFA`.
- The only application-source changes from v1.5 are deferred-TIME promotion, early acquisition completion during hand setting, and the signature. Motor waveform, RTC and UART-driver source are unchanged.
- ESP R13 application source is unchanged. Its existing release BIN is hash-verified; no new ESP build, radio, browser or DST test pass is claimed for this maintenance update.
- The source manifest normalizes CRLF to LF. Asset checksums separately identify exact download bytes.
- The source programming project names RC6BE, has no bound probe serial, and disables automatic flashing when entering Debug. The end-user project retains the simple `Install-MM32` name and selects the bundled firmware.
- No hardware was flashed or reset as part of publication.

## Checks

The current entry point is `tests/mm32/check_rc6be_session_sleep.py`. Publication results comprise 8 session checks, 4 deferred-promotion checks, 12 deadline checks, 5 handover checks, 56 inherited general checks and 8 motor checks (93 total). These use the actual RC6BE binary with modeled peripherals, not physical motor or radio simulation. Local run summaries are retained outside Git; these are not CI hardware results.

The ZIP is checked for readable contents, valid project XML and exact embedded firmware hashes. Repository checks verify Markdown links, firmware source identities, the generated webpage, expected build signature, timer-owned handover and accidental private/binary files. The CI workflow runs these dependency-free checks; it does not invoke a licensed Arm compiler or contact a clock.

For historical context, v1.5's ESP R13 adapters/browser checks covered 18,809 settings/HTTP/protocol/calendar cases, all 1,440 daily time choices and 116 focused DST assertions. Those remain historical results, not new v1.5.1 runs. The ESP-to-MM32 test fixture now points to the current RC6BE image for future runs.

## Physical limits and known investigation

Live RC6BE observations showed retained time surviving hand setting, successful early Wi-Fi-session completion and the ordinary M.SET access window expiring without waiting for the hands. Neither this observation nor compiled tests establish physical smoothness or endurance. Night parking, 06:00 release, a live DST transition and a completed 24–48h run on RC6BE are not claimed here.

The earlier unexpected fresh startup during RC6BC's daily-wake period remains unexplained. Its original reset flags lacked a software/watchdog indication, but historical power/pin flags could not establish the latest cause. RC6BE fixes a separately reproduced session deadlock and is not presented as a cure for that restart. No reset-recorder experiment is included in this release.
