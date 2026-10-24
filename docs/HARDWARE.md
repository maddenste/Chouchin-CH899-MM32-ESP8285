# Is your clock compatible?

CH899 clocks can look identical outside but have different electronics inside. Open the movement cover and compare your board with the photos below before installing.

**This upgrade is for the MM32 board.** That name comes from the chip which controls the hands. To identify it, check these two markings:

- **MM32SPIN05PF** on the large square chip — this controls the hands.
- **ESP-01F** on the Wi-Fi module — this module contains the ESP8285 Wi-Fi chip.

## Movement controller

Look for **MM32SPIN05PF** on the large square chip:

<img src="photos/05-mm32spin-controller-and-crystal.jpg" alt="Close-up showing the MM32SPIN05PF chip marking" width="650">

## Wi-Fi module

Look for the **ESP-01F** module used with the ESP8285:

<img src="photos/03-esp01f-module-and-uart-header.jpg" alt="ESP-01F Wi-Fi module on the compatible board" width="650">

**Found a different board?** If the large chip says **HC32L130J8TA** and the Wi-Fi module says **TXW813-320**, you have the **HC32 board**. Use [WiFi Clock v2.0 for that board](https://github.com/maddenste/Chouchin-899-latest-revision) instead.

If neither description matches, [ask for help](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues) before installing. The two board types need different firmware.

**Board matches? [Continue with installation →](GETTING_STARTED.md#2-download-and-prepare)**

## Programming access

### MM32 pads

The group is labelled **GND, VDD, DIO, CLK, RESET**. Read the lettering on your board rather than assuming a left-to-right order. The [MM32 guide](MM32.md) explains which connections to make.

<img src="photos/08-mm32-swd-header.jpg" alt="MM32 programming pad labels" width="650">

### ESP pads

The ESP group exposes **IO0, RX, TX, V, G**. Follow the [ESP guide](FLASHING.md), including the separate MM32 reset connection.

<img src="photos/07-esp-programming-header.jpg" alt="ESP programming pad labels" width="650">

Programming needs access to these pads, but normal operation needs no added components or wires. Use only the specified 3.3 V supply and signals.

[Installation overview](GETTING_STARTED.md) · [Internal pin map and circuit notes for developers](development/ARCHITECTURE.md#internal-pin-map)
