# Install the Wi-Fi firmware

Use **WiFi-Clock-ESP.bin** from the extracted [WiFi Clock installation package](DOWNLOADS.md). Complete [the MM32 step](MM32.md) first.

## What you need

- A USB-to-serial adapter with **3.3 V signals**.
- A Windows PC with **Python and esptool 4.5.1**, the version used by this guide.
- Access to the ESP programming pads and the separate MM32 RESET pad.
- A stable regulated **3.3 V board supply**, with batteries removed.

This guide is for an ordinary USB-to-serial adapter. A NodeMCU used as a bridge has different printed-label conventions; do not assume its TX/RX labels have the same meaning.

If needed, obtain Python from [the official Windows downloads page](https://www.python.org/downloads/windows/). With Python working in a terminal, install esptool:

```powershell
python -m pip install esptool==4.5.1
```

Use this version for the command below. Installing the PC tool does not program the clock.

## 1. Connect the serial adapter

With power removed, connect:

| Adapter | Clock ESP pad |
| --- | --- |
| TX | RX |
| RX | TX |
| GND | G |

Use the [pad photographs](HARDWARE.md#programming-access). Power the board separately from the regulated 3.3 V supply. **Leave the adapter's VCC/5V/3V3 power wire disconnected.** Never apply 5 V to the board or its signals.

Before applying clock power:

1. Connect the adapter to USB. In **Device Manager → Ports (COM & LPT)**, note its COM number. Unplug and reconnect its USB cable if you need to identify which entry belongs to it.
2. Close any serial monitor or other program using the adapter.
3. Open the extracted package folder in File Explorer. Type **powershell** in its address bar and press Enter.

## 2. Put the ESP into programming mode

1. Hold the clock's **MM32 RESET pad to GND**. Keep this connection throughout the ESP transfer.
2. Connect ESP **IO0 to GND**.
3. Apply power. IO0 must be grounded when the ESP starts.
4. You may now release IO0. **MM32 RESET stays grounded.**

MM32 RESET and ESP IO0 are different pads. Do not hold the ESP itself in reset: it must be running its programming mode to answer the PC.

If you make a separate identification or backup read before writing, reset the ESP back into programming mode between the read and write operations.

## 3. Write the BIN

Use the BIN included in the same installation package as the MM32 firmware.

In the PowerShell window opened earlier, run the command below. Replace **COM4** with your adapter's COM number.

```powershell
python -m esptool --chip esp8266 --port COM4 --baud 38400 --before no_reset --after no_reset --no-stub write_flash --flash_mode dout --flash_freq 40m --flash_size 1MB 0x0 'WiFi-Clock-ESP.bin'
```

Leave the MM32 RESET connection grounded until the transfer finishes. The command says **esp8266** because esptool uses that chip family for the ESP8285 too.

Wait for the transfer to finish successfully. If it fails, stop and check the wiring, COM port, power and boot sequence. Do not add a full-chip erase as a routine fix: that erases saved settings.

## 4. Restart normally

1. Remove clock power.
2. Release ESP IO0 and the **MM32 RESET-to-GND connection**.
3. Disconnect the adapter's driven serial leads.
4. Restore normal clock power.

The ESP stays in programming mode until restarted normally. Look for **WiFi-Clock-Setup** and follow [Wi-Fi setup](USER_GUIDE.md#open-the-settings-page).

Existing settings can survive an application-only upgrade, but keep a note of your preferences. An original ESP backup restores only the Wi-Fi chip; it cannot restore the original MM32 movement firmware. Keep personal backups private.

[Installation overview](GETTING_STARTED.md) · [Programming help](TROUBLESHOOTING.md#a-programmer-will-not-connect)
