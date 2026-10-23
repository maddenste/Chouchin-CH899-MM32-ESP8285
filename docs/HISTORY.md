# Candidate history

## WiFi Clock v1.5 — initial public source tree, 24 October 2026

**Candidate only: MM32 RC6BB + ESP R12. No stable binary release.**

- New source-built MM32 movement application for MM32SPIN05PF hardware, paired with an ESP8285 Wi-Fi/settings application.
- Independent homing, minute catch-up, hardware seconds PWM, optical-reference supervision and safe latched fault indication.
- Four minute/seconds movement combinations; overnight and permanent seconds parking.
- Existing waveform preserved through ordinary holds; safe full restart/rehome for changed movement/saver settings.
- RC6BB makes the timer interrupt the sole owner of warm seconds release in its bounded safe phase.
- Exact accepted TIME echo before Save-triggered SLEEP, retaining pending newer updates during catch-up.
- Any-minute daily update, optional secondary NTP, timezone/custom POSIX and early DST wake handling.
- Fractional NTP retained internally; TIME starts near whole-second boundaries without a new fractional wire field.
- Matching HC32-style settings page, setup AP on every wake, DHCP hostname, no mDNS, refresh grace and local Save confirmation flow.

Initial smooth movement and clean diagnostic observations are encouraging, not a completed endurance qualification. See [the remaining gates](TESTING.md#physical-release-gates).

The older [ESP-only project](https://github.com/maddenste/Chouchin-CH899-Firmware) and [HC32 project](https://github.com/maddenste/Chouchin-899-latest-revision) retain their own histories. This repository does not replace their released artifacts or claim their hardware is interchangeable.
