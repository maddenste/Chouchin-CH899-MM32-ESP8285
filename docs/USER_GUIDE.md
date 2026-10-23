# Setup and everyday use

## Open settings

Hold **M.SET for about three seconds** to wake Wi-Fi. Join **WiFi-Clock-Setup** and open **http://192.168.4.1/**, or use the clock's router-assigned LAN address while it is awake. The setup AP is offered alongside the saved Wi-Fi network on every wake.

The LAN hostname is **WiFi-Clock-ABCDEF** using the final six MAC hex digits. Router display/name registration varies. **mDNS is not implemented**; a `.local` address is not promised. Use a trusted 2.4 GHz network and do not expose this HTTP page to the Internet.

<img src="screenshots/setup-mobile.png" alt="Mobile setup page with synthetic test settings" width="350">

## Wi-Fi and time

Choose a Wi-Fi network or enter its name manually. A saved password is not sent back to the browser; leaving it unchanged keeps the stored secret. The clock synchronises through NTP while the ESP is awake; it does not require an always-on Wi-Fi session.

Primary NTP defaults to **pool.ntp.org**. The secondary field defaults to **blank**; enter a backup if wanted. A good accepted response is sufficient: the firmware does not require three NTP lookups. Fractional NTP seconds are retained internally, and TIME transmission is scheduled near the start of a whole second. This improves consistency but is not a promise of laboratory accuracy or zero daily drift.

Select timezone and Automatic, Disabled or Custom-rule DST. Custom input uses supported POSIX rules, not an IANA name such as `Europe/London`. Fixed offsets and `Mmonth.week.weekday[/time]` rules are supported; J/day-number rules are not. Check a custom rule against your region's actual requirements. Changing back to Automatic selects the zone's automatic rule; saving is required.

**Daily update time** accepts any hour and minute using the browser time picker. It is local clock time, not a ten-minute interval selector. A temporary wake approximately one minute before a DST transition does not replace the saved daily time. The pending-DST record is distinguished from an ordinary manual correction; see [protocol](PROTOCOL.md).

## Movement

| Minute hand | Seconds hand | Behavior |
| --- | --- | --- |
| Gradual | Continuous | Minute hand advances in six steps per minute; seconds continue |
| Jump | Continuous | Minute hand advances at the minute marker; seconds continue |
| Gradual | Pause at 12 | Stop2Go seconds with gradual minute steps |
| Jump | Pause at 12 | Hold&Start / Stop2Go seconds and minute jump |

Stop2Go moves slightly faster for most of the minute and holds at `00`. Thus a minute step tied to civil time need not coincide with the accelerated seconds hand pointing at the corresponding dial mark. Judge timing against actual time, not the moving Stop2Go hand alone.

| Second-hand battery saver | Behavior |
| --- | --- |
| Off | Selected seconds movement throughout the day |
| Night parking | Seconds park at `00` between 00:00 and 06:00; minute/hour display continues |
| On | Seconds remain parked, including when no seconds hand is fitted; minute/hour display continues |

Scheduled-night startup completes the normal first seconds revolution before parking. The PWM timebase is preserved across ordinary holds/overnight release; powered pulses still finish safely. Permanent parking does not require launching the runtime seconds waveform.

**Changing the movement style or second hand battery saver will restart the clock and rehome the hands after saving.** Wait for homing/catch-up to finish; the hands can take several minutes to set.

## Save and session ending

Save persists settings and starts the confirmation flow. The ESP sends TIME, the MM32 returns the exact accepted record, and only a matching confirmation permits the Save-triggered SLEEP request. SLEEP is **ESP → MM32**, requesting early shutdown of the ESP session; it is not the ESP putting the movement controller to sleep.

Refreshing/opening the page has a five-second grace to avoid immediately ending the session. Do not assume that a Save success means NTP has already completed or that the mechanical hands have finished setting. A network change can make the page unreachable; reconnect using the new network/IP or the setup AP.

Large ordinary time corrections (over one minute) can safely drain movement and rehome without waiting for the end of the current seconds revolution. Small corrections and flagged DST changes use the established boundary policy. After a correction, seconds held at `00` resume on an appropriate whole-minute boundary rather than deliberately starting late. A newer update arriving during catch-up remains pending.

## Buttons and LEDs

| Hold about three seconds | Action |
| --- | --- |
| M.SET | Wake ESP/settings session; does not erase settings |
| REC | Safely park/rehome for hand alignment; normal running is locked out until restart |
| M.SET + REC | Request saved ESP settings clear through the CLEAN exchange |

Before fitting/refitting hands, use the REC parking workflow, wait until movement has stopped at its reference, then remove power before touching hands/gears. Do not adjust hands while powered. Restore normal power afterward to home and set time again.

Flashing red alone means a request/session is in progress. Blue confirms a time record was received, **not** that the hands are already correct. Repeated simultaneous red/blue flash groups indicate [numbered faults](TROUBLESHOOTING.md#error-codes).
