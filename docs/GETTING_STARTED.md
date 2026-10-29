# Install WiFi Clock v1.5

This guide takes you from checking your clock to opening its settings page. You will install two firmware files: one controls the hands, the other handles Wi-Fi. Both are included in one download.

> [!WARNING]
> **Install at your own risk.** The original factory MM32 movement firmware is read-protected and cannot be read out for a backup. Once overwritten, it cannot be recovered from the chip. This replacement firmware was built from scratch.

**Updating from v1.5 or v1.5.1?** Program only the MM32 movement controller using [the movement-firmware guide](MM32.md). Keep the existing ESP R13 firmware and saved Wi-Fi settings. Then restart the clock normally. The steps below cover a first installation.

You will need to open the clock and connect programming equipment. The instructions below use Windows; no code editing or compiling is needed.

## 1. Check your board

CH899 clocks were made with different circuit boards. [Compare yours with the photos](HARDWARE.md) to confirm it is the **MM32 board** supported here. The identification guide also links to the upgrade for the other board type.

## 2. Download and prepare

**[Download WiFi Clock v1.5](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5.2/WiFi-Clock-v1.5.2.zip)** and extract the complete ZIP to a folder on your PC. Keep its files together.

You will need:

- A Windows PC.
- A [CMSIS-DAP / DAPLink programmer](https://www.ebay.co.uk/itm/254327616482) for the MM32 — the programmer listing used for this project.
- A [NodeMCU development board](https://github.com/nodemcu/nodemcu-devkit-v1.0) used as a USB-to-serial bridge for the ESP — the method used for this clock. A separate adapter with **3.3 V signals** is an alternative.
- A regulated **3.3 V supply** and short connecting leads.
- [Keil µVision](https://www.keil.com/download/product/) and the [MM32 device pack](https://www.keil.arm.com/packs/mm32spin0x_dfp-mindmotion/boards/) for the movement chip.
- [Python](https://www.python.org/downloads/windows/) and esptool for the Wi-Fi chip. The Wi-Fi installation guide gives the command to install esptool.

Check the model and pin labels before ordering; seller listings can change. The MM32 uses the programmer's **SWD** connection; the ESP uses **serial TX/RX**.

**Remove the batteries before using an external supply.** Check voltage and polarity. Never apply 5 V to the board or its signals. Leave programmer/adapter power outputs disconnected when using the separate supply. All equipment needs a common ground.

## 3. Program both chips

1. **[Install the movement firmware →](MM32.md)** using the included **Install-MM32.uvprojx** project.
2. **[Install the Wi-Fi firmware →](FLASHING.md)** using the included **WiFi-Clock-ESP.bin** file.

The two chips use different connections and programming procedures. Follow each guide in order. If programming or verification fails, stop and check the setup before continuing.

## 4. Start the clock

Remove power, release temporary IO0/reset connections and disconnect programmer-driven leads. Restore normal clock power.

The hands will find their starting positions. After Wi-Fi setup, they will move to the current time; allow several minutes for this to finish.

## 5. Set up Wi-Fi

1. Join **WiFi-Clock-Setup** from your phone or computer.
2. Open **http://192.168.4.1/**.
3. Select your home Wi-Fi network and enter its password.
4. Choose your timezone and clock preferences.
5. Press **Save settings** and allow the hands to finish setting.

If the page is unavailable, hold **M.SET for about three seconds** and try again. If your phone warns that the setup network has no Internet, stay connected while using the local page.

**Finished:** the hands show the correct time and follow your chosen movement style. Wi-Fi normally switches off to save power; hold M.SET again whenever you want to reopen the settings.

Next: [settings and everyday use](USER_GUIDE.md) · [Troubleshooting](TROUBLESHOOTING.md)
