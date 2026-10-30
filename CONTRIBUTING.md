# Help improve the project

You do not need to write code to help. Clear reports of what the clock does on real hardware are useful.

## Report a problem

Start with [troubleshooting](docs/TROUBLESHOOTING.md). If the problem remains, open an issue and describe what you changed, what you expected and what happened. Include the firmware versions or filenames if known, the movement/battery-saver settings and the LED indication.

Do not include passwords, device backups or private captures.

## Improve the instructions

If a step is confusing or does not match what you see, point to that step and explain the difference. Check that your board is MM32/ESP8285, not HC32/TXW813.

## Source changes

Use [the developer guide](docs/development/README.md) for builds, tests, internal hardware mapping and the protocol. Keep changes focused and retain license notices.

Do not bundle vendor tools, SDKs, stock firmware or per-device data. Keep building, testing and flashing separate. Motor changes must preserve safe coil release and the memory/stack limits; model tests do not establish physical smoothness.

Documentation changes should use the settings page's visible labels and explain user actions first. Do not claim a release qualification that has not occurred.

The maintainer will be working overseas for roughly three months from late October 2026, so replies and updates may be delayed. Please still report problems; include enough detail for later investigation.
