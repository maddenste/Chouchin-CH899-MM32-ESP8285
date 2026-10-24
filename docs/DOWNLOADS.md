# Download WiFi Clock v1.5

**[Download the installation package](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/WiFi-Clock-v1.5.zip)**

Extract the complete ZIP to a folder on your PC. It contains everything needed for both chips:

| File | What it is for |
| --- | --- |
| `START-HERE.txt` | Read this first |
| `Install-MM32.uvprojx` | Open in Keil µVision to program the movement controller |
| `WiFi-Clock-ESP.bin` | Wi-Fi firmware, used in the ESP installation guide |
| `firmware/WiFi-Clock-MM32.hex` | Movement firmware, already selected in the programming project |
| `SHA256SUMS.txt` | Checksums for the two firmware files |

Keep the extracted files together. Do not open the project from inside the ZIP.

> [!WARNING]
> **Install at your own risk.** The factory MM32 movement firmware is read-protected and cannot be read out for a backup. Once overwritten, it cannot be recovered from the chip. This replacement firmware was built from scratch.
>
> Testing is ongoing. Please [report bugs or unexpected behaviour](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues).

## Before installing

Check [your board](HARDWARE.md), then follow [the installation guide](GETTING_STARTED.md). This package is for **MM32SPIN05PF + ESP8285 / ESP-01F**. Firmware for HC32/TXW813 or the original ESP-only project is not interchangeable.

Programming tools are installed separately; the guides show what you need. You do not need to edit or compile firmware.

[Release notes and individual downloads](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/tag/v1.5) · [Download checksums](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/SHA256SUMS.txt)

Developers can find the original build names, source and binary identities in [the technical release record](development/RELEASE_IDENTITY.md).
