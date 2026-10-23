# Help, LEDs and error codes

## Before changing anything

Record the exact MM32/ESP versions, selected movement and parking mode, what was pressed/saved, hand positions and LED sequence. Do not enter debug or reflash before preserving a useful observation: a debugger may halt/reset the clock and lose the session.

Flashing **red alone** is a request/session indication, not a numbered fault. **Blue** confirms TIME reception, not finished homing or correctly positioned hands. Homing/catch-up can take several minutes. With night parking selected, stationary seconds at `00` overnight are expected.

## Error codes

For numbered faults, **red and blue flash together N times**, then remain dark for approximately ten seconds before repeating. The following mapping was checked against RC6BB, not copied as an unchanged stock/HC32 error list.

| Code | Plain-language meaning |
| --- | --- |
| 1 | Invalid startup/restart command or attempt to reuse an already-started control session |
| 2 | Reserved legacy debugger/command-abort indication; no ordinary button action should produce it in RC6BB |
| 3 | Unexpected CPU exception or unhandled interrupt |
| 4 | Minute/hour homing reference was not found within the permitted search |
| 5 | Seconds homing/reference/alignment failed, or an authorized correction wait expired |
| 6 | Initial valid time acquisition timed out |
| 7 | Overall homing/catch-up movement took too long |
| 8 | RTC access, calendar validation, setting or sampling availability failed |
| 9 | Time/position consistency failed; includes impossible alignment/calibration-related state |
| 10 | Motor timing, sampling, DMA, output configuration or ramp safety guard failed |

There is **no battery-voltage fault code** in this replacement. A failure code is not by itself proof that a physical sensor/motor is defective.

Most faults stop movement and require reset/power-cycle after the cause is addressed. For RTC/consistency faults 8/9 in a qualified running state, the firmware may first move to its diagnostic position around **1:50:30** if coordinates can still be trusted. Unsafe electrical/sensor/timer faults do not attempt that motion. Error-6 setup recovery has a constrained path to accept a clean replacement TIME and request a reset; it is not permission to resume motors directly from a fault.

## Common symptoms

- **No setup page:** wake with M.SET, check WiFi-Clock-Setup or the current LAN IP; mDNS is absent. Check 2.4 GHz connectivity and supply. Saving a network change can close the old connection.
- **Red continues flashing:** the ESP may be awake but MM32 has not accepted a valid TIME. Page access alone does not establish successful UART/NTP handoff. Report versions and elapsed time; do not arbitrarily change UART baud.
- **No SWD probe / ULINK error:** verify the actual CMSIS-DAP probe, USB connection, SWD target selection, common ground and board supply. Selecting an unrelated programmer is not a firmware fix.
- **ESP bootloader does not answer:** check actual COM port, 3.3 V logic, crossed TX/RX, common ground, boot-at-IO0-low and an ESP that is powered/out of reset. Re-enter bootloader between read and write operations.
- **Seconds park too long after time correction:** a boundary wait may be intentional. Record current actual time, direction/size of correction and mode. Do not confuse accelerated Stop2Go dial position with civil seconds.
- **Lumpy/undulating seconds:** record whether it starts after a hold, Save, daily wake or catch-up, and whether the next lap differs. Test without debug. Clean counters cannot establish physical smoothness; this remains part of pre-release qualification.

Report problems through this repository's Issues. Do not post Wi-Fi passwords, tokens, personal flash dumps, private UART captures or per-board factory data.
