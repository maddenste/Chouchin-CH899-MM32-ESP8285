# Chouchin CH899 · WiFi Clock v1.5

Replacement firmware for the **MM32SPIN05PF + ESP8285** Chouchin CH899 clock movement: Wi-Fi time synchronisation, configurable hand movement and a local settings page.

<img src="docs/photos/06-full-pcb-component-side.jpg" alt="MM32SPIN05PF and ESP8285 Chouchin board" width="650">

**Pre-release project.** The current pair is **MM32 RC6BB + ESP v1.5 R12**. Source builds and software checks have passed, but overnight operation and sustained smooth seconds-hand movement are still being qualified. There is no stable firmware download yet. Do not interpret this repository's availability as a completed release.

## Check your board first

This project is for **MM32SPIN05PF + ESP8285 / ESP-01F** hardware, with a PCF8563 RTC. Check [the chip photographs](docs/HARDWARE.md); the CH899 name alone is not sufficient.

For **HC32L130J8TA + TXW813-320**, use [the separate HC32 project](https://github.com/maddenste/Chouchin-899-latest-revision). Its firmware, programming tools and pin assignments are not interchangeable with these.

This replaces firmware on **both chips**. The [original ESP-only project](https://github.com/maddenste/Chouchin-CH899-Firmware) retained the stock MM32 firmware; this project does not.

## Related projects

- **[MM32 + ESP8285 — WiFi Clock v1.5](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285):** replacement firmware for both the MM32 movement controller and ESP8285 Wi-Fi chip, with selectable movement and battery-saving modes. Currently pre-release.
- **[HC32L130 + TXW813 — WiFi Clock v2.0](https://github.com/maddenste/Chouchin-899-latest-revision):** the separate project for the newer HC32L130J8TA / TXW813-320 board.
- **[Original ESP8285-only project](https://github.com/maddenste/Chouchin-CH899-Firmware):** replaces only the ESP8285 Wi-Fi application on the older board, retaining the original MM32 movement firmware.

Check both chip markings before choosing a project. Firmware and flashing tools are not interchangeable between board revisions; install a matched pair where both controllers are replaced.

## Make it your clock

- Local Wi-Fi setup, NTP time synchronisation and configurable time zones/DST.
- Daily update at any hour and minute, plus a temporary wake before a DST change.
- Continuous or Hold&Start seconds, with gradual or jumping minute movement.
- Second-hand battery saver: Off, Night parking (00:00–06:00), or On (always parked).
- Save confirmation between the ESP and MM32 before the ESP session ends.
- No hardware modifications and no cloud account required.

**Changing the movement style or second hand battery saver restarts the clock and rehomes the hands after saving.**

<img src="docs/screenshots/setup-desktop.png" alt="WiFi Clock v1.5 settings page with synthetic test data" width="700">

## Start here

- [Equipment and installation overview](docs/GETTING_STARTED.md)
- [MM32 programming](docs/MM32.md) · [ESP programming](docs/FLASHING.md)
- [Setup and everyday use](docs/USER_GUIDE.md)
- [LEDs, error codes and troubleshooting](docs/TROUBLESHOOTING.md)
- [Candidate identity and qualification status](docs/RELEASE_IDENTITY.md)
- [Build from source](docs/BUILD.md) · [Testing](docs/TESTING.md)
- [Hardware and architecture](docs/ARCHITECTURE.md) · [UART protocol](docs/PROTOCOL.md)
- [Research and project background](docs/BACKGROUND.md)
- [Candidate history](docs/HISTORY.md)

Development and programming were carried out on Windows. Other host systems have not been qualified. Vendor firmware dumps, credentials, per-device flash contents and programming-tool executables are not included.

Unofficial project · WiFi Clock v1.5 — Modified by Steve Madden · 2026.

Project-authored material: GPL-3.0-or-later. See [NOTICE.md](NOTICE.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
