# Developer documentation

These pages are for changing, building or investigating the firmware. **They are not needed for normal use of an installed clock.**

For installation and settings, start with [the user installation guide](../GETTING_STARTED.md) or [everyday use](../USER_GUIDE.md).

## Build and verify

- [Build the MM32 and ESP source](BUILD.md)
- [Supported test commands and remaining release checks](TESTING.md)
- [Current candidate identifiers and binary checksums](RELEASE_IDENTITY.md)
- [Repository preparation and verification results](REPOSITORY_CHECKS.md)

## Understand or change the firmware

- [Architecture, internal pin map and fault handling](ARCHITECTURE.md)
- [MM32 ↔ ESP protocol, including Save confirmation and SLEEP](PROTOCOL.md)
- [Source provenance and investigation notes](SOURCES.md)

The source is under `firmware/mm32` and `firmware/esp`. Test dependencies are kept separate under `tests` and `firmware/esp/tests`. The old names of inherited test fixtures do not identify extra firmware that users should install.

Keep documentation and software tests separate from physical qualification. Clean diagnostics do not prove even hand movement. Do not flash, reset or change a connected clock merely to run offline tests.
