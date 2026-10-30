# Download WiFi Clock v1.5

**[Download the installation package](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5.3/WiFi-Clock-v1.5.3.zip)**

**Already using an earlier v1.5 release?** Update only the MM32 movement controller using the included project. ESP R13 is unchanged, so you can leave the Wi-Fi chip as it is. [What changed →](HISTORY.md)

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

Check [which board is inside your clock](HARDWARE.md), then follow [the installation guide](GETTING_STARTED.md). This package is for the **MM32 board** and replaces both its movement and Wi-Fi firmware. Use the files from this package together.

Programming tools are installed separately; the guides show what you need. You do not need to edit or compile firmware.

[Release notes and individual downloads](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/tag/v1.5.3) · [Download checksums](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5.3/SHA256SUMS.txt)

Developers can find the original build names, source and binary identities in [the technical release record](development/RELEASE_IDENTITY.md).
