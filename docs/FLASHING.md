# Install the ESP Wi-Fi firmware

Use the **ESP R13** BIN from [downloads](DOWNLOADS.md), together with MM32 RC6BC.

## What you need

- A USB-to-serial adapter with **3.3 V signals**.
- A Windows PC with **Python and esptool 4.5.1**, the version used for the tested procedure.
- Access to the ESP programming pads and the separate MM32 RESET pad.
- A stable regulated **3.3 V board supply**, with batteries removed.

This guide is for an ordinary USB-to-serial adapter. A NodeMCU used as a bridge has different printed-label conventions; do not assume its TX/RX labels have the same meaning.

If needed, obtain Python from [the official Windows downloads page](https://www.python.org/downloads/windows/). With Python working in a terminal, install the esptool version used by this guide:

```powershell
python -m pip install esptool==4.5.1
```

The command installs the PC tool; it does not connect to or change your clock. The flashing command below uses the version-4 option names. Other esptool versions may need different commands.

## 1. Connect the serial adapter

With power removed, connect:

| Adapter | Clock ESP pad |
| --- | --- |
| TX | RX |
| RX | TX |
| GND | G |

Use the [pad photographs](HARDWARE.md#programming-access). Power the board separately from the regulated 3.3 V supply. **Leave the adapter's VCC/5V/3V3 power wire disconnected.** Never apply 5 V to the board or its signals.

Close any serial monitor or other program using the adapter.

## 2. Put the ESP into programming mode

1. Hold the clock's **MM32 RESET pad to GND**. Keep this connection throughout the ESP transfer.
2. Connect ESP **IO0 to GND**.
3. Apply power. IO0 must be grounded when the ESP starts.
4. You may now release IO0. **MM32 RESET stays grounded.**

MM32 RESET and ESP IO0 are different pads. Do not hold the ESP itself in reset: it must be running its programming mode to answer the PC.

If you make a separate identification or backup read before writing, reset the ESP back into programming mode between the read and write operations.

## 3. Write the BIN

Check the downloaded BIN against the release's checksum list first.

Find your adapter's actual COM port in Windows. The example uses **COM4**; change it if yours is different. Run the command from the folder containing the BIN, or replace the filename with its full path.

The current candidate's example is:

```powershell
python -m esptool --chip esp8266 --port COM4 --baud 38400 --before no_reset --after no_reset --no-stub write_flash --flash_mode dout --flash_freq 40m --flash_size 1MB 0x0 'Chouchin-899-MM32-ESP-v1.5-R13-20261024.bin'
```

Use the command/file listed with the eventual release if its filename changes. The command does not put the ESP into programming mode for you; complete step 2 first.

Wait for the transfer to finish successfully. If it fails, stop and check the wiring, COM port, power and boot sequence. Do not add a full-chip erase as a routine fix: that erases saved settings.

## 4. Restart normally

1. Remove clock power.
2. Release ESP IO0 and the **MM32 RESET-to-GND connection**.
3. Disconnect the adapter's driven serial leads.
4. Restore normal clock power.

The ESP stays in programming mode until restarted normally. Look for **WiFi-Clock-Setup** and follow [Wi-Fi setup](USER_GUIDE.md#open-the-settings-page).

Existing settings can survive an application-only upgrade, but keep a note of your preferences. An original ESP backup restores only the Wi-Fi chip; it cannot restore the original MM32 movement firmware. Keep personal backups private.

[Installation overview](GETTING_STARTED.md) · [Programming help](TROUBLESHOOTING.md#a-programmer-will-not-connect)
