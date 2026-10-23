# Program the ESP8285 Wi-Fi controller

**Pre-release guide.** This is the ESP8285 workflow, not the TXW813 workflow. Use 3.3 V logic and the matched BIN only. Existing settings may be retained by an application-only write; do not erase flash as a routine upgrade step.

## Connect

For an ordinary USB-UART adapter: **adapter TX → clock RX**, **adapter RX → clock TX**, and **GND → G**. A NodeMCU used as a bridge has different printed-label conventions; do not apply this table to an unidentified clone. Use the [pad photograph](HARDWARE.md#programming-access).

Power the board from a verified regulated 3.3 V supply with batteries removed. Do not connect the adapter's VCC/5V/3V3 power wire as a second supply. UART RX/TX must also be 3.3 V logic.

## Enter the ROM bootloader

1. Remove clock power and connect ground/serial leads.
2. Hold the clock's **MM32 RESET pad to GND** to prevent its UART traffic from interfering. Keep it grounded throughout the ESP transfer. This is the confirmed bench setup, not the ESP's reset line.
3. Ground ESP **IO0**, then apply power/reset to the ESP. GPIO0 must be low at the reset edge; grounding it after a normal boot is insufficient.
4. IO0 can be released after the initial bootloader entry. It need not remain grounded throughout the transfer; MM32 RESET remains grounded.
5. The ESP itself must be powered and released from reset to answer. Do not hold the ESP reset low or force an unidentified enable/reset signal high. MM32 reset and ESP reset are different signals.

Close serial monitors and other programs using the adapter. The tested adapter used COM4, but use the actual COM port on your PC. If you perform separate identification/read and write operations, **re-enter the ESP bootloader between them**; the tested workflow needed an ESP reset between read and write.

## Write the application

The verified bench settings were **esptool 4.5.1**, **38400 baud**, **no stub**, no automatic reset before/after, DOUT / 40 MHz / 1 MB, offset **0x0**. The command below is an example for that version; replace port and file path deliberately. It does not enter the bootloader for you.

```powershell
python -m esptool --chip esp8266 --port COM4 --baud 38400 --before no_reset --after no_reset --no-stub write_flash --flash_mode dout --flash_freq 40m --flash_size 1MB 0x0 'Chouchin-899-MM32-ESP-v1.5-R12-20261023.bin'
```

Check the BIN's SHA-256 before writing. The R12 candidate is **375,776 bytes**, not a complete personal 1 MiB backup. The ROM no-stub transfer's success is not an independent full-flash readback claim. Do not add a whole-chip erase unless you intentionally want to erase saved settings and understand the recovery implications.

After success, the ESP remains in the bootloader. Power off, release IO0 and the MM32 RESET-to-GND strap, disconnect programmer-driven lines and restart normally. The setup AP is **WiFi-Clock-Setup**, including on wakes with saved station credentials. See [setup](USER_GUIDE.md).

An original ESP backup restores only ESP contents. It cannot restore the original MM32 movement firmware. Keep original per-device images and credentials private; never upload them to an issue.
