# What is new in v1.5?

**WiFi Clock v1.5** is available from [downloads](DOWNLOADS.md).

Compared with the earlier ESP-only project, v1.5 also replaces the movement controller's firmware, allowing:

- **Sweep, Burst and Hold&Start** movement styles.
- **Night parking** for seconds between midnight and 06:00, or all-day parking.
- A **daily update time at any hour and minute**.
- Timezone selection, automatic daylight-saving changes and optional custom rules.
- A local settings page with an optional secondary time server.
- Access through **WiFi-Clock-Setup** whenever the clock's Wi-Fi is awake.

Changing movement style or second-hand battery saving restarts and sets the clock again after saving. The settings page warns you before this happens.

Released **24 October 2026**. For exact build identifiers and technical changes, see [the developer release notes](development/RELEASE_IDENTITY.md).

The [original ESP-only firmware](https://github.com/maddenste/Chouchin-CH899-Firmware) remains a separate option that retains the manufacturer's MM32 software. The [HC32/TXW813 version](https://github.com/maddenste/Chouchin-899-latest-revision) is for different hardware.
