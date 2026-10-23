# Start here — MM32 + ESP8285

**Pre-release:** do not start a public-user installation until a qualified matched firmware pair is published. This guide describes the intended workflow; no stable download is currently offered.

## 1. Identify the board

Confirm **MM32SPIN05PF**, an **ESP8285 / ESP-01F** module and **PCF8563**. Use the [photographs](HARDWARE.md). A similar enclosure or a CH899 model number is not proof of compatible electronics.

## 2. Prepare

You need access to the PCB programming pads, a compatible SWD programmer for MM32, a **3.3 V logic** USB-UART adapter for ESP, short leads, a stable regulated board supply, and the appropriate Windows software. Soldering/programming access is required; the running firmware does not require hardware modifications.

Remove batteries before using an external supply. The bench clock used regulated **3.3 V at the battery terminals**. Verify polarity and voltage. Never connect 5 V to the board or its signals. Do not connect adapter/programmer power outputs alongside an external supply. Share ground. Do not infer a wire's function from its color or from an unrelated board photograph.

Programming replaces existing firmware. Keep any personal original backups privately. An ESP backup alone cannot restore the original MM32 application. Do not bypass readout protection or assume that a full MM32 original backup is available.

## 3. Install a matched pair

- [MM32 movement-controller guide](MM32.md): SWD, Keil µVision and the matching HEX.
- [ESP guide](FLASHING.md): ROM UART bootloader, esptool and the matching BIN at offset zero.

Neither HC32 UART programming nor TXW813 power-on flashing applies. Do not substitute a file from either related project.

## 4. Start normally

Power down, release boot/reset straps, disconnect programmer-driven signals and restore normal power. The clock homes the hands, obtains time and catches up. Homing can take several minutes; blue indicates a received time, not completed hand setting.

Join **WiFi-Clock-Setup**, open **http://192.168.4.1/**, enter Wi-Fi/time preferences and save. Read the [user guide](USER_GUIDE.md) before changing movement or parking settings. A setting change can deliberately restart/rehome the movement.

If anything differs from the guide, stop and check [troubleshooting](TROUBLESHOOTING.md). Do not repeatedly flash or erase in response to an unexplained fault.
