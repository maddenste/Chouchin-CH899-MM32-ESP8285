# Source provenance and investigation notes

This project replaces applications on owner-supplied hardware. No board schematic or original MM32 application source was supplied. Component markings, programming access, UART records and optical-reference behavior were established through inspection and testing.

## Related project snapshots

- [Original ESP-only project](https://github.com/maddenste/Chouchin-CH899-Firmware): public photographs, original protocol observations and earlier ESP application. Template snapshot `9aa2c7d3bc06c3d28d500d1421581137060c2402`.
- [HC32/TXW813 project](https://github.com/maddenste/Chouchin-899-latest-revision): documentation structure and settings-page design. Template snapshot `9d6c631436215fd98c14e87fc4071e04ada2ca69`.

These snapshots establish provenance, not current instructions. The boards and firmware generations differ. Check current source for baud rate, buttons, daily-time granularity, AP behavior, faults and flashing requirements. No HC32/TXW813 firmware or proprietary SDK/tool is copied into this tree.

## Development findings

Runtime seconds drive uses alternating hardware PWM, a hardware pulse counter and DMA output stop. Ordinary holds preserve the waveform. Movement/saver changes request a safe full restart rather than a live reconfiguration. Save uses an exact TIME echo before an ESP shutdown request. Corrections retain immutable in-flight and deferred-latest records. ESP R13 retains fractional NTP time and sends at whole-second boundaries.

RC6BB makes the timer interrupt the sole owner of warm release. Initial observations improved, but that does not establish a general root cause or complete the endurance test. Software models passed some earlier cases in which physical movement still varied.

A data sheet establishes possible chip capability, not a routed PCB connection. No direct RTC CLKOUT wire is required or assumed. SWD samples do not establish analogue coil drive or rotor behavior.

Public photos are existing metadata-stripped copies. Personal originals, credentials, per-device backups and private captures remain outside the repository. See [NOTICE](../../NOTICE.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md).

RC6BC adds deadline-aware minute scheduling and full powered widths for delayed minute rises. R13 updates the MM32 project link and aligns webpage input limits with the existing backend. Details and evidence are in [the release record](RELEASE_IDENTITY.md).

RC6BE (v1.5.1) changes only deferred-time/session ownership and completion, plus its build identity. Motor, RTC and UART-driver implementations and ESP R13 application source remain unchanged from v1.5. See [the release record](RELEASE_IDENTITY.md).

RC6BG (v1.5.2) retains the three-second scheduled ESP wake delay from the RC6BF investigation and removes its temporary reset recorder and cookies. It makes no motor timing or ESP application changes.

## Seconds output-drive evidence

RC6BI follows the exact MM32SPIN05PF TIM3 PWM example in [MindMotion's LibSamples_MM32SPIN0x_q V1.16](https://www.mindmotion.com.cn/uploadfiles/2026/08/LibSamples_MM32SPIN0x_q_V1.16.zip), linked from the [product page](https://www.mindmotion.com.cn/products/mm32mcu/mm32_other_product/mm32_other_MCU/mm32spin05/). The example selects alternate-function push-pull with GPIO_Speed_50MHz. In the actual HAL initializer this is nibble 0xB (MODE 11). Offline execution of the vendor function confirmed the encoding on PA7 and PB0 without changing other pins.

The [Chinese F datasheet v1.25](https://www.mindmotion.com.cn/uploadfiles/2026/01/DS_MM32SPIN05x_version_F_SC.pdf) specifies stronger loaded output limits for MODE 11 than MODE 01. The [reference manual](https://www.mindmotion.com.cn/uploadfiles/2024/11/UM_MM32SPIN05x_q_SC.pdf) still marks 10/11 reserved, while direct-register macro labels also disagree with the HAL. These contradictions remain; no formal vendor clarification is claimed. The exact-part example, HAL implementation and datasheet support the selected setting. It changes output drive, not the supply voltage or motor frequency; 50 MHz is the GPIO configuration label.

After RC6BH's rate compensation alone did not cure a warm/lumpy observation, RC6BI changed only the runtime seconds drive. The owner then reported sustained smooth movement through the overnight run. This supports drive margin as a working explanation, not a measured electrical or thermal root cause. No analogue coil-current/output-voltage measurement or full temperature qualification has been performed. Vendor SDKs and proprietary tools are not redistributed.
