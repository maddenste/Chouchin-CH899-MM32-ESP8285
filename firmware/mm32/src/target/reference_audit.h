/* Passive reference audit restricted to the midnight passage
 * and defers confirmed phase-mismatch recovery to a scheduled Wi-Fi session.
 * Minute samples only use released seconds gaps; seconds regain the shared
 * input before their next pulse and reject the first unsettled sample. */
#define audit (minute_log + MM32_AUDIT_FIRST)
#define audit_enabled minute_log[195]
#define audit_seconds_status minute_log[196]
#define audit_seconds_seen minute_log[197]
#define audit_seconds_delta minute_log[198]
#define audit_cancellations minute_log[199]
#define audit_last_probe minute_log[200]
#define audit_window_seen minute_log[201]
#define audit_initialized minute_log[202]
/* audit: 0 status(1 checking,2 pass,3 phase mismatch,4 missing,5 insufficient,
 * 6 cancelled),1 active,2 attempts,3 passes,4 mismatches,5 missing,
 * 6 insufficient,7 samples,8 first high substep,9 signed phase error,
 * 10 low markers,11 last qualified low marker,12 low streak,13 high streak,
 * 14 candidate tick,15 sample tick,16 selected sensor,17 seconds ready tick,
 * 18 probe counter,19 reference-qualified flag. All counts volatile. */
static uint32_t audit_settle_counts(void)
{
    uint32_t rate = rtc_pace[1] + 1u;
    if (FT(0x28u) == 31u)
        rate *= 4u;
    else if (FT(0x28u) == 15u)
        rate *= 8u;
    return (rate + 127u) / 128u;
}
static void audit_restore_seconds(uint32_t tick, uint32_t from_timer)
{
    if (audit[16] != 2u)
        return;
    GPIOB_BSRR = PAIR << 16;
    GPIOB_BSRR = 1u << 13;
    audit[16] = 1u;
    audit[17] = tick + 1u + from_timer;
}
static uint32_t audit_seconds_ready(uint32_t tick)
{
    if (audit[16] == 2u)
        return 0u;
    if (!audit[17])
        return 1u;
    if ((int32_t)(tick - audit[17]) < 0)
        return 0u;
    audit[17] = 0u;
    return 1u;
}
static __attribute__((noinline)) void audit_sample_minute(uint32_t tick)
{
    uint32_t high = (B_IDR >> 14) & 1u;
    if (!audit[1])
        return;
    ++audit[7];
    if (tick - audit[15] > 16u)
        audit[12] = audit[13] = 0u;
    audit[15] = tick;
    if (!high)
    {
        audit[13] = 0u;
        if (audit[12] < 3u)
            ++audit[12];
        if (audit[12] == 3u && audit[11] != parallel_log[22])
        {
            audit[11] = parallel_log[22];
            if (audit[10] < 12u)
                ++audit[10];
        }
        return;
    }
    audit[12] = 0u;
    if (!audit[13])
    {
        audit[8] = (parallel_log[22] * 6u + fine_minute_steps) % 4320u;
        audit[14] = tick;
    }
    if (audit[13] < 3u)
        ++audit[13];
    if (!audit[19] && audit[10] >= 12u && audit[13] == 3u && tick - audit[14] >= 8u)
    {
        int32_t error = (int32_t)((audit[8] + MINUTE_REFERENCE_OFFSET) % 4320u);
        if (error > 2160)
            error -= 4320;
        audit[9] = (uint32_t)error;
        audit[19] = 1u;
        audit[0] = (error >= -6 && error <= 6) ? 2u : 3u;
    }
}
static void audit_before_seconds_rise(uint32_t tick)
{
    if (audit[16] != 2u)
        return;
    if (pwm_engine ? tick - audit[18] >= 1u :
        ((FT(0x24u) - audit[18]) & 65535u) >= audit_settle_counts())
        audit_sample_minute(tick);
    audit_restore_seconds(tick, 1u);
}
static void audit_seconds_reference(void)
{
    int32_t delta = (int32_t)seconds_log[254] - 960;
    audit_seconds_delta = (uint32_t)delta;
    audit_seconds_seen = seconds_log[255];
    audit_seconds_status = (delta >= -16 && delta <= 16) ? 2u : 3u;
    if (audit[1] && audit_seconds_status == 3u)
        alignment_pending |= 2u;
}
static __attribute__((noinline)) void audit_tick(uint32_t tick, uint32_t stage)
{
    if (!audit_initialized)
    {
        for (uint32_t i = 0u; i < MM32_AUDIT_WORDS; ++i)
            audit[i] = 0u;
        audit_initialized = 1u;
    }
    uint32_t window = (parallel_log[16] == 23u && parallel_log[15] >= 30u) ||
                      (parallel_log[16] == 0u && parallel_log[15] <= 5u);
    if (!audit_enabled || stage != 7u || daily_log[13] || minute_log[229] || minute_log[230])
    {
        if (audit[1])
        {
            audit[0] = 6u;
            audit[1] = 0u;
            ++audit_cancellations;
        }
        audit_restore_seconds(tick, 0u);
        /* Never reuse pre-correction evidence or restart mid-window. */
        audit_window_seen = window;
        return;
    }
    if (!window)
    {
        if (audit[1])
        {
            if (!audit[19])
                audit[0] = audit[10] >= 12u ? 4u : 5u;
            if (audit[0] == 2u)
                ++audit[3];
            else if (audit[0] == 3u)
            {
                ++audit[4];
                alignment_pending |= 1u;
            }
            else if (audit[0] == 4u)
                ++audit[5];
            else
                ++audit[6];
            audit[1] = 0u;
        }
        audit_restore_seconds(tick, 0u);
        audit_window_seen = 0u;
        return;
    }
    if (!audit_window_seen)
    {
        audit_window_seen = 1u;
        audit[1] = 1u;
        audit[0] = 1u;
        ++audit[2];
        for (uint32_t i = 7u; i < 16u; ++i)
            audit[i] = 0u;
        audit[11] = 0xffffffffu;
        audit[19] = 0u;
    }
    if (parallel_log[30])
    {
        /* Optical 12 itself is outside the window. No fake fresh reading:
         * parked status denotes a position retained since reference/homing. */
        if (audit_seconds_status == 2u || (!audit_seconds_seen && parallel_log[8]))
            audit_seconds_status = 4u;
    }
    /* Autonomous edges cannot wait for sensor-mux restoration. Restrict
     * minute-channel probes to seconds holds, retain seconds lap auditing. */
    if (pwm_engine && pwm_running())
    {
        audit_restore_seconds(tick, 0u);
        return;
    }
    if (audit[16] == 2u && !second_active &&
        (pwm_engine ? tick - audit[18] >= 1u :
         ((FT(0x24u) - audit[18]) & 65535u) >= audit_settle_counts()))
    {
        audit_sample_minute(tick);
        audit_restore_seconds(tick, 0u);
    }
    if (!audit[1] || audit[19] /* Qualified once: no more minute-sensor powered probes. */
        || !fine_enabled || second_active || audit[16] == 2u || tick - audit_last_probe < 8u)
        return;
    if (!pwm_engine && (FT(0x0cu) & 2u) &&
        ((FT(0x34u) - FT(0x24u)) & 65535u) < audit_settle_counts())
        return;
    audit_last_probe = tick;
    audit[18] = pwm_engine ? tick : FT(0x24u) & 65535u;
    GPIOB_BSRR = PAIR << 16;
    GPIOB_BSRR = 1u << 15;
    audit[16] = 2u;
}
