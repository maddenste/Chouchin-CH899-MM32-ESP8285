# Downloads and release status

**WiFi Clock v1.5 is still being tested. There is no ready-to-install release yet.**

The public repository currently provides source code and documentation. Please wait for a tested release before upgrading a clock for everyday use. The remaining work includes overnight operation, daily time updates and consistently even seconds-hand movement.

## When a release is available

The [Releases page](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases) will provide the files to install together:

- **MM32 HEX** — firmware for the movement controller.
- **ESP BIN** — firmware for Wi-Fi and the settings page.
- The matching programming project/instructions and checksum list.

Use files from the same release. Do not mix these with the original ESP-only project or the HC32/TXW813 version.

Start with [board identification](HARDWARE.md), then [the installation overview](GETTING_STARTED.md). A released download is intended to be installed without editing or compiling source code.

## Already testing a candidate?

The current candidates are **MM32 RC6BB + ESP v1.5 R12**. Include those identifiers, or the filenames you installed, when asking for help. They are not a stable-release recommendation.

Developers can find exact build filenames, checksums and test evidence in [the technical release record](development/RELEASE_IDENTITY.md).
