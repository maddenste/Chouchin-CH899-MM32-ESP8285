# Identify the hardware

The firmware targets the tested **MindMotion MM32SPIN05PF, ESP8285N08 / ESP-01F and PCF8563** CH899 board. The MM32 photograph clearly shows the MM32SPIN05PF package marking. This is evidence for this board, not a compatibility claim for every CH899 movement.

<img src="photos/05-mm32spin-controller-and-crystal.jpg" alt="MM32SPIN05PF marking" width="650">

<img src="photos/03-esp01f-module-and-uart-header.jpg" alt="ESP-01F module and programming area" width="650">

<img src="photos/04-pcf8563-rtc.jpg" alt="PCF8563 RTC" width="500">

## Programming access

The MM32 pad group is labeled **GND, VDD, DIO, CLK, RESET**; inspect the board lettering rather than assuming a left-to-right order. DIO is SWDIO and CLK is SWCLK. RESET is the MM32 reset, not the ESP reset.

<img src="photos/08-mm32-swd-header.jpg" alt="MM32 programming pad labels" width="650">

The ESP programming group exposes **IO0, RX, TX, V, G**. IO0 is sampled at ESP reset/power-on. G is ground; do not use V as a 5 V input.

<img src="photos/07-esp-programming-header.jpg" alt="ESP programming pads" width="650">

## Internal ownership

| Function | MM32 pins / peripheral used by this source |
| --- | --- |
| Seconds coil outputs | PA7 / PB0, alternating TIM3 PWM |
| Minute coil outputs | PB1 / PB2, timed runtime pulses |
| RTC I²C | PB8 SCL / PB9 SDA |
| REC / M.SET inputs | PB10 / PB11, active low |
| LED outputs | PA15 / PB3, active low |
| ESP application UART | UART2, 38400 baud 8N1 |

These internal mappings are for source review, not instructions to wire a new board. The existing optical-reference circuitry and ESP wake control are used unchanged. Pin sharing and initialization order matter.

The RTC's CLKOUT is **not required to be wired to the MM32**. Rate calibration is read over the existing I²C connection; no added quartz wire or hardware modification is needed. Do not assume that a nearby crystal visibly belongs to the MCU or that a trace has been mapped merely because a component is present.

See [architecture](ARCHITECTURE.md) for the timebases and [background](BACKGROUND.md) for evidence/provenance.
