# How the clock works

For firmware developers. For normal operation, see [the user guide](../USER_GUIDE.md).

## Two independent applications

The **ESP8285** provides Wi-Fi, the setup page, NTP and local timezone/DST conversion. The **MM32** controls motors, optical-reference acquisition, buttons, LEDs, the PCF8563 RTC and ESP wake sessions. They exchange framed ASCII records over UART. Neither application is the stock manufacturer's application.

The **PCF8563** retains calendar time and provides a quartz-derived calibration reference read through I²C. The MM32 runs from its own internal clock; reading I²C does not directly produce motor pulses. The MM32 also retains a software civil-time phase from received TIME messages.

## Motor ownership

| Resource | Responsibility |
| --- | --- |
| TIM3 | Continuously running, center-aligned, alternating seconds PWM |
| TIM1 | Count delivered PWM pulse midpoints |
| DMA channel 2 | Disable seconds outputs after the target pulse count |
| TIM14 | Minute pulse starts/falls in runtime |
| TIM2 | Free-running counter for clock-rate measurement, not motor outputs |
| SysTick / PendSV | 128 Hz software clock, buttons and supervisory work |

TIM1 deliberately receives TIM3 events. This is an intentional hardware connection, not two timers accidentally competing for a pin. The motor handlers serialize at equal priority; UART can preempt them. Fault shutdown remains higher priority than visual continuity.

Runtime seconds movement uses hardware PWM in all four movement combinations. Stop2Go has a retained initial 32-pulse ramp and then a latched period/width. An ordinary `00` hold disables outputs without rebuilding the waveform timer. Overnight and ordinary correction holds preserve the same running waveform where the state permits; a deliberate full restart/rehome creates a new motor session.

**RC6BB change:** only TIM3 CC4 commits a warm release. It accepts an up-counting compare slot within 128 timer counts of the scheduled point, inside the original safe released gap. Request and polling paths cannot independently open outputs. A late interrupt defers release rather than emitting a shortened pulse. An unpowered minute request is retained until that handover finishes; powered pulse falls are not delayed. Speed, width and ramp mathematics are unchanged from RC6BA.

**RC6BC change:** an unpowered minute rise no longer defers the software tick; runtime checks enforce actual pending-tick/late-compare deadlines. Delayed minute starts receive their full powered width. Powered-fall protection remains and first-fault reasons distinguish scheduler failures. The source cleanup does not change the RC6BC HEX.

These changes remove specific scheduling weaknesses. It is **not proof that timer contention caused the reported lumpiness**. Coarse read-only output captures found nominal pulses during both smooth and lumpy observations; they could not measure analogue drive or rotor behavior. Physical endurance testing remains necessary.

## RTC discipline and corrections

The MM32 can use the RTC's unused non-interrupting countdown timer as a short-window rate reference. If that reference is unavailable or repeatedly unusable, calendar-based calibration remains available. The countdown is not a stopwatch stream capable of directly clocking each PWM edge. No RTC CLKOUT wiring is required.

ESP R13 retains fractional NTP time, accounts approximately for network processing/round trip, and starts TIME near a whole-second edge. MM32 captures receipt phase and ages pending records through waits. An exact TIME echo confirms record acceptance, not measured hand accuracy.

Large ordinary corrections, small corrections and future DST records have distinct admission paths. Pending records do not overwrite the immutable correction already being applied. Save-triggered movement/battery-saver changes request a safe full restart, rather than live timer reconfiguration.

## Memory limits

RC6BE flash usage and binary identity are recorded in [RELEASE_IDENTITY.md](RELEASE_IDENTITY.md). Static allocation including fixed diagnostics is **2,944 bytes**; a separate **1,152-byte stack** occupies the remainder of 4 KiB SRAM. There is no spare ordinary static-data allocation. The build's conservative stack accounting allows 1,008 bytes including an extra fault path and enforces a further 128-byte guard. These are linker/model checks, not measured maximum runtime stack usage.

Reserved SRAM diagnostic words also hold functional state. They are not safe to clear wholesale while running. Register/RAM edits copied from old experiments can corrupt the current clock.

## Internal pin map

| Function | Pins / peripheral used by the source |
| --- | --- |
| Seconds coil outputs | PA7 / PB0, alternating TIM3 PWM |
| Minute coil outputs | PB1 / PB2, timed runtime pulses |
| RTC I²C | PB8 SCL / PB9 SDA |
| REC / M.SET inputs | PB10 / PB11, active low |
| LEDs | PA15 / PB3, active low |
| ESP application UART | UART2, 38400 baud 8N1 |

These mappings describe the inspected board and current source, not a wiring plan for a different board. Existing optical-reference circuitry and ESP wake control are retained. Shared pin ownership and initialization order matter. A visible crystal must not be assigned to a particular chip without evidence.

For external programming connections and photographs, use [hardware identification](../HARDWARE.md) and the [MM32](../MM32.md) / [ESP](../FLASHING.md) guides.

## Fault handling

The user-facing [error-code table](../TROUBLESHOOTING.md#error-codes) retains codes 1–10. Code 2 is a legacy/reserved abort indication, not an ordinary REC action. Code 10 covers timer, sampling, DMA, output configuration and ramp guards. No battery-voltage fault is implemented.

For faults 8/9, diagnostic parking around 1:50:30 is permitted only from a qualified running state with trusted coordinates. Unsafe electrical/sensor/timer faults stop without diagnostic movement. Faults override webpage leases and movement continuity.

Error-6 setup recovery may accept a new valid TIME after the clean recovery exchange solely to request reset. It does not restart motor motion directly from a fault. The exact entry/lockout conditions are in `ap_recovery.h` and `uart_transport.h`.
