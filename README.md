# Chouchin-CH899 · WiFi Clock v1.5

Give your clock Wi-Fi time updates, a choice of hand movements and a simple settings page on your phone.

- **Sweep, Burst or Hold&Start** — including the station-clock pause at 12.
- **Battery saving** — park the seconds hand overnight or all day.
- **Automatic timekeeping** — choose your timezone, daylight saving and daily update time.

<img src="docs/screenshots/setup-desktop.png" alt="WiFi Clock v1.5 settings page" width="700">

## Will it work with my clock?

There are different circuit boards inside CH899 clocks. This upgrade is for the **MM32 board**. [Compare your board with these photos](docs/HARDWARE.md) before installing; the clock's appearance alone is not enough to identify it.

## Install

**[Download WiFi Clock v1.5](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/WiFi-Clock-v1.5.zip)** · **[Follow the installation guide →](docs/GETTING_STARTED.md)**

The guide covers the equipment, programming both chips and connecting to Wi-Fi. Installation requires opening the clock and connecting a programmer; no compiling or board modifications are needed.

> [!WARNING]
> **Install at your own risk.** The factory movement firmware is read-protected: it cannot be backed up or recovered from the chip after replacement. This replacement was built from scratch.
>
> Testing is ongoing. Please [report any bugs](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues).

[Settings and everyday use](docs/USER_GUIDE.md) · [Help](docs/TROUBLESHOOTING.md) · [Release notes](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/tag/v1.5)

## Built from scratch

This began with an existing clock board, no circuit diagram and no access to its protected movement firmware. We started by getting the hands to move, then identified the LED and button connections, worked out how the motors find their starting positions, decoded the Wi-Fi module's messages, and discovered how a separate timekeeping chip communicates over I²C.

From those discoveries, we built replacement firmware for both chips. Much of the work went into keeping the seconds hand smooth through pauses, restarts and time corrections. [Read the project background →](docs/BACKGROUND.md)

## Other versions

- **[Have an HC32 board? Use WiFi Clock v2.0](https://github.com/maddenste/Chouchin-899-latest-revision)** — similar movement features for different electronics. Its [board photos](https://github.com/maddenste/Chouchin-899-latest-revision/blob/main/docs/HARDWARE.md#board-photographs) help identify it; v2.0 is not an update for this MM32 board.
- **[Want to keep the factory hand movement? Use the Wi-Fi-only upgrade](https://github.com/maddenste/Chouchin-CH899-Firmware)** — improves setup and internet time synchronisation on the MM32 board, without adding movement styles or seconds-hand parking.

Use the files for your chosen project together; they are not interchangeable.

---

Unofficial project · WiFi Clock v1.5 — Modified by Steve Madden · 2026.

[Background](docs/BACKGROUND.md) · [For developers](docs/development/README.md) · [License and credits](NOTICE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
