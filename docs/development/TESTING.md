# Testing and evidence limits

For developers and release qualification. For ordinary clock checks, see [troubleshooting](../TROUBLESHOOTING.md).

## Repository checks

Run `python tools/verify_repository.py` from a clean checkout. It verifies local Markdown file links, the candidate's source manifest, required documents and known candidate identifiers, and rejects compiled firmware/private-data directories accidentally staged in Git. The CI workflow runs only these host-side checks; it does not claim to build with a licensed Arm compiler or connect to a clock.

## MM32 compiled-code regressions

After the MM32 build, use Python 3.12 and `pip install -r tests/requirements.txt`. Run these **selected entry-point suites**, not broad `unittest discover`:

```text
python tests/mm32/check_rc6bg_clean_wake.py
python tests/mm32/check_rc6bg_clean_wake.py --session
python tests/mm32/check_rc6bg_clean_wake.py --pending
python tests/mm32/check_rc6bg_clean_wake.py --deadline
python tests/mm32/check_rc6bg_clean_wake.py --handover
python tests/mm32/check_rc6bg_clean_wake.py --regression --part=1
python tests/mm32/check_rc6bg_clean_wake.py --regression --part=2
python tests/mm32/check_rc6bg_clean_wake.py --motor
```

These commands select the actual **RC6BG AXF/signature**, including inherited regression fixtures. Historic module names describe model evolution; their standalone entry points may require old artifacts and are not the commands for the current release.

The added session checks cover deferred time during homing/catch-up, early Wi-Fi completion, retained time aging, M.SET/web access, stale records, counter wrap and correction/REC/CLEAN ownership. The inherited checks cover timer handover, minute deadlines, movement, parking, time corrections and protocol handling. They execute compiled Cortex-M0 instructions with modeled peripherals, not motor mechanics or ESP radio.

## ESP tests

The `firmware/esp/tests` fixtures compile application code against Arduino stubs. `Build-Checks.ps1` accepts compiler, Python and Node-module paths; install the same Python requirements first. Build MM32 too: producer/parser integration uses the current RC6BG image. The mocked browser tests need Playwright and an Edge installation at the fixture's documented Windows path. No real clock is contacted by these tests.

Example from the repository root (replace tool paths with your installations):

```powershell
& ./firmware/esp/tests/Build-Checks.ps1 -Compiler 'C:/path/to/ARMCLANG/bin/armclang.exe' -Python 'C:/path/to/python.exe' -NodeModules 'C:/path/to/node_modules' -Workspace (Get-Location).Path
```

The `playwright` package must exist beneath the supplied NodeModules directory. The default tool paths reflect the bench PC; they are not required installation locations. Fixtures and browser result images are generated locally and ignored by Git.

Only a small focused DST transition suite is necessary here; prior broad calendar qualification does not need to be re-run interactively on the clock. Browser screenshots in this repository use synthetic settings.

## Historical physical evidence and outstanding qualification

The owner reports consistently smooth seconds on RC6BC. Main-run daytime snapshots cover 9h15m and 555 additional revolutions without recorded fault/rebuild. A later 75s live capture observed a correct hold/release and six minute pulses; total laps reached 663. One hourly SWD check failed; access returned without a recorded reset. One crystal-reference sample was rejected and recovered without fallback; calendar failure/reject and UART recovery/overflow counters stayed zero.

The following are not claimed as completed on this final pair:

- Sustained physical checks of every movement style, outside debug.
- Night parking and 06:00 release, including power-on during parking.
- Always-parked saver mode and return to movement after a settings restart.
- Daily ESP wake, time correction and continued smooth movement.
- M.SET, REC, CLEAN/settings clear, Save echo/SLEEP and recovery from a failed network session.
- Correct minute-hand position after homing/catch-up and after time changes.
- A 24–48-hour matched-build endurance run without unexpected faults, resets, drift or PWM rebuilds.

Read-only diagnostic counters can establish that faults/rebuilds were not recorded. They cannot prove smooth movement. A PC that sleeps, a disconnected probe or sparse samples leave observation gaps; record them honestly.

See [REPOSITORY_CHECKS.md](REPOSITORY_CHECKS.md) for the checks performed specifically on this publication tree. Overnight qualification remains separate and is not silently promoted to a pass by CI.

## v1.5.1 qualification note

RC6BE was observed on the development board retaining a received time during hand setting, closing Wi-Fi and changing from red to blue without waiting for minute-hand catch-up. A subsequent manual M.SET access window expired normally. This does not establish endurance, visual smoothness or a cure for the earlier unexpected restart. The prior RC6BC daytime results above remain historical evidence, not a completed RC6BE endurance run.

## v1.5.2 qualification note

RC6BG removes the temporary reset recorder and retains the three-second scheduled-wake delay. Its build identity and source scope are in [RELEASE_IDENTITY.md](RELEASE_IDENTITY.md); exact model-check scope, the successful predecessor daily wake and the final-build live baseline are in [REPOSITORY_CHECKS.md](REPOSITORY_CHECKS.md). Earlier physical reports above do not establish a completed endurance run on RC6BG.
