/* Run the existing clock tick only when the next enabled motor compare is
 * at least 1/512 second away. Equal priorities retain the existing exclusive
 * ownership of shared state. A close edge runs first; TIM3 then pends PendSV
 * to retry the deferred tick. No busy-wait and no extra periodic interrupt.
 * In normal tracking the guard covers both hands' starts and stops. In
 * autonomous Stop2Go it guards only TIM14 minute edges, never TIM3 flags. Coarse
 * homing/catch-up/fault motion retains its existing SysTick deadlines.
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
        if (MT(0x0cu) & 2u)
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
    /* Guard against an unexpected handler overrun; never silently accept a
     * tick that consumes the reserved edge margin. Timer resets invalidate
     * elapsed-CNT comparisons and are tracked separately by epoch. */
    if (was_enabled && fine_enabled && epoch == motor_timer_epoch &&
        (((pwm_engine ? MT(0x24u) : FT(0x24u)) - before) & 65535u) > guard)
        fail(10u);
}

void SysTick_Handler(void)
{
    /* A deferred tick must complete before the next 128 Hz tick. Keeping a
     * backlog would fabricate repeated sensor samples and motor deadlines. */
    if (motor_tick_pending)
    {
        motor_tick_pending = 0u;
        fail(10u);
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
