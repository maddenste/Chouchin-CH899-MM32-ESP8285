# Chouchin-CH899 · WiFi Clock v1.5

Wi-Fi time synchronisation, configurable hand movement and a simple local settings page.

**Check your board first:** this project is for **MM32SPIN05PF + ESP8285 / ESP-01F** only. For **HC32L130J8TA + TXW813-320**, use [WiFi Clock v2.0](https://github.com/maddenste/Chouchin-899-latest-revision). The firmware is not interchangeable.

<img src="docs/photos/06-full-pcb-component-side.jpg" alt="Compatible Chouchin-CH899 MM32 and ESP8285 board" width="350">

## Have a different CH899 board or want an ESP-only upgrade?

- **[WiFi Clock v2.0 — HC32L130 + TXW813](https://github.com/maddenste/Chouchin-899-latest-revision)** supports the newer board with those chip markings. It uses different firmware and programming tools.
- **[Original ESP8285-only firmware](https://github.com/maddenste/Chouchin-CH899-Firmware)** keeps the manufacturer's MM32 movement firmware and replaces only the Wi-Fi application.

This v1.5 project replaces **both** applications on the tested MM32/ESP8285 board. Do not mix firmware from the three projects.

## Ready to install?

Download **[MM32 RC6BC HEX](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/MM32SPIN05PF_DEADLINE_GUARD_RC6BC_20261024.hex)** for the **movement controller** and **[ESP R13 BIN](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin)** for the **Wi-Fi chip**.

These are the two firmware files needed. Also download the **[MM32 programming project](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/WiFi-Clock-v1.5-MM32-Programmer.zip)** and keep its HEX in the supplied `build` folder.

If you experience a bug or unexpected behaviour, please [let me know through GitHub Issues](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues). Include firmware versions, settings and what happened; for a stopped clock, note hand positions and LED behaviour.

**[Start here: equipment, software and flashing steps →](docs/GETTING_STARTED.md)**

No compiling or firmware editing is required. Install the two prepared files, then enter your Wi-Fi settings. No extra components or board modifications are needed.

**Flashing instructions for both chips:** follow the [MM32 programming guide](docs/MM32.md) and [ESP Wi-Fi flashing guide](docs/FLASHING.md). MM32 uses SWD/µVision; ESP uses a 3.3 V USB-to-serial adapter. These are different procedures.

- [Firmware downloads, release notes and checksums](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/tag/v1.5)
- [Current user guide](docs/USER_GUIDE.md)
- [Help, LED error codes and reporting a problem](docs/TROUBLESHOOTING.md)

The documented procedures were tested on Windows. Other systems may work with suitable tools but have not been verified.

## Make it your clock

- Wi-Fi network, primary NTP server and optional secondary server.
- Daily updates at **any hour and minute**, plus an early wake for DST changes.
- Timezone selection, automatic daylight saving and custom POSIX rules.
- Sweep, Burst or Hold&Start hand movement.
- Second hand battery saver: Off, Night parking from midnight to 06:00, or On.

Hold&Start recreates the characteristic station-clock motion: the seconds hand pauses at 12, then restarts as the minute hand advances.

Changing movement style or second-hand battery saving restarts the clock and rehomes the hands after saving. The page warns you before this happens.

<img src="docs/screenshots/setup-desktop.png" alt="WiFi Clock v1.5 settings page" width="700">

[Research and project background](docs/BACKGROUND.md), [source builds](docs/development/BUILD.md) and [test evidence and remaining limits](docs/development/TESTING.md) are documented separately.

Unofficial project · WiFi Clock v1.5 — Modified by Steve Madden · 2026.

GPL-3.0-or-later · [License and attribution](NOTICE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
