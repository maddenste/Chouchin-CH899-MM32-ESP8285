# Publication-tree checks — 24 October 2026

This file concerns repository preparation, not overnight hardware qualification.

- Firmware source was copied from the exact RC6BB and ESP R12 candidate packages. Production C/Arduino/HTML content was not intentionally changed.
- Build scripts and the MM32 programming project were retained, with the personal probe selection/serial removed from public project options. Select your own CMSIS-DAP probe before programming. Device packs, flash algorithms, compilers and other executable tools are not included.
- The inherited MM32 fixture dependency chain is supplied for the selected RC6BB entry point. ESP integration-test paths were adapted to the repository and bind to RC6BB, not an absent old candidate.
- `source-manifest.sha256` records candidate firmware source with CRLF normalized to LF, so normal Git checkout newline conversion does not cause a false identity failure. It is not a binary release checksum manifest.
- Board photographs are existing public copies (no GPS EXIF tags found); UI screenshots contain synthetic data. The API test stub uses a synthetic locally administered MAC, not the owner's device MAC.
- Stable binary downloads, a GitHub firmware release and a completed endurance claim are intentionally absent.

## Verified from this tree

- Dependency-free source manifest, generated webpage, single-owner warm-release and local document/image-link checks passed.
- All 69 selected MM32 compiled-code checks passed from this tree: focused 5 (23.218 s), motor 8 (158.369 s), first regression half 28 (200.023 s), second half 28 (153.838 s). Test classes retained older fixture names but used this tree's actual RC6BB AXF/signature.
- MM32 rebuild: exact RC6BB HEX hash, 31,500 bytes flash; 888-byte conservative ordinary stack bound, 1,008 bytes including an extra fault path, within the 1,152-byte reservation/128-byte guard.
- ESP rebuild: exact original R12 BIN hash and 375,776-byte image; Arduino core 3.1.2, 32,544 bytes static RAM and 60,223 / 65,536 bytes IRAM/cache accounting.
- ESP fixtures: 18,809 compiled settings/HTTP/protocol/calendar cases plus retained network/session/UART checks passed, including all 1,440 daily-update choices, fractional NTP, whole-second send, and two exact-echo/confirmed-SLEEP exchanges against actual RC6BB.
- Focused DST suite: 116 assertions, including seven compiled ESP→RC6BB boundary applications, passed.
- Mocked browser checks passed for desktop/mobile, 40 locations, movement/saver controls, native any-minute time picker, optional secondary NTP, password retention and settings reset. These are browser fixtures, not physical networking tests.
- The maintainer confirmed the ESP flashing wiring: MM32 RESET stays grounded throughout; ESP IO0 is low for bootloader entry and can then be released.

Physical release gates remain in [TESTING.md](TESTING.md). No clock was accessed, reset or flashed while preparing this repository, and the existing overnight monitoring task was not modified.
