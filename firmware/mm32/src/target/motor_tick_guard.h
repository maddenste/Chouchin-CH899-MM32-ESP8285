/* Equal-priority motor handlers serialize state. In autonomous PWM, only
 * close powered minute falls defer a tick; unpowered starts may wait.
 * Post-service checks enforce real SysTick/compare deadlines. Coarse legacy
 * scheduling retains its duration margin. No busy-wait or extra periodic IRQ.
 */
static __attribute__((noinline)) void clock_tick_body(void);

static uint32_t motor_guard_counts(void)
{
    /* Autonomous minute edges use TIM14 even if seconds PWM never launched.
     * Its clock scale must not depend on uninitialised TIM3 registers. */
    uint32_t divisor = ((pwm_engine ? MT(0x28u) : FT(0x28u)) + 1u) * 4u;
    return (rtc_pace[1] + divisor) / divisor;
}

static uint32_t motor_guard_busy(uint32_t guard)
{
    if (!fine_enabled || parallel_log[2] != 7u)
        return 0u;
    uint32_t enabled = FT(0x0cu) & 30u;
    if (pwm_engine)
    {
        /* Seconds edges are autonomous and no longer have a bookkeeping IRQ.
         * Do not defer the sampling clock on a sticky TIM3 compare flag. */
        /* Only an energised coil's FALL is urgent. A queued rise may wait
         * until this tick returns: deferring the clock for an unpowered
         * start can create a false tick backlog during parked-seconds bursts. */
        if (pwm_min_phase == 2u && (MT(0x0cu) & 2u))
            return (MT(0x10u) & 2u) ||
                   (((MT(0x34u) - MT(0x24u)) & 65535u) <= guard);
        return 0u;
    }
    if (FT(0x10u) & enabled)
        return 1u;
    uint32_t now = FT(0x24u) & 65535u;
    for (uint32_t i = 0u; i < 4u; ++i)
    {
        if ((enabled & (2u << i)) && ((FT(0x34u + 4u * i) - now) & 65535u) <= guard)
            return 1u;
    }
    return 0u;
}

static void motor_guard_kick(void)
{
    if (motor_tick_pending)
        REG32(0xe000ed04u) = 1u << 28;
}

static __attribute__((noinline)) void motor_tick_fault(uint32_t reason, uint32_t before, uint32_t guard)
{
    /* Preserve the first record; never probe uninitialised/gated motor
     * peripherals during a coarse startup fault. No new global allocation. */
    if (seconds_log[16] != 0x50574d46u)
    {
        seconds_log[72] = before;
        seconds_log[74] = guard;
        seconds_log[75] = REG32(0xe000ed04u);
        if (pwm_engine)
        {
            seconds_log[73] = MT(0x24u);
            seconds_log[76] = MT(0x0cu);
            seconds_log[77] = MT(0x28u);
            seconds_log[78] = MT(0x34u);
            seconds_log[79] = MT(0);
            pwm_fault_snapshot(reason);
        }
        else
        {
            seconds_log[17] = reason;
            seconds_log[18] = parallel_log[4];
        }
    }
    motor_tick_pending = 0u;
    fail(10u);
}

static void motor_tick_dispatch(void)
{
    if (!motor_tick_pending)
        return;
    uint32_t guarded = fine_enabled && parallel_log[2] == 7u;
    uint32_t guard = guarded ? motor_guard_counts() : 0u;
    if (motor_guard_busy(guard))
    {
        return;
    }
    uint32_t epoch = motor_timer_epoch, was_enabled = guarded;
    /* Center-aligned TIM3 reverses direction: use the free-running minute
     * timer for elapsed work duration in the PWM engine, not modulo CNT. */
    uint32_t before = was_enabled ? (pwm_engine ? MT(0x24u) : FT(0x24u)) & 65535u : 0u;
    motor_tick_pending = 0u;
    clock_tick_body();
    /* Preserve the legacy coarse-engine duration check. In hardware PWM,
     * the 2ms margin protects a powered fall, not all housekeeping while
     * outputs are off. Check actual deadlines rather than faulting solely
     * because idle/queued-rise work exceeded that margin. */
    if (was_enabled && fine_enabled && epoch == motor_timer_epoch)
    {
        if (pwm_engine)
        {
            if (REG32(0xe000ed04u) & (1u << 26))
                motor_tick_fault(32u, before, guard); /* Next SysTick really due. */
            else if ((MT(0x0cu) & MT(0x10u) & 2u) &&
                     ((MT(0x24u) - MT(0x34u)) & 65535u) >
                         (pwm_min_phase == 2u ? guard : fine_min_period / 4u))
                motor_tick_fault(33u, before, guard); /* Actual late motor edge. */
        }
        else if (((FT(0x24u) - before) & 65535u) > guard)
            motor_tick_fault(34u, before, guard);
    }
}

void SysTick_Handler(void)
{
    /* A deferred tick must complete before the next 128 Hz tick. Keeping a
     * backlog would fabricate repeated sensor samples and motor deadlines. */
    if (motor_tick_pending)
    {
        motor_tick_fault(31u, 0u, 0u); /* Preserve backlog before clearing it. */
        return;
    }
    motor_tick_pending = 1u;
    motor_tick_dispatch();
    if (motor_tick_pending)
        SLEEP_IRQ_NOTE();
}

void PendSV_Handler(void)
{
    motor_tick_dispatch();
}
