# Chouchin-CH899 · WiFi Clock v1.5

**For the older MM32 revision of the Chouchin CH899 clock.** This upgrade replaces both the hand-movement and Wi-Fi firmware, adding movement styles and seconds-hand battery saving.

## Choose your firmware

| Firmware | Your clock (photos) | What it changes |
| --- | --- | --- |
| [**v1.0 — Wi-Fi only**](https://github.com/maddenste/Chouchin-CH899-Firmware) | [Older revision (MM32)](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/blob/main/docs/HARDWARE.md) | Improves Wi-Fi setup; keeps the factory hand movement |
| [**v1.5 — full upgrade**](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285) | [Older revision (MM32)](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/blob/main/docs/HARDWARE.md) | Adds movement styles and seconds-hand parking; replaces movement and Wi-Fi software |
| [**v2.0 — full upgrade**](https://github.com/maddenste/Chouchin-899-latest-revision) | [Newer revision (HC32)](https://github.com/maddenste/Chouchin-899-latest-revision/blob/main/docs/HARDWARE.md#board-photographs) | Adds movement styles and seconds-hand parking; replaces movement and Wi-Fi software |

Choose by the board inside your clock, not by the highest version number. Follow that project's installation guide and use its files together.

![Chouchin-CH899 WiFi Clock v1.5 — MM32 and ESP8285](docs/assets/wifi-clock-v1.5-banner.png)

## Check your clock

Compare the circuit board inside your clock with this photo. The casing alone does not identify the revision. [See close-ups and identification help →](docs/HARDWARE.md)

<img src="docs/photos/06-full-pcb-component-side.jpg" alt="The older MM32 clock board supported by WiFi Clock v1.5" width="450">

## Make it your clock

- **Sweep, Burst or Hold&Start** — including the station-clock pause at 12.
- **Battery saving** — park the seconds hand overnight or all day.
- **Automatic timekeeping** — choose your timezone, summer/winter time changes and daily update time.

<details>
<summary>See the settings page</summary>

<img src="docs/screenshots/setup-desktop.png" alt="WiFi Clock v1.5 settings page" width="700">

</details>

## Install

**[Download WiFi Clock v1.5](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/WiFi-Clock-v1.5.zip)** · **[Follow the installation guide →](docs/GETTING_STARTED.md)**

The guide covers the equipment, programming both chips and connecting to Wi-Fi. You will need to open the clock and connect programming equipment. No compiling or board modifications are needed.

> [!WARNING]
> **Install at your own risk.** The factory movement firmware is read-protected: it cannot be backed up or recovered from the chip after replacement.
>
> Testing is ongoing. Please [report any bugs](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues).

[Settings and everyday use](docs/USER_GUIDE.md) · [Help](docs/TROUBLESHOOTING.md) · [Release notes](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/tag/v1.5)

## Built from scratch

We began with an undocumented board and protected factory software. Starting with getting the hands to move, we identified the LED and button connections, worked out how the hands find their starting positions, decoded the Wi-Fi messages and investigated the separate timekeeping chip. From that came replacement firmware for both chips, with much of the work devoted to smooth seconds-hand movement. [The project background →](docs/BACKGROUND.md)

---

Unofficial project · WiFi Clock v1.5 — Modified by Steve Madden · 2026.

[For developers](docs/development/README.md) · [License and credits](NOTICE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
