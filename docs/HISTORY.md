# What is new in v1.5?


## v1.5.2 — 29 October 2026

Daily Wi-Fi wake now starts three seconds after the selected minute, keeping it clear of the minute's motor transition. The manual M.SET wake is still immediate. This timing completed a live daily wake without a restart; testing continues.

Includes the earlier fix for Wi-Fi sessions staying active while the hands were setting. Temporary development diagnostics have been removed. Motor waveforms and ESP R13 are unchanged.

**Updating from v1.5 or v1.5.1:** update only the MM32 movement controller. [Download and install](DOWNLOADS.md). This is the only release offered for installation; older versions are retained privately.

## v1.5.1 — 26 October 2026

Fixes a time update getting stuck while the hands were homing or setting, which could leave the red LED flashing and Wi-Fi awake unnecessarily. The received time is kept safely and applied when the hands are ready. The normal M.SET setup window remains available.

Only the MM32 firmware changes (RC6BE). ESP R13 and the motor waveforms are unchanged. An earlier unexpected restart is still under investigation; this update is not claimed to fix it.

## v1.5

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
