# Third-party notices

Original project code is GPL-3.0-or-later; third-party components retain their own terms.

## ESP build dependencies

The candidate uses **ESP8266 Arduino Core 3.1.2**. Obtain its sources and notices from the [official tagged tree](https://github.com/esp8266/Arduino/tree/3.1.2) and [license](https://github.com/esp8266/Arduino/blob/3.1.2/LICENSE). The core is LGPL-2.1-or-later and bundles components with other terms, including Espressif NONOS SDK and BearSSL. Preserve the applicable upstream notices when distributing a combined binary; this repository's GPL text does not replace them.

Arduino CLI, esptool, the core/toolchain, Arm Compiler, Keil MDK, the MindMotion device pack and its programming algorithm must be obtained separately. They are not included or relicensed by this project. Their installation and use are subject to their respective terms.

## Test-only dependencies

Unicorn, pyelftools, tzdata and Playwright are optional development/test dependencies, not code running on the clock. Install them separately under their upstream licenses. Test stubs do not emulate ESP radio hardware or a physical motor.

## Related project material

Public photographs and documentation structure are drawn from Steve Madden's related GPL-3.0-or-later Chouchin projects, linked in [NOTICE.md](NOTICE.md). The HC32 project's vendor-derived binaries, SDK integration overlays and proprietary tools are not copied into this repository.
