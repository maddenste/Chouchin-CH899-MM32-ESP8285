# Help and troubleshooting

## The settings page will not open

1. Hold **M.SET for about three seconds**.
2. Join **WiFi-Clock-Setup** and open **http://192.168.4.1/**.
3. If your phone warns that this network has no Internet, stay connected while using setup.
4. To open it through your home network instead, use the clock's current IP address from your router.

Wi-Fi switches off between sessions to save power. A page becoming unavailable after saving or closing it is not necessarily a fault. A `.local` name is not supported.

Check that your home Wi-Fi is 2.4 GHz. If you changed its name or password, use the setup network to update the clock.

## The hands are moving to the wrong place or have not finished setting

After power-on or a movement/battery-saver change, the hands first find their reference positions, then move to the time. This can take several minutes.

Blue means time was received, **not** that the hands have finished setting. Leave the clock undisturbed while it completes the movement.

If the hands finish consistently misaligned, check how they were fitted. Use the REC hand-fitting procedure in [the user guide](USER_GUIDE.md#buttons); always remove power before adjusting the hands.

## Seconds stop at 12

- **Hold&Start:** a short pause at 12 every minute is part of the style.
- **Night parking:** seconds stay at 12 between midnight and 06:00.
- **Battery saver On:** seconds stay parked all day.
- **After a time change:** seconds may wait at 12 while the clock lines up its next minute.

Check the selected settings and allow time correction to finish. If the hand does not resume when expected, note the time, selected mode and LEDs when reporting it.

## Red keeps flashing

The clock is still requesting time or opening a session. Check the page's Wi-Fi/time status, saved network details and time-server settings.

Being able to open the page does not by itself mean the clock has received valid time. If red keeps flashing, note how long it has been doing so and whether the page says **Time synchronised**.

## Movement is uneven

Note whether it happens after a pause at 12, a daily update, saving settings or the hands finishing their initial setting. Also note whether the following revolution is different.

Check with the programming/debug session closed. If it continues, [report it](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues). Include the movement style and what happened immediately before the problem.

## Error codes

**Count simultaneous red-and-blue flashes**, not red-only flashes. Both LEDs flash together N times, followed by about ten seconds dark, then repeat.

| Flashes | Meaning |
| --- | --- |
| 1 | The clock could not start correctly |
| 2 | Reserved for a developer abort indication; not expected during normal use |
| 3 | An unexpected processor error occurred |
| 4 | The minute/hour hand reference could not be found |
| 5 | The seconds reference/alignment failed, or the clock waited too long to complete a correction |
| 6 | The clock waited too long to receive valid time after starting |
| 7 | The hands took too long to find their starting positions or reach the time |
| 8 | The clock could not reliably read or set its timekeeping chip |
| 9 | The clock's time or recorded hand position was inconsistent |
| 10 | A motor timing or control safety check failed |

There is **no low-battery error code** in this firmware. A code does not automatically mean the motor or sensor is physically broken.

For errors 8 or 9, the hands may first move to around **1:50:30** to show a fault. In other cases they may stop where they are. Record the code and what happened before restarting.

Most faults need a power-cycle after the cause has been addressed. Do not repeatedly erase or reflash the clock without identifying the problem. If the error returns, report it. Developers can find [the detailed fault behavior](development/ARCHITECTURE.md#fault-handling) separately.

## A programmer will not connect

For MM32, check the SWD probe, common ground, board power and that µVision is set to the probe actually connected. An error naming ULINK does not mean you have a ULINK programmer.

For ESP, check the actual COM port, crossed TX/RX wiring and the IO0-at-power-on sequence. MM32 RESET must remain grounded during the ESP transfer. Re-enter the bootloader between separate read and write operations.

Do not select a similar-looking chip or force an unidentified signal high. Use the [MM32](MM32.md) or [ESP](FLASHING.md) programming guide.

## Ask for help

[Open an issue](https://github.com/maddenste/Chouchin-CH899-MM32-ESP8285/issues) and include:

- Firmware versions, if known, or the filenames you installed.
- Movement style and battery-saver setting.
- What you pressed or changed just before the problem.
- Hand positions and the LED flash count.
- Whether a programmer/debugger was connected.

A clear photo of the board or a short movement video can help. Do not include passwords, complete device backups or private network captures.
