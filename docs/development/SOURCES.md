# Source provenance and investigation notes

This project replaces applications on owner-supplied hardware. No board schematic or original MM32 application source was supplied. Component markings, programming access, UART records and optical-reference behavior were established through inspection and testing.

## Related project snapshots

- [Original ESP-only project](https://github.com/maddenste/Chouchin-CH899-Firmware): public photographs, original protocol observations and earlier ESP application. Template snapshot `9aa2c7d3bc06c3d28d500d1421581137060c2402`.
- [HC32/TXW813 project](https://github.com/maddenste/Chouchin-899-latest-revision): documentation structure and settings-page design. Template snapshot `9d6c631436215fd98c14e87fc4071e04ada2ca69`.

These snapshots establish provenance, not current instructions. The boards and firmware generations differ. Check current source for baud rate, buttons, daily-time granularity, AP behavior, faults and flashing requirements. No HC32/TXW813 firmware or proprietary SDK/tool is copied into this tree.

## Development findings

Runtime seconds drive uses alternating hardware PWM, a hardware pulse counter and DMA output stop. Ordinary holds preserve the waveform. Movement/saver changes request a safe full restart rather than a live reconfiguration. Save uses an exact TIME echo before an ESP shutdown request. Corrections retain immutable in-flight and deferred-latest records. ESP R12 retains fractional NTP time and sends at whole-second boundaries.

RC6BB makes the timer interrupt the sole owner of warm release. Initial observations improved, but that does not establish a general root cause or complete the endurance test. Software models passed some earlier cases in which physical movement still varied.

A data sheet establishes possible chip capability, not a routed PCB connection. No direct RTC CLKOUT wire is required or assumed. SWD samples do not establish analogue coil drive or rotor behavior.

Public photos are existing metadata-stripped copies. Personal originals, credentials, per-device backups and private captures remain outside the repository. See [NOTICE](../../NOTICE.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md).
