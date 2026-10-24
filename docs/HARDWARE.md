# Is your clock compatible?

Check the markings on the circuit board before downloading firmware. **CH899 is used for more than one board type**, and a matching enclosure is not enough.

This project is for the tested board with:

- **MM32SPIN05PF** — the movement controller.
- **ESP8285 / ESP-01F** — the Wi-Fi module.
- **PCF8563** — the clock's timekeeping chip.

## Movement controller

Look for **MM32SPIN05PF** on the large square chip:

<img src="photos/05-mm32spin-controller-and-crystal.jpg" alt="Close-up showing the MM32SPIN05PF chip marking" width="650">

## Wi-Fi module

Look for the **ESP-01F** module used with the ESP8285:

<img src="photos/03-esp01f-module-and-uart-header.jpg" alt="ESP-01F Wi-Fi module on the compatible board" width="650">

The timekeeping chip is marked **PCF8563**:

<img src="photos/04-pcf8563-rtc.jpg" alt="PCF8563 timekeeping chip" width="500">

If your board instead says **HC32L130J8TA + TXW813-320**, use [the newer-board project](https://github.com/maddenste/Chouchin-899-latest-revision). Do not use this project's files on it. If the markings differ or you cannot identify them, stop and ask before flashing.

## Programming access

### MM32 pads

The group is labelled **GND, VDD, DIO, CLK, RESET**. Read the lettering on your board rather than assuming a left-to-right order. The [MM32 guide](MM32.md) explains which connections to make.

<img src="photos/08-mm32-swd-header.jpg" alt="MM32 programming pad labels" width="650">

### ESP pads

The ESP group exposes **IO0, RX, TX, V, G**. Follow the [ESP guide](FLASHING.md), including the separate MM32 reset connection.

<img src="photos/07-esp-programming-header.jpg" alt="ESP programming pad labels" width="650">

Programming needs access to these pads, but normal operation needs no added components or wires. Use only the specified 3.3 V supply and signals.

[Installation overview](GETTING_STARTED.md) · [Internal pin map and circuit notes for developers](development/ARCHITECTURE.md#internal-pin-map)
