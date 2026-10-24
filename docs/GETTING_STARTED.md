# Install WiFi Clock v1.5

**Not ready for general installation yet.** The firmware is still being tested. Wait for the ready-to-install files listed on the [downloads page](DOWNLOADS.md) before following these steps.

## Before you start

This is an electronics upgrade, not an update uploaded through the settings page. You will need to open the movement and connect programming equipment. If you are not comfortable with that, ask someone experienced to help.

Check [the board photographs](HARDWARE.md). This guide is for **MM32SPIN05PF + ESP8285** only, not HC32/TXW813.

Installation replaces firmware on **both chips**. Keep any original backups you already have. A backup of the Wi-Fi chip alone will not restore the original movement firmware.

## 1. Gather the equipment

- A Windows PC; these are the instructions tested during development.
- A compatible CMSIS-DAP SWD programmer for the MM32.
- A USB-to-serial adapter with **3.3 V signals** for the ESP.
- A stable regulated **3.3 V supply**, short leads and access to the board's programming pads.
- Keil µVision with the MM32 device pack, and esptool for the ESP. The individual guides identify the tested versions.

**Power safety:** remove the batteries before connecting the external supply. Check voltage and polarity first. Never apply 5 V to the board or its signals. Do not connect programmer/adapter power outputs alongside a separate supply. All connected equipment needs a common ground.

## 2. Get the correct firmware

When a release is available, download its **MM32 HEX** and **ESP BIN** together, plus any supplied programming project and checksum file. Follow the [downloads page](DOWNLOADS.md); files from the other CH899 projects are not substitutes.

Ready-made files will be intended for installation without editing or compiling. The source-build instructions are separate for developers.

## 3. Program the two chips

1. Follow [the MM32 programming guide](MM32.md).
2. Follow [the ESP programming guide](FLASHING.md).

Use the file for the correct chip. If identification or verification fails, stop and check the wiring and tool settings before trying again.

## 4. Start the clock normally

Remove power, release the temporary IO0/reset connections and disconnect programmer-driven leads. Restore normal clock power.

The hands will find their reference positions and then move to the current time. This process, called homing and setting, can take several minutes. A blue LED means time has been received, not that the hands have finished moving.

## 5. Set up Wi-Fi

1. Join **WiFi-Clock-Setup** from your phone or computer.
2. Open **http://192.168.4.1/**.
3. Choose your home Wi-Fi network and enter its password.
4. Choose your timezone and clock preferences.
5. Press **Save settings** and allow the clock to finish setting its hands.

If the settings page is not available, hold **M.SET for about three seconds** and try again. A phone may warn that the setup network has no Internet access; stay connected to it while using the local setup page.

Next: [settings and everyday use](USER_GUIDE.md). If something is wrong, use [troubleshooting](TROUBLESHOOTING.md) rather than repeatedly erasing or reflashing.
