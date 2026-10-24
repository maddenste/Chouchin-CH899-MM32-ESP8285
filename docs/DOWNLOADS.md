# Firmware downloads

Install **WiFi Clock v1.5** using the matched **MM32 RC6BC + ESP R13** files.

> [!WARNING]
> **Install at your own risk.** The factory MM32 movement firmware is read-protected and cannot be backed up by reading the chip. Once overwritten, it cannot be recovered from the chip. The replacement MM32 firmware was built from scratch. Testing is ongoing; please [report any bugs or unexpected behaviour](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues).

| Download | Use |
| --- | --- |
| [MM32 HEX](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/MM32SPIN05PF_DEADLINE_GUARD_RC6BC_20261024.hex) | Movement controller |
| [ESP BIN](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin) | Wi-Fi/settings application |
| [MM32 programming project ZIP](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/WiFi-Clock-v1.5-MM32-Programmer.zip) | Extract together; contains the matching HEX in its build folder |
| [SHA256SUMS.txt](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/SHA256SUMS.txt) | Check downloaded file identities |

[Release notes and all assets](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/tag/v1.5).

Check [board compatibility](HARDWARE.md), then follow [getting started](GETTING_STARTED.md). No source editing or compiling is required. Use these two firmware files together; firmware for HC32/TXW813 or the original ESP-only project is not interchangeable.

Developers can use the source attached to the release or the tagged repository. Exact build identifiers and hashes are in [the build record](development/RELEASE_IDENTITY.md). [Test evidence](development/TESTING.md) distinguishes completed checks from the uncompleted overnight/DST qualification.
