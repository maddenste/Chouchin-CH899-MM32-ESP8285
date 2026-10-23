/* Crystal-derived rate discipline, not I2C-triggered motor edges.
 * TIM2: free-running 32-bit HCLK counter, no outputs or IRQs.
 * C40[0] signature; [1] 0 new/1 active/3 fallback; [2] TIM2 initialised;
 * [3..5] RTC saved config; [6] last raw; [7] accumulated RTC ticks;
 * [8] HCLK anchor; [9] last HCLK; [10] next software poll tick;
 * [11] anchor valid; [12] rejects; [13] consecutive rejects; [14] updates;
 * [15] measured rate*8; [16] accepted rate*8; [17] max read duration;
 * [18] latest raw; [19] total reads. No debugger reset command.
 */
#define QT(o) REG32(0x40000000u + (o))
static void quartz_reject(void)
{
    ++pulse_diag[12];
    pulse_diag[11] = 0u;
    if (++pulse_diag[13] >= 3u)
    {
        (void)rtc_counter_pause();
        pulse_diag[1] = 3u; /* Existing calendar calibration resumes. */
    }
}
static __attribute__((noinline)) void quartz_sample(uint32_t raw, uint32_t clock, uint32_t duration)
{
    pulse_diag[18] = raw;
    ++pulse_diag[19];
    if (duration > pulse_diag[17])
        pulse_diag[17] = duration;
    uint32_t rate = rtc_pace[1] + 1u;
    uint32_t gap = pulse_diag[11] ? clock - pulse_diag[9] : 0u;
    pulse_diag[35] = gap;
    if (gap > pulse_diag[34])
        pulse_diag[34] = gap;
    /* An overlong read is unusable. A scheduling gap, however, is not a
     * failed RTC read: discard the old window and seed from this valid pair. */
    if (duration > rate * 2u)
    {
        pulse_diag[21] = 3u;
        quartz_reject();
        return;
    }
    if (pulse_diag[11] && gap > rate * 5u)
    {
        ++pulse_diag[12];
        ++pulse_diag[36];
        pulse_diag[21] = 6u;
        pulse_diag[11] = 0u;
        /* Never reconstruct elapsed counter ticks across unknown reloads. */
    }
    if (!pulse_diag[11])
    {
        pulse_diag[6] = raw;
        pulse_diag[8] = pulse_diag[9] = clock;
        pulse_diag[7] = 0u;
        pulse_diag[11] = 1u;
        return;
    }
    uint32_t delta = (pulse_diag[6] + 255u - raw) % 255u;
    uint32_t elapsed = clock - pulse_diag[9];
    uint32_t expected = (uint32_t)(((uint64_t)elapsed * 32u) / rate);
    if (delta > 200u || delta + 12u < expected || delta > expected + 12u)
    {
        pulse_diag[21] = 4u;
        quartz_reject();
        return;
    }
    pulse_diag[6] = raw;
    pulse_diag[9] = clock;
    pulse_diag[7] += delta;
    pulse_diag[13] = 0u;
    if (pulse_diag[7] < 8192u)
        return;
    uint32_t span = clock - pulse_diag[8];
    uint32_t measured = (uint32_t)(((uint64_t)span * 32768u) / pulse_diag[7]);
    pulse_diag[15] = measured;
    if (measured < 50000u * 1024u || measured > 75000u * 1024u)
    {
        pulse_diag[21] = 5u;
        quartz_reject();
        return;
    }
    uint32_t old = rate * 1024u + release_state[1];
    if (pulse_diag[14])
        measured = (old * 7u + measured + 4u) / 8u;
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    rtc_pace[1] = measured / 1024u - 1u;
    release_state[1] = measured % 1024u;
    REG32(0xe000e014u) = rtc_pace[1];
    rtc_pace[4] = 1u;
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
    pulse_diag[16] = measured;
    ++pulse_diag[14];
    pulse_diag[8] = clock;
    pulse_diag[7] = 0u;
    /* TIM3 adopts this rate at the existing lap-safe phase boundary.
     * No active pulse, polarity or phase counter is reset here. */
}
static void quartz_poll(void)
{
    uint32_t tick = parallel_log[4];
    if (parallel_log[2] == 6u || parallel_log[2] == 14u || pulse_diag[1] == 3u)
        return;
    if (pulse_diag[2] && QT(0x08u) != MM32_TIMER_STANDALONE_SMCR)
    {
        pwm_fault_snapshot(10u);
        fail(10u);
        return;
    }
    if (!pulse_diag[1])
    {
        pulse_diag[0] = 0x51525443u;
        pulse_diag[11] = pulse_diag[13] = 0u;
        if (!pulse_diag[2])
        {
            REG32(0x4002101cu) |= 1u;
            QT(0) = QT(0x0cu) = QT(0x20u) = 0u;
            QT(0x08u) = MM32_TIMER_STANDALONE_SMCR; /* Before UG/CEN. */
            QT(0x28u) = 0u;
            QT(0x2cu) = 0xffffffffu;
            QT(0x14u) = 1u;
            QT(0x10u) = 0u;
            QT(0) = 1u;
            pulse_diag[2] = 1u;
        }
        if (!rtc_counter_start())
        {
            pulse_diag[1] = 3u;
            pulse_diag[21] = 1u;
            pulse_diag[22] = rtc_motion_error();
            ++pulse_diag[12];
            return;
        }
        pulse_diag[1] = 1u;
        pulse_diag[10] = tick;
    }
    if ((int32_t)(tick - pulse_diag[10]) < 0)
        return;
    uint32_t raw, before = QT(0x24u);
    uint32_t ok = rtc_counter_read(&raw);
    uint32_t after = QT(0x24u);
    pulse_diag[10] = parallel_log[4] + 2u;
    if (parallel_log[2] == 6u || parallel_log[2] == 14u)
        return; /* An interrupt may have faulted during the I2C transaction. */
    if (!ok)
    {
        pulse_diag[21] = 2u;
        pulse_diag[22] = rtc_motion_error();
        quartz_reject();
        return;
    }
    /* Consistent completion timestamps; read uncertainty averages over>=2s. */
    quartz_sample(raw, after, after - before);
}
