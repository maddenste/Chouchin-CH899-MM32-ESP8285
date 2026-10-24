# Testing and remaining release gates

For developers and release qualification. For ordinary clock checks, see [troubleshooting](../TROUBLESHOOTING.md).

## Repository checks

Run `python tools/verify_repository.py` from a clean checkout. It verifies local Markdown file links, the candidate's source manifest, required documents and known candidate identifiers, and rejects compiled firmware/private-data directories accidentally staged in Git. The CI workflow runs only these host-side checks; it does not claim to build with a licensed Arm compiler or connect to a clock.

## MM32 compiled-code regressions

After the MM32 build, use Python 3.12 and `pip install -r tests/requirements.txt`. Run these **selected entry-point suites**, not broad `unittest discover`:

```text
python tests/mm32/check_rc6bb_handover.py --focused
python tests/mm32/check_rc6bb_handover.py --part=1
python tests/mm32/check_rc6bb_handover.py --part=2
python tests/mm32/check_rc6bb_handover.py --motor
```

The entry point rebinds inherited fixtures to the **actual RC6BB AXF/signature**. Historic module names describe model evolution, not extra firmware to install. Their old standalone entry points require old artifacts and are not supported test commands for this repository. No old firmware binaries or captures are shipped.

These 5 + 28 + 28 + 8 checks execute compiled Cortex-M0 instructions with modeled timer/DMA/RTC/UART behavior: fixed-phase handover, late IRQ deferral, queued minute preservation, safe drain, normal waveforms, ramp, overnight/permanent parking, settings restart, correction/mailbox handling, DST, exact echo/SLEEP and fault paths. They do **not** model coil current, gears, rotor dynamics, ESP radio or physical flash.

## ESP tests

The `firmware/esp/tests` fixtures compile application code against Arduino stubs. `Build-Checks.ps1` accepts compiler, Python and Node-module paths; install the same Python requirements first. Build MM32 too: producer/parser integration uses the current RC6BB image. The mocked browser tests need Playwright and an Edge installation at the fixture's documented Windows path. No real clock is contacted by these tests.

Example from the repository root (replace tool paths with your installations):

```powershell
& ./firmware/esp/tests/Build-Checks.ps1 -Compiler 'C:/path/to/ARMCLANG/bin/armclang.exe' -Python 'C:/path/to/python.exe' -NodeModules 'C:/path/to/node_modules' -Workspace (Get-Location).Path
```

The `playwright` package must exist beneath the supplied NodeModules directory. The default tool paths reflect the bench PC; they are not required installation locations. Fixtures and browser result images are generated locally and ignored by Git.

Only a small focused DST transition suite is necessary here; prior broad calendar qualification does not need to be re-run interactively on the clock. Browser screenshots in this repository use synthetic settings.

## Physical release gates

- Sustained smooth seconds in each movement style, outside debug.
- Night parking and 06:00 release, including power-on during parking.
- Always-parked saver mode and return to movement after a settings restart.
- Daily ESP wake, time correction and continued smooth movement.
- M.SET, REC, CLEAN/settings clear, Save echo/SLEEP and recovery from a failed network session.
- Correct minute-hand position after homing/catch-up and after time changes.
- A 24–48-hour matched-build endurance run without unexpected faults, resets, drift or PWM rebuilds.

Read-only diagnostic counters can establish that faults/rebuilds were not recorded. They cannot prove smooth movement. A PC that sleeps, a disconnected probe or sparse samples leave observation gaps; record them honestly.

See [REPOSITORY_CHECKS.md](REPOSITORY_CHECKS.md) for the checks performed specifically on this publication tree. Overnight qualification remains separate and is not silently promoted to a pass by CI.
