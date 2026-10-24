# MM32 ↔ ESP UART protocol

For firmware developers. Users save preferences through [the settings page](../USER_GUIDE.md#save-your-changes); no UART commands are needed for everyday use.

The matched applications use **38400 baud, 8 data bits, no parity, one stop bit**, 3.3 V logic. ESP ROM boot text has a different baud rate and is not an application record. The MM32 parser rejects noise/truncated records rather than treating raw boot text as commands.

| Direction | Record | Meaning |
| --- | --- | --- |
| MM32 → ESP | `USER\n` | Wake-session handshake request |
| ESP → MM32 | `USER_OK\r\n` | Handshake acknowledgment |
| MM32 → ESP | `CLEAN\n` | Request saved-settings clear; ESP confirms the repeated request before clearing |
| ESP → MM32 | `CLEAN_OK\r\n` | Clear acknowledgment |
| ESP → MM32 | `+TICK\r\n` | Setup-session keepalive |
| ESP → MM32 | `+TIME:...\r\n` | Time, wake schedule, movement and parking settings |
| MM32 → ESP | Exact accepted `+TIME:...\r\n` | Confirmation of the transmitted record |
| ESP → MM32 | `SLEEP\r\n` | Request early end of ESP session; no reply required |

Example wire record, with a synthetic date/time:

```text
+TIME:Sat Oct 24 10:00:00 2026 +0100 10:0031\r\n
```

After numeric UTC offset, `10:00` is the next requested wake time. The final **two adjacent digits** are movement `3` and parking `1`; they are not additional minutes. Actual wire endings are CR/LF bytes, not the literal backslash letters shown here.

| Movement digit | Minute / seconds |
| --- | --- |
| 0 | Gradual / continuous |
| 1 | Jump / continuous |
| 2 | Gradual / pause at 12 |
| 3 | Jump / pause at 12 |

Parking: `0` Off, `1` Night parking, `2` On. Legacy records without the selectors still parse, but do not provide the full matched settings flow.

The user interface exposes **Sweep (0), Burst (1) and Hold&Start (3)**. Selector 2 is accepted at protocol level but is not a separate choice in the current Movement style dropdown. Do not document four user-selectable styles from the raw two-bit encoding.

An optional **` DST`** suffix marks an upcoming DST update. During the early wake, the ESP can send the upcoming local offset/time plus the temporary transition schedule. The MM32 defers that flagged change to its authorized boundary rather than treating it as an ordinary immediate large correction. The saved everyday wake time remains an ESP setting and is restored in ordinary messages.

After Save, the ESP retains the exact pending TIME record and retries confirmation while awake. Only a matching MM32 echo qualifies that Save exchange for SLEEP; an unrelated older echo is insufficient. Pending-update and in-flight-correction records are separate on MM32 so a later valid update is not silently lost during catch-up.

TIME is sent near `.000` of any second, not only `:00` of a minute. The format carries whole seconds, not a fractional timestamp. MM32 compensates approximately for serial record duration and monotonic age; do not edit received timestamps manually to fake alignment.

SLEEP does not directly change the PWM timebase. The MM32 owns the eventual ESP shutdown and safe settings-restart sequencing. There is no MM32 response to SLEEP and no interpretation of SLEEP as a command to stop normal hand movement.
