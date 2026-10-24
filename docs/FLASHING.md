# Install the Wi-Fi firmware

Use **WiFi-Clock-ESP.bin** from the extracted [WiFi Clock installation package](DOWNLOADS.md). Complete [the MM32 step](MM32.md) first.

## What you need

- A [NodeMCU development board](https://github.com/nodemcu/nodemcu-devkit-v1.0) and USB data cable, used as a serial bridge.
- A Windows PC with **Python and esptool 4.5.1**, the version used by this guide.
- Access to the ESP programming pads and the separate MM32 RESET pad.
- A stable regulated **3.3 V board supply**, with batteries removed.

The **NodeMCU bridge method worked on this clock**. It uses the NodeMCU's USB connection to program the clock; no firmware needs installing on the NodeMCU. An ordinary 3.3 V serial adapter can also be used, with the alternative wiring below.

If needed, obtain Python from [the official Windows downloads page](https://www.python.org/downloads/windows/). With Python working in a terminal, install esptool:

```powershell
python -m pip install esptool==4.5.1
```

Use this version for the command below. Installing the PC tool does not program the clock.

## 1. Connect the NodeMCU bridge

With clock power removed and the NodeMCU unplugged from USB, connect:

| NodeMCU printed pin | Connect to |
| --- | --- |
| GND | Clock ESP pad G |
| RX / GPIO3 | Clock ESP pad RX |
| TX / GPIO1 | Clock ESP pad TX |
| RST | NodeMCU's own GND |

Keep **NodeMCU RST connected to its own GND** throughout programming so its onboard ESP does not interfere. This is separate from the clock's MM32 RESET connection in step 2.

The RX-to-RX and TX-to-TX connections are intentional for this method: the printed labels refer to the NodeMCU's own ESP. They follow the [standard NodeMCU schematic](https://github.com/nodemcu/nodemcu-devkit-v1.0/blob/master/NODEMCU_DEVKIT_V1.0.PDF); check the wiring if using a different board or clone.

<details>
<summary>Using an ordinary USB-to-serial adapter instead?</summary>

Use an adapter with **3.3 V signal levels**. Its labels refer to the adapter itself, so cross TX and RX:

| Adapter | Clock ESP pad |
| --- | --- |
| TX | RX |
| RX | TX |
| GND | G |

</details>

Use the [pad photographs](HARDWARE.md#programming-access). Power the clock separately from the regulated 3.3 V supply. **Leave NodeMCU VIN/3V3 and any adapter VCC/5V/3V3 power outputs disconnected from the clock.** Never apply 5 V to the board or its signals.

Before applying clock power:

1. Connect the NodeMCU (or adapter) to USB. In **Device Manager → Ports (COM & LPT)**, note its COM number. Unplug and reconnect its USB cable if you need to identify which entry belongs to it.
2. Close any serial monitor or other program using the adapter.
3. Open the extracted package folder in File Explorer. Type **powershell** in its address bar and press Enter.

## 2. Put the ESP into programming mode

1. Hold the clock's **MM32 RESET pad to GND**. Keep this connection throughout the ESP transfer.
2. Connect ESP **IO0 to GND**.
3. Apply power. IO0 must be grounded when the ESP starts.
4. You may now release IO0. **MM32 RESET stays grounded.**

MM32 RESET and ESP IO0 are different pads. Do not hold the clock's ESP itself in reset: it must be running its programming mode to answer the PC. The NodeMCU's own RST-to-GND connection stays in place.

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
3. Disconnect the NodeMCU or adapter from the clock and USB.
4. Restore normal clock power.

The ESP stays in programming mode until restarted normally. Look for **WiFi-Clock-Setup** and follow [Wi-Fi setup](USER_GUIDE.md#open-the-settings-page).

Existing settings can survive an application-only upgrade, but keep a note of your preferences. An original ESP backup restores only the Wi-Fi chip; it cannot restore the original MM32 movement firmware. Keep personal backups private.

[Installation overview](GETTING_STARTED.md) · [Programming help](TROUBLESHOOTING.md#a-programmer-will-not-connect)
