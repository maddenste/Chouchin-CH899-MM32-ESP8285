# Chouchin CH899 · WiFi Clock v1.5

Keep your clock on time over Wi-Fi, choose how its hands move, and change its settings from your phone or computer.

**Still in testing:** a ready-to-install release is not available yet. See [downloads and release status](docs/DOWNLOADS.md).

## What you can change

- **Movement style:** Sweep, Burst or Hold&Start, which pauses the seconds hand at 12 before starting the next minute.
- **Second-hand battery saving:** leave it running, park it overnight from midnight to 06:00, or keep it parked all day. The minute and hour hands keep working.
- **Daily time update:** choose any hour and minute.
- **Timezone and daylight saving:** select your location, with automatic clock changes where supported.
- **Wi-Fi and time servers:** configure them in a local webpage. No cloud account or phone app is needed.

<img src="docs/screenshots/setup-desktop.png" alt="WiFi Clock settings page showing movement, battery saving and daily update controls" width="700">

## Getting started

1. [Check that your board is compatible](docs/HARDWARE.md).
2. [Read the installation guide](docs/GETTING_STARTED.md) before connecting a programmer.
3. [Set up Wi-Fi and choose your preferences](docs/USER_GUIDE.md).

Installation replaces firmware on **both chips** and needs programming equipment and access to the circuit board. No extra components or changes to the board's circuitry are needed.

## Is this the right clock?

This project supports the tested **MM32SPIN05PF + ESP8285 / ESP-01F** board. Check the chip markings: the CH899 name or enclosure alone is not enough.

<img src="docs/photos/06-full-pcb-component-side.jpg" alt="Compatible MM32 and ESP8285 clock board" width="450">

### Other CH899 projects

- **[Original ESP8285-only firmware](https://github.com/maddenste/Chouchin-CH899-Firmware)** keeps the manufacturer's MM32 movement firmware and replaces only the Wi-Fi application. It is a different option for the older board, not the Wi-Fi half of this upgrade.
- **[WiFi Clock v2.0 for HC32L130 + TXW813](https://github.com/maddenste/Chouchin-899-latest-revision)** is for the newer board with those chip markings. Its firmware and programming tools cannot be used on MM32/ESP8285 hardware.

Use the two firmware files supplied together for this project; do not mix files from the three repositories.

## Using your clock

- [Settings, movement styles and buttons](docs/USER_GUIDE.md)
- [LED meanings, error codes and help](docs/TROUBLESHOOTING.md)
- [What is new in v1.5](docs/HISTORY.md)
- [How the project started](docs/BACKGROUND.md)

For a problem, [open an issue](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues) with your firmware versions, settings and a description of what happened. Please do not include Wi-Fi passwords or private device backups.

## For developers

[Source builds, testing, hardware details and the communication protocol](docs/development/README.md) are documented separately. You do not need these to use an installed clock.

Unofficial project · WiFi Clock v1.5 — Modified by Steve Madden · 2026.

GPL-3.0-or-later · [License and attribution](NOTICE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
