# Background and provenance

This is replacement firmware for existing hardware designed by someone else. Work included identifying chips and programming access, tracing/establishing usable pin functions, observing the original UART exchange, determining reference-sensor behavior and creating a new MM32 movement application matched to an ESP setup/time client. There was no supplied board schematic or starting MM32 application source.

## Related repositories

- [Original CH899 ESP project](https://github.com/maddenste/Chouchin-CH899-Firmware): public board photographs, original ESP/MM32 protocol observations and earlier ESP-only replacement. Template snapshot: `9aa2c7d3bc06c3d28d500d1421581137060c2402`.
- [HC32L130 + TXW813 project](https://github.com/maddenste/Chouchin-899-latest-revision): repository layout, user-facing guide structure and the webpage appearance. Template snapshot: `9d6c631436215fd98c14e87fc4071e04ada2ca69`.

Those projects document different firmware generations/boards. Their instructions are background, not authority for current baud rate, buttons, AP behavior, daily-time granularity, error codes or flashing this matched pair. No HC32/TXW813 firmware or proprietary SDK/tool was copied into this tree.

## What changed during development

The seconds drive moved to autonomous alternating hardware PWM with a hardware pulse counter/DMA output stop. Ordinary holds were changed to preserve the waveform rather than rebuild it. Movement and battery-saver changes use safe full restart/rehome instead of complicated live transitions. Save gained an exact TIME echo before an ESP shutdown request. Time correction gained immutable/deferred records, an upcoming-DST flag and received-phase aging. ESP NTP retains fractional seconds and sends at whole-second boundaries.

Intermittent lumpy motion led to many tests. Some software models passed while physical motion still varied. RC6BB isolates warm release to a single timer-owned safe phase; initial observations improved, but that is not a proven general cure or completed endurance result. Failed experiments are not shipped as installation choices.

## Evidence boundaries

The pin map and behavior here describe the inspected board and current source. A chip data sheet establishes a possible capability, not a routed PCB connection. No direct RTC CLKOUT wire is required or assumed. Coarse SWD samples cannot substitute for an oscilloscope, and clean fault counters cannot establish visual smoothness.

The public photos are the existing metadata-stripped project copies. Private original images, flash backups, UART captures, network details and per-device state are deliberately excluded.
