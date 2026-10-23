/* Private rtc.c helpers. Exclusive experimental ownership of the unused
 * countdown timer, never calendar/STOP/TEST1/CLKOUT/alarm configuration.
 * An interrupt-using timer is not taken over. */
static uint32_t counter_open(void)
{
    wifi_rtc.error = 0u;
    wifi_rtc.crh_before = RTC_CRH;
    if ((RTC_CRH & 0xffu) != 0x44u || (RTC_IDR & RTC_BOTH) != RTC_BOTH)
        return 0u;
    GPIOB_BSRR = RTC_BOTH;
    rtc_active = 1u;
    uint32_t irq = irq_save();
    RTC_CRH = (RTC_CRH & ~0xffu) | 0x66u;
    irq_restore(irq);
    pulse_diag[25] = 1u;
    return 1u;
}
static uint32_t counter_write(uint32_t reg, uint32_t value)
{
    uint32_t ok = bus_start() && bus_send(0xa2u) && bus_send(reg) && bus_send(value);
    bus_stop();
    return ok && !wifi_rtc.error;
}
uint32_t rtc_counter_start(void)
{
    volatile uint8_t control[2], status[1];
    if (!counter_open())
        return 0u;
    uint32_t ok = read_range(status, 1u, 1u) && read_range(control, 14u, 2u);
    /* An MCU-only reset may leave this build's 4096-Hz timer running.
     * RC6I reserves a non-interrupting timer in that configuration. */
    if (ok && !(status[0] & 1u) &&
        (!(control[0] & 0x80u) || control[0] == 0x80u))
    {
        pulse_diag[3] = status[0];
        pulse_diag[4] = (control[0] & 0x80u) ? 3u : control[0];
        pulse_diag[5] = control[1];
        pulse_diag[20] = 1u; /* Ownership survives failed pause until confirmed. */
        /* AF=1 preserves the alarm flag; TF=0 clears countdown flag.
         * Keep TI_TP/AIE unchanged; TIE stays disabled. */
        ok = counter_write(14u, 3u) &&
             counter_write(1u, (status[0] & 0x12u) | 8u) &&
             counter_write(15u, 255u) && counter_write(14u, 0x80u);
        if (ok)
            ok = read_range(control, 14u, 2u) && control[0] == 0x80u;
        if (!ok)
        {
            wifi_rtc.error = 0u;
            if (counter_write(14u, pulse_diag[4] & 0x7fu))
                pulse_diag[20] = 0u;
        }
    }
    else
        ok = 0u;
    bus_cleanup();
    return ok;
}

static uint32_t counter_before_calendar(void)
{
    if (pulse_diag[20])
        return rtc_counter_pause();
    /* RTC survives an MCU-only reset. Quiesce our reserved 4096-Hz profile
     * before full-register verification, even when SRAM ownership was reset. */
    if (!counter_open())
    {
        /* Startup can inherit a slave-held SDA after an interrupted transfer.
         * Recover ONCE before this precheck, not only later in set_rtc().
         * Reject wrong pin modes; never drive SCL high or alter RTC controls. */
        if ((RTC_CRH & 0xffu) != 0x44u)
        {
            wifi_rtc.error = 8u;
            return 0u;
        }
        if (!bus_prepare())
        {
            bus_cleanup();
            return 0u;
        }
        /* bus_prepare leaves the established bus open-drain and active.
         * The same bounded read/cleanup below now owns that recovered bus. */
        pulse_diag[25] = 1u;
    }
    volatile uint8_t control[2], status[1];
    uint32_t ok = read_range(control, 14u, 2u) && read_range(status, 1u, 1u);
    bus_cleanup();
    if (!ok)
        return 0u;
    if (control[0] != 0x80u || (status[0] & 1u))
        return 1u;
    pulse_diag[4] = 3u;
    pulse_diag[5] = control[1];
    pulse_diag[20] = 1u;
    return rtc_counter_pause();
}
uint32_t rtc_counter_read(uint32_t *value)
{
    volatile uint8_t a[2], b[2];
    if (!counter_open())
        return 0u;
    uint32_t ok = read_range(a, 14u, 2u);
    uint32_t first = REG32(0x40000024u);
    if (ok)
        ok = read_range(b, 14u, 2u);
    uint32_t span = REG32(0x40000024u) - first;
    bus_cleanup();
    if (!ok)
        return 0u;
    pulse_diag[26] = a[0];
    pulse_diag[27] = a[1];
    pulse_diag[28] = b[0];
    pulse_diag[29] = b[1];
    pulse_diag[30] = span;
    extern volatile uint32_t rtc_pace[16];
    uint32_t rate = rtc_pace[1] + 1u;
    uint32_t delta = (a[1] % 255u + 255u - b[1] % 255u) % 255u;
    uint32_t expected = (uint32_t)(((uint64_t)span * 32u) / rate);
    pulse_diag[32] = delta;
    pulse_diag[33] = expected;
    /* Period n=255 ticks, not an assumed 256-count binary overflow. */
    if (a[0] != 0x80u || b[0] != 0x80u || a[1] > 255u || b[1] > 255u)
    {
        pulse_diag[31] = 1u;
        return 0u;
    }
    /* Timestamped consistency, not a fixed5.86ms assumption. A completion
     * timestamp is not an exact sample instant: allow12 ticks uncertainty.
     * Reject long/ambiguous transfers rather than allowing a whole reload. */
    if (span > rate * 4u || delta > 200u ||
        delta + 12u < expected || delta > expected + 12u)
    {
        pulse_diag[31] = 2u;
        return 0u;
    }
    pulse_diag[31] = 0u;
    *value = b[1] % 255u;
    return 1u;
}
uint32_t rtc_counter_pause(void)
{
    if (!counter_open())
        return 0u;
    volatile uint8_t status[1];
    uint32_t ok = counter_write(14u, pulse_diag[4] & 0x7fu) &&
                  read_range(status, 1u, 1u) &&
                  counter_write(1u, (status[0] & 0x12u) | 8u) &&
                  counter_write(15u, pulse_diag[5]);
    bus_cleanup();
    if (ok)
        pulse_diag[20] = 0u;
    return ok;
}
