# Install WiFi Clock v1.5

The upgrade programs two chips: **MM32** for hand movement and **ESP8285** for Wi-Fi and the settings page. Both are included in the installation package.

> [!WARNING]
> **Install at your own risk.** The original factory MM32 movement firmware is read-protected and cannot be read out for a backup. Once overwritten, it cannot be recovered from the chip. This replacement firmware was built from scratch.
>
> **Testing is ongoing.** Please [report any bugs or unexpected behaviour](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues).

This is a circuit-board upgrade, not an update sent through the settings page. You will need to open the movement and connect programming equipment. If you are unfamiliar with this work, ask someone experienced to help.

## 1. Check your board

Use [the identification photographs](HARDWARE.md). Your board must have **MM32SPIN05PF + ESP8285 / ESP-01F**. HC32/TXW813 boards use different firmware and tools.

## 2. Download and prepare

**[Download WiFi Clock v1.5](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/releases/download/v1.5/WiFi-Clock-v1.5.zip)** and extract the complete ZIP to a folder on your PC. Read `START-HERE.txt`.

You will need:

- A Windows PC.
- A compatible CMSIS-DAP SWD programmer for the MM32.
- A USB-to-serial adapter with **3.3 V signals** for the ESP.
- A regulated **3.3 V supply** and short connecting leads.
- Keil µVision with the MM32 device pack, plus Python/esptool. The chip-specific guides below include download and setup instructions.

**Remove the batteries before using an external supply.** Check voltage and polarity. Never apply 5 V to the board or its signals. Leave programmer/adapter power outputs disconnected when using the separate supply. All equipment needs a common ground.

The firmware is ready to install; no editing or compiling is needed.

## 3. Program both chips

1. Follow [install the movement firmware](MM32.md). Open **Install-MM32.uvprojx** from the extracted package and use **Flash → Download**.
2. Follow [install the Wi-Fi firmware](FLASHING.md), using **WiFi-Clock-ESP.bin** from the same package.

The two chips use different connections and programming procedures. Follow each guide in order. If programming or verification fails, stop and check the setup before continuing.

Keep any verified ESP backups you already have. An ESP backup cannot restore the read-protected factory MM32 firmware.

## 4. Start the clock

Remove power, release temporary IO0/reset connections and disconnect programmer-driven leads. Restore normal clock power.

The hands will find their reference positions and then move to the current time. Allow several minutes for this to finish. A blue LED means time has been received, not that the hands have finished moving.

## 5. Set up Wi-Fi

1. Join **WiFi-Clock-Setup** from your phone or computer.
2. Open **http://192.168.4.1/**.
3. Select your home Wi-Fi network and enter its password.
4. Choose your timezone and clock preferences.
5. Press **Save settings** and allow the hands to finish setting.

If the page is unavailable, hold **M.SET for about three seconds** and try again. If your phone warns that the setup network has no Internet, stay connected while using the local page.

Next: [settings and everyday use](USER_GUIDE.md) · [Troubleshooting](TROUBLESHOOTING.md)
