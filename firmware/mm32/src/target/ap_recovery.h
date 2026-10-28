/* Error 6 only: operator-requested network recovery with motors disabled.
 * Other faults and REC lockout remain latched. No new wire commands. */
volatile uint32_t ap_recovery[10];
/* state(0 idle,1 CLEAN,2 setup,3 reset requested), raw, hold start, fired,
 * next TX, index, response tick, TIME baseline, ACK baseline, TICK baseline */
static void ap_recovery_tick(uint32_t tick)
{
    if (parallel_log[3] != 6u || buttons[9])
        return;
    uint32_t raw = ((~B_IDR) >> 10) & 3u;
    if (raw != 3u)
    {
        ap_recovery[1] = raw;
        ap_recovery[3] = 0u;
        return;
    }
    if (ap_recovery[1] != 3u)
    {
        ap_recovery[1] = 3u;
        ap_recovery[2] = tick;
    }
    if (!ap_recovery[0] && !ap_recovery[3] && tick - ap_recovery[2] >= 388u)
    {
        ap_recovery[3] = 1u;
        ap_recovery[0] = 1u; /* Main opens UART; ISR never starts a motor. */
        ap_recovery[5] = 6u;
        ap_recovery[4] = tick;
        ap_recovery[6] = tick;
        ap_recovery[7] = uart_probe_good_time;
        ap_recovery[8] = buttons[16];
        ap_recovery[9] = uart_probe_good_tick;
    }
}
static void ap_recovery_poll(void)
{
    if (parallel_log[3] != 6u || buttons[9] || !ap_recovery[0] || ap_recovery[0] == 3u)
        return;
    uint32_t tick = parallel_log[4];
    if (!esp_awake)
    {
        radio_on();
        parallel_leds_daily_start();
    }
    uart_probe_poll_once();
    if (ap_recovery[0] == 1u && buttons[16] != ap_recovery[8])
    {
        ap_recovery[0] = 2u;
        ap_recovery[6] = tick;
        ap_recovery[7] = uart_probe_good_time;
        /* Do NOT remove ESP power on CLEAN_OK: its deferred restart must run. */
    }
    if (uart_probe_good_tick != ap_recovery[9])
    {
        ap_recovery[9] = uart_probe_good_tick;
        ap_recovery[6] = tick;
    }
    if (ap_recovery[0] == 2u && uart_probe_good_time != ap_recovery[7] &&
        uart_probe_time_event.year >= 2000u && uart_probe_time_event.year <= 2099u)
    {
        ap_recovery[0] = 3u;
        reset_note_request(MM32_RESET_CLEAN);
        /* Fresh startup restores disabled IRQs/timers and rehomes safely.
         * Never jump directly from a latched fault into movement. */
        __asm volatile("dsb" ::: "memory");
        REG32(0xe000ed0cu) = 0x05fa0004u;
        __asm volatile("dsb" ::: "memory");
        return;
    }
    if (tick - ap_recovery[6] >= 38400u)
    {
        radio_off();
        ap_recovery[0] = 0u;
        parallel_leds_fault_start(tick);
        return;
    }
    if (ap_recovery[0] == 1u)
    {
        static const uint8_t clean[6] = {'C', 'L', 'E', 'A', 'N', '\n'};
        if (ap_recovery[5] == 6u && (int32_t)(tick - ap_recovery[4]) >= 0)
        {
            ap_recovery[5] = 0u;
            ap_recovery[4] = tick + 256u;
        }
        if (ap_recovery[5] < 6u && (UART1_CSR & 1u))
            REG32(UART_BASE) = clean[ap_recovery[5]++];
    }
}
