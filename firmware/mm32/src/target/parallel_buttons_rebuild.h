/* Independently qualified gestures; movement is changed only by REC.
 * Stable state layout: 9 is immediate permanent lockout,
 * 7==2 is a pending safe park transition. PB11 M.SET / PB10 REC active-low.
 * Never drive button pins. Nominal hold 384 ticks after four-sample debounce.
 */
#define buttons (minute_log + 220u)
static void buttons_tick(uint32_t tick)
{
    if (buttons[9])
        return;
    uint32_t raw = ((~B_IDR) >> 10) & 3u;
    buttons[0] = raw;
    if (raw != buttons[1])
    {
        buttons[1] = raw;
        buttons[2] = 1u;
    }
    else if (buttons[2] < 4u)
        ++buttons[2];
    if (buttons[2] == 4u)
        buttons[3] = raw;
    if (buttons[1] != buttons[3])
        return; /* Never fire on stale held level. */
    raw = buttons[3];
    if (!raw)
    {
        buttons[4] = buttons[6] = 0u;
        return;
    }
    if (buttons[6])
        return;
    if (!buttons[4])
    {
        buttons[4] = raw;
        buttons[5] = tick;
    }
    else if (raw == 3u && buttons[4] != 3u)
    {
        buttons[4] = 3u;
        buttons[5] = tick;
    }
    else if (raw != buttons[4])
        buttons[5] = tick;
    if (raw == buttons[4] && tick - buttons[5] >= 384u)
    {
        buttons[6] = 1u;
        if (raw == 1u)
        {
            manual_web_active = 0u;
            buttons[9] = 1u;
            buttons[7] = 2u;
            ++buttons[18];
            parallel_leds_rec_start(tick);
        }
        else if (!buttons[7] && !buttons[10])
            buttons[7] = raw == 3u ? 3u : 1u;
    }
}

/* ISR-owned safe handover. Stop starting seconds immediately, finish their
 * current pulse and all already queued runtime minute pulses before rehoming.
 * No catch-up/homing queue is carried into the fresh parking search. */
static uint32_t buttons_park_tick(uint32_t tick, uint32_t stage)
{
    if (buttons[7] != 2u)
        return 0u;
    if (fine_enabled)
    {
        /* Hardware owns current pulse endings and queued minute pulses. */
        fine_seconds_drain();
        /* Initial catch-up minutes are still owned by the coarse scheduler. */
        if (stage != 7u && minute_active && (int32_t)(tick - minute_end) >= 0)
        {
            GPIOB_BSRR = 6u << 16;
            minute_active = 0u;
        }
        if (fine_motion_pending() || (stage == 7u && request_pulses))
            return 1u;
        fine_stop();
    }
    if (second_active && (parallel_log[26] ? (int32_t)(tick - runtime_end) >= 0
                                           : ((tick - parallel_log[18]) & 7u) == 6u))
    {
        A_BSRR = 1u << 23;
        GPIOB_BSRR = 1u << 16;
        second_active = 0u;
    }
    if (minute_active && (int32_t)(tick - minute_end) >= 0)
    {
        GPIOB_BSRR = 6u << 16;
        minute_active = 0u;
        if (stage == 7u && request_pulses)
        {
            ++parallel_log[13];
            if (--request_pulses == 0u)
                parallel_log[22] = (parallel_log[22] + 1u) % 720u;
        }
    }
    if (stage == 7u && request_pulses && !minute_active && !second_active &&
        (int32_t)(tick - minute_due) >= 0)
    {
        GPIOB_BSRR = minute_polarity ? 2u : 4u;
        minute_polarity ^= 1u;
        minute_active = 1u;
        minute_end = tick + 4u;
        minute_due = tick + 8u;
    }
    if (minute_active || second_active || (stage == 7u && request_pulses))
        return 1u;
    uint32_t recovery = alignment_recovery == 2u && !buttons[9];
    buttons[7] = buttons[8] = buttons[10] = 0u;
    motors_off();
    radio_off();
    if (!recovery)
        if (!buttons[9])
            parallel_leds_off();
    daily_log[0] = daily_log[13] = 0u;
    if (recovery)
    {
        /* Preserve valid RTC, daily schedule, mode/settings, LED/web lease
         * and audit evidence. Reset only motor-local acquisition state. */
        for (uint32_t i = 1u; i < 160u; ++i)
            if (i < 153u || i > 156u)
                minute_log[i] = 0u; /* Retain confirmed TIME across recovery. */
        for (uint32_t i = 180u; i < 188u; ++i)
            minute_log[i] = 0u;
        fine_minute_steps = fine_night_parked = 0u;
        correction_wait_ahead = 0u;
        independent_catchup = 0u;
        parallel_log[22] = 0u; /* Fresh mechanical zero before normal catch-up. */
        minute_log[161] = minute_log[176] = minute_log[177] = 0u;
        alignment_recovery = 3u;
    }
    else
        for (uint32_t i = 1u; i < 220u; ++i)
            minute_log[i] = 0u;
    for (uint32_t i = 240u; i < 256u; ++i)
        minute_log[i] = 0u;
    for (uint32_t i = 1u; i < 256u; ++i)
        /* Calendar sampling belongs to the continuously running RTC clock,
         * not the motor acquisition state. Preserve its trusted projection
         * and rate window through REC/alignment/backward-time rehoming. */
        if ((i < 221u || i > 227u) &&
            (i < MM32_RESET_DIAG_FIRST || i >= MM32_RESET_DIAG_FIRST + MM32_RESET_DIAG_WORDS))
            seconds_log[i] = 0u;
    request_pulses = fine_pulses = dwell_fraction = minute_fine = 0u;
    second_highs = catchup_pulses = 0u;
    parallel_log[7] = parallel_log[8] = parallel_log[26] = parallel_log[30] = 0u;
    parallel_log[20] = parallel_log[21] = 0u;
    parallel_log[18] = tick + 1u;
    minute_due = tick + 1u;
    A_CRL = (A_CRL & ~(15u << 28)) | (1u << 28);
    GPIOB_CRL = (GPIOB_CRL & ~0xFFFu) | 0x221u;
    B_CRH = (B_CRH & ~(PAIR_MODES | (15u << 24))) | (2u << 20) | (2u << 28) | (4u << 24);
    parallel_log[2] = 1u;
    return 1u;
}

static void buttons_clean_finish(uint32_t result, uint32_t tick)
{
    __asm volatile("cpsid i" ::: "memory");
    if (buttons[9])
    {
        __asm volatile("cpsie i" ::: "memory");
        return;
    }
    if (result == 1u)
    {
        buttons[10] = 0u;
        buttons[15] = result;
        /* Confirmed erase: preserve ESP power through software restart and
         * allow five minutes to open setup; page TICKs extend the lease. */
        manual_web_active = 1u;
        manual_web_deadline = tick + 38400u;
        manual_web_tick_seen = uart_probe_good_tick;
        esp_time_received = 0u;
        esp_response_tick = tick;
        parallel_leds_daily_start();
        if (!parallel_log[6])
        {
            uart_probe_good_time = 0u;
            line_length = line_overflowed = 0u;
            next_user = tick + 256u;
            tx_index = 5u;
        }
        __asm volatile("cpsie i" ::: "memory");
        return;
    }
    radio_off();
    buttons[10] = 0u;
    buttons[15] = result;
    parallel_leds_off();
    if (!parallel_log[6])
    {
        /* Resume startup acquisition, discarding any TIME seen during CLEAN. */
        uart_probe_good_time = 0u;
        buttons[11] = tick;
        line_length = line_overflowed = 0u;
        next_user = tick + 256u;
        tx_index = 5u;
        radio_on();
        parallel_leds_daily_start();
    }
    __asm volatile("cpsie i" ::: "memory");
}

static void buttons_poll(void)
{
    static const uint8_t clean[6] = {'C', 'L', 'E', 'A', 'N', '\n'};
    uint32_t stage = parallel_log[2], tick = parallel_log[4];
    if (!stage || stage == 5u || stage == 6u || buttons[9])
        return;
    if (buttons[10])
    {
        uart_probe_poll_once();
        if (buttons[16])
        {
            buttons_clean_finish(1u, tick);
            return;
        }
        if (tick - buttons[11] >= 15360u)
        {
            buttons_clean_finish(2u, tick);
            return;
        }
        if (buttons[13] == 6u && (int32_t)(tick - buttons[12]) >= 0)
        {
            buttons[13] = 0u;
            buttons[12] = tick + 256u;
        }
        if (buttons[13] < 6u && (UART1_CSR & 1u))
        {
            REG32(UART_BASE) = clean[buttons[13]++];
            if (buttons[13] == 6u)
                ++buttons[14];
        }
        return;
    }
    __asm volatile("cpsid i" ::: "memory");
    uint32_t action = buttons[7];
    /* M.SET's web lease is independent of mechanical correction. CLEAN must
     * still wait until an accepted correction has completed. */
    if (!action || buttons[9] ||
        (action != 1u && (daily_log[0] == 7u || daily_log[13])))
    {
        __asm volatile("cpsie i" ::: "memory");
        return;
    }
    buttons[7] = 0u;
    if (action == 1u)
    {
        ++buttons[17];
        manual_web_active = 1u;
        manual_web_deadline = tick + 7680u;
        manual_web_tick_seen = uart_probe_good_tick;
        esp_sleep_requested = 0u; /* This new manual request supersedes old SLEEP. */
        if (daily_log[0] == 7u || daily_log[13])
        {
            /* Do not replace the immutable TIME snapshot, restart acquisition
             * or alter parked hands. Just power setup access independently. */
            if (!esp_awake)
                radio_on();
            next_user = tick;
            tx_index = 5u;
            parallel_leds_daily_start();
        }
        else if (!parallel_log[6])
        {
            /* Startup already powers ESP and services USER independent of hands. */
            next_user = tick + 256u;
            tx_index = 5u;
            parallel_leds_daily_start();
        }
        else if (daily_log[0] != 2u)
            buttons[8] = 1u;
    }
    else if (action == 3u)
    {
        manual_web_active = 0u;
        ++buttons[19];
        buttons[10] = 1u;
        buttons[11] = tick;
        buttons[12] = tick + 256u;
        buttons[13] = 6u;
        buttons[14] = buttons[15] = buttons[16] = 0u;
        buttons[8] = 0u;
        if (daily_log[0] == 2u)
        {
            daily_log[0] = 1u;
            daily_schedule(daily_log[14]);
        }
        radio_off();
        radio_on();
        parallel_leds_daily_start();
    }
    __asm volatile("cpsie i" ::: "memory");
}

/* Runtime TIME ownership is independent of the HTTP/web lease. A valid
 * record parsed during RTC I/O must be processed before a following SLEEP. */
static __attribute__((noinline)) void runtime_time_poll(void)
{
    if (parallel_log[2] != 7u || !parallel_log[6] || buttons[9] || buttons[10] ||
        mode_restart_state || alignment_recovery || daily_log[0] == 2u || daily_log[0] == 7u ||
        daily_log[13] || uart_probe_good_time == schedule_time_seen)
        return;
    Mm32UartEvent e = uart_probe_time_event;
    if (e.kind != MM32_UART_TIME || e.year < 2000u || e.year > 2099u)
        return;
    uint32_t tick = parallel_log[4];
    uint32_t origin = published_time_tick;
    if (!time_age(&e, &origin))
    {
        fail(8u);
        return;
    }
    uart_probe_time_event = e;
    published_time_tick = origin;
    uint32_t now = seconds_log[227], received = rtc_event_stamp(&e);
    if (now == 0xffffffffu)
    {
        fail(8u);
        return;
    }
    /* Mark consumed only after movement is eligible and the aged event is
     * retained. Repeated aligned records must not create another hold. */
    schedule_time_seen = uart_probe_good_time;
    if ((received > now && received - now > 2u) ||
        (received < now && now - received > 2u))
    {
        daily_log[0] = 2u;
        daily_log[4] = tick;
        daily_log[14] = now;
        daily_log[5] = uart_probe_good_time - 1u;
        daily_log[15] = uart_probe_uart_errors;
    }
    else
    {
        if (!time_publish(&e, origin))
        {
            fail(8u);
            return;
        }
        if (!daily_log[3] || e.scheduled_hour != daily_log[10] ||
            e.scheduled_minute != daily_log[11])
        {
            daily_log[10] = e.scheduled_hour;
            daily_log[11] = e.scheduled_minute;
            daily_schedule(now);
        }
    }
}

static void manual_web_poll(void)
{
    static const uint8_t user[5] = {'U', 'S', 'E', 'R', '\n'};
    if (!manual_web_active || buttons[9] || buttons[10])
        return;
    uint32_t tick = parallel_log[4];
    uart_probe_poll_once();
    if (mode_restart_state)
        return;
    /* Correction-owned sessions cannot use daily_poll's acquisition path.
     * Keep the normal non-blocking USER request cadence for this web lease;
     * daily acquisition and initial startup retain their existing TX owner. */
    if (esp_awake && parallel_log[6] && daily_log[0] != 2u)
    {
        if (tx_index == 5u && (int32_t)(tick - next_user) >= 0)
        {
            tx_index = 0u;
            next_user = tick + 256u;
        }
        if (tx_index < 5u && (UART1_CSR & 1u))
            REG32(UART_BASE) = user[tx_index++];
    }
    runtime_time_poll();
    if (uart_probe_good_tick != manual_web_tick_seen)
    {
        manual_web_tick_seen = uart_probe_good_tick;
        if ((int32_t)((tick + 1280u) - manual_web_deadline) > 0)
            manual_web_deadline = tick + 1280u;
    }
    if ((int32_t)(tick - manual_web_deadline) >= 0)
    {
        manual_web_active = 0u;
        /* Acquisition/correction retains its own timeout; a webpage lease
         * never powers off an unfinished time-request session. */
        if (parallel_log[6] && daily_log[0] != 2u && daily_log[0] != 7u)
            radio_off();
    }
}
