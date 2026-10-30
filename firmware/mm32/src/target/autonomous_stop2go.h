/* RC6AH: TIM3 always runs from its internal clock during ordinary holds.
 * TIM1 counts completed pulses. Its CC1 request drives DMA1 channel 2,
 * atomically clearing TIM3 CCER after pulse 960 in a released gap. CPU
 * servicing is not required to stop either output. Only delivered pulses
 * advance software position; blank internal cycles during holds do not.
 * CC4 is advisory for resuming in a released, up-counting gap: if late,
 * outputs stay disabled until another safe gap. No timer reset/UG is used.
 * RC6AK adds normal-speed first pulses and32-step Stop2Go launch ramps.
 * CC4 notifications update period/width only in inactive gaps; the PWM
 * hardware still generates every edge and DMA still enforces960 pulses.
 * TIM14 minute sequencing and TIM2 quartz reference are unchanged.
 */
#define BT(o) REG32(0x40012c00u + (o))
#define MT(o) REG32(0x40014000u + (o))
#define GD(o) REG32(0x4002001cu + (o)) /* DMA1 channel 2. */
#define pwm_resume_pending seconds_log[61]
#define pwm_resume_tick seconds_log[62]
#define pwm_dma_zero seconds_log[64] /* 0x2000079C: first 2 KB SRAM, DMA-accessible. */

static void pwm_dma_arm(uint32_t target)
{
    BT(0x0cu) = 0u;
    GD(0) = 0u;
    REG32(0x40020004u) = 0xf0u; /* Only channel 2 flags. */
    pwm_dma_zero = 0u;
    GD(0x08u) = 0x40000420u; /* TIM3 CCER: both motor output enables. */
    GD(0x0cu) = (uint32_t)&pwm_dma_zero;
    GD(0x04u) = 1u;
    BT(0x34u) = target;
    BT(0x10u) = ~2u;
    /* Highest priority, 32-bit source/destination, memory->peripheral,
     * one transfer, no increments/circular reload; transfer-error IRQ only. */
    GD(0) = 0x3a19u;
    BT(0x0cu) = 1u << 9; /* TIM1_CC1 -> DMA1 channel 2 (vendor mapping). */
}

/* Stop2Go keeps one timing pair throughout each moving revolution.
 * RC6BH refreshes the next pair from the filtered RTC reference only after
 * DMA has parked the hand. Homing still clears these operational words. */
#define pwm_fixed_period seconds_log[56]
#define pwm_fixed_width seconds_log[57]
/* RC6AK: reserved motor-local words, cleared on homing. No new RAM block. */
#define pwm_ramp_normal seconds_log[66]
#define pwm_ramp_step seconds_log[67]
#define pwm_ramp_last seconds_log[68]
#define pwm_ramp_active seconds_log[69]
#define pwm_ramp_updates seconds_log[70]
#define pwm_ramp_launches seconds_log[71]
static uint32_t pwm_ramp_width(uint32_t period)
{
    return 2u*((period*3u+4u)/8u); /* 75%, even for equal opposite pulses. */
}

/* Reserved seconds telemetry, not operational state. Preserve the FIRST fault
 * before shutdown disables TIM3's clock and destroys readable timer state. */
static void pwm_fault_snapshot(uint32_t reason)
{
    if (seconds_log[16] == 0x50574d46u)
        return;
    seconds_log[17] = reason;
    seconds_log[18] = parallel_log[4];
    seconds_log[19] = pwm_seen;
    seconds_log[20] = BT(0x24u);
    seconds_log[21] = FT(0);
    seconds_log[22] = FT(0x24u);
    seconds_log[23] = FT(0x10u);
    seconds_log[24] = FT(0x0cu);
    seconds_log[25] = BT(0);
    seconds_log[26] = BT(0x08u);
    seconds_log[27] = BT(0x34u);
    seconds_log[28] = MT(0x24u);
    seconds_log[29] = MT(0x10u);
    seconds_log[30] = pwm_min_phase;
    seconds_log[31] = second_highs;
    seconds_log[32] = seconds_log[248];
    seconds_log[33] = seconds_log[251];
    seconds_log[34] = FT(0x28u);
    seconds_log[35] = FT(0x2cu);
    seconds_log[36] = FT(0x34u);
    seconds_log[37] = FT(0x38u);
    seconds_log[38] = FT(0x3cu);
    seconds_log[39] = MT(0x34u);
    seconds_log[40] = parallel_log[2];
    seconds_log[41] = motor_tick_pending;
    seconds_log[42] = REG32(0x40020000u);
    seconds_log[43] = GD(0);
    seconds_log[44] = GD(0x04u);
    seconds_log[45] = GD(0x08u);
    seconds_log[46] = GD(0x0cu);
    seconds_log[47] = pwm_resume_pending;
    seconds_log[63] = FT(0x08u);
    seconds_log[65] = REG32(0x40000008u); /* TIM2 SMCR, not DMA source word64. */
    seconds_log[16] = 0x50574d46u;
}

static uint32_t pwm_running(void)
{
    return pwm_engine && fine_enabled && (FT(0) & 1u) &&
           FT(0x20u) == 0x110u;
}
static uint32_t pwm_powered(void)
{
    if (!pwm_running())
        return 0u;
    uint32_t count = FT(0x24u), low = fine_sec_width / 2u;
    uint32_t high = fine_period - low;
    if (FT(0) & 16u)
        return count <= low || count > high;
    return count < low || count >= high;
}
static void pwm_watchdog(uint32_t tick);
static void pwm_stop(void)
{
    ++motor_timer_epoch;
    GD(0) = 0u;
    pwm_resume_pending = 0u;
    pwm_ramp_active = 0u;
    /* Force inactive while AF still owns pins, then return released GPIO. */
    FT(0x18u) = 4u << 12;
    FT(0x1cu) = 4u << 4;
    FT(0x20u) = FT(0x0cu) = FT(0) = FT(0x10u) = 0u;
    BT(0) = BT(0x0cu) = 0u;
    FT(0x08u) = BT(0x08u) = MM32_TIMER_STANDALONE_SMCR;
    MT(0) = MT(0x0cu) = MT(0x10u) = 0u;
    REG32(0xe000e280u) = (1u << 16) | (1u << 19);
    A_BSRR = 1u << 23;
    GPIOB_BSRR = 1u << 16;
    A_CRL = (A_CRL & ~(15u << 28)) | (1u << 28);
    GPIOB_CRL = (GPIOB_CRL & ~15u) | 1u;
    if (pwm_min_phase == 2u)
    {
        GPIOB_BSRR = 6u << 16;
        minute_active = 0u;
    }
    second_active = 0u;
    pwm_min_phase = 0u;
    pwm_engine = 0u;
    fine_enabled = 0u;
    motor_guard_kick();
}
static uint32_t pwm_init(void)
{
    if (REG32(0x40021004u) & ((4u << 8) | (4u << 11)))
    {
        fail(10u);
        return 0u;
    }
    ++motor_timer_epoch;
    RCC_AHBENR |= 1u; /* DMA1, no clock-source/prescaler change. */
    GD(0) = 0u;
    REG32(0x40020004u) = 0xf0u;
    pwm_resume_pending = 0u;
    pwm_ramp_normal = pwm_ramp_step = pwm_ramp_last = pwm_ramp_active = 0u;
    pwm_ramp_updates = pwm_ramp_launches = 0u;
    REG32(0x4002101cu) |= 2u; /* TIM3 */
    REG32(0x40021018u) |= (1u << 11) | (1u << 16); /* TIM1/TIM14 */
    FT(0) = FT(0x0cu) = FT(0x20u) = FT(0x10u) = 0u;
    BT(0) = BT(0x0cu) = BT(0x20u) = BT(0x44u) = 0u;
    FT(0x08u) = BT(0x08u) = MM32_TIMER_STANDALONE_SMCR;
    BT(0x24u) = BT(0x34u) = 0u;
    BT(0x2cu) = 65535u;
    MT(0) = MT(0x0cu) = MT(0x20u) = 0u;
    MT(0x04u) = MT(0x18u) = 0u; /* TIM14 offset08 is reserved, not SMCR. */
    MT(0x28u) = 15u;
    MT(0x2cu) = 65535u;
    MT(0x14u) = 1u;
    MT(0x10u) = 0u;
    MT(0) = 1u;
    /* Minutes must work even if permanent parking never launches seconds. */
    uint32_t cycles = (rtc_pace[1] + 1u) * 1024u + release_state[1];
    fine_min_period = (cycles + 1024u) / 2048u;
    fine_min_width = (fine_min_period + 1u) / 2u;
    REG32(0xe000e410u) = (REG32(0xe000e410u) & 0x00ffff00u) | 0x80000080u;
    REG32(0xe000e408u) = (REG32(0xe000e408u) & 0xff00ffffu) | 0x00800000u;
    REG32(0xe000ed20u) = (REG32(0xe000ed20u) & 0xffffu) | 0x80800000u;
    REG32(0xe000e280u) = (1u << 16) | (1u << 19);
    REG32(0xe000e100u) = (1u << 16) | (1u << 19);
    REG32(0xe000e280u) = 1u << 10;
    REG32(0xe000e100u) = 1u << 10; /* DMA2/3 transfer-error path only. */
    pwm_engine = fine_enabled = 1u;
    pwm_min_phase = pwm_seen = pwm_draining = 0u;
    return 1u;
}
static void pwm_launch(void)
{
    if (pwm_running() || pwm_min_phase == 2u)
    {
        fail(10u);
        return;
    }
    audit_before_seconds_rise(parallel_log[4]);
    FT(0) = FT(0x0cu) = FT(0x20u) = 0u;
    BT(0) = BT(0x0cu) = BT(0x20u) = 0u;
    /* Establish safe standalone selectors BEFORE either timer's UG event. */
    FT(0x08u) = BT(0x08u) = MM32_TIMER_STANDALONE_SMCR;
    uint32_t cycles = (rtc_pace[1] + 1u) * 1024u + release_state[1];
    fine_period = fine_hold_seconds ?
        (uint32_t)(((uint64_t)cycles * 123u + 131072u) / 262144u) :
        (cycles + 1024u) / 2048u;
    /* Normal modes unchanged. Stop2Go adopts Proof09's75% powered profile,
     * initially at normal cadence, then ramped only between complete pulses. */
    fine_sec_width = fine_hold_seconds ? pwm_ramp_width(fine_period) :
        2u * ((cycles * 3u + 8192u) / 16384u);
    if (fine_hold_seconds && pwm_fixed_period)
    {
        fine_period = pwm_fixed_period;
        fine_sec_width = pwm_fixed_width;
    }
    fine_min_period = (cycles + 1024u) / 2048u;
    fine_min_width = (fine_min_period + 1u) / 2u;
    uint32_t low = fine_sec_width / 2u, high = fine_period - low;
    if (fine_period > 65535u || !low || low >= high)
    {
        fail(10u);
        return;
    }
    if (fine_hold_seconds && !pwm_fixed_period)
    {
        pwm_fixed_period = fine_period;
        pwm_fixed_width = fine_sec_width;
    }
    if (fine_hold_seconds)
    {
        pwm_ramp_normal = (pwm_fixed_period * 128u + 61u) / 123u;
        if (pwm_ramp_normal > 65535u || pwm_ramp_normal < pwm_fixed_period)
        {
            fail(10u);
            return;
        }
        fine_period = pwm_ramp_normal;
        fine_sec_width = pwm_ramp_width(fine_period);
        low = fine_sec_width / 2u; high = fine_period - low;
        pwm_ramp_step = pwm_ramp_last = 0u;
        pwm_ramp_active = 1u;
        ++pwm_ramp_launches;
    }
    BT(0x04u) = 0u;
    BT(0x18u) = 6u << 4; /* OC1REF= CNT<CCR1, internal only. */
    BT(0x1cu) = 0u;
    BT(0x28u) = 0u;
    /* Normal modes wrap the observer counter, not the motor phase. Since
     * CNT stays below CCR1=960, no output-disable DMA request is generated. */
    BT(0x2cu) = fine_hold_seconds ? 65535u : 959u;
    BT(0x34u) = 960u;
    BT(0x14u) = 1u;
    BT(0x24u) = BT(0x10u) = 0u;
    BT(0x04u) = 0u; /* No TIM3 slave gate: waveform never freezes at 00. */
    BT(0x08u) = MM32_PULSE_COUNTER_SMCR; /* Deliberate TIM3 ITR2 counter. */
    FT(0x04u) = 3u << 4; /* CC1 match pulse, even if flag already set. */
    /* TIM3 keeps SMS=0, TS=111: internal clock, with erratum workaround. */
    FT(0x28u) = 15u;
    FT(0x2cu) = fine_period;
    FT(0x34u) = fine_period / 2u; /* Midpoint of each released gap. */
    /* PWM2's first complete pulse is at the top of the triangle. Its pin
     * must be the NEXT polarity retained from homing/the previous lap. */
    uint32_t a_mode = second_polarity ? 7u : 6u;
    uint32_t b_mode = second_polarity ? 6u : 7u;
    FT(0x18u) = a_mode << 12;
    FT(0x1cu) = b_mode << 4;
    FT(0x38u) = a_mode == 6u ? low : high;
    FT(0x3cu) = b_mode == 6u ? low : high;
    FT(0x40u) = pwm_ramp_active ? low + (fine_period/2u-low)/2u : 0u;
    FT(0) = 3u << 5; /* Center aligned, compare events both directions. */
    FT(0x14u) = 1u;
    FT(0x24u) = fine_period / 2u + 1u; /* Both outputs low, initially up. */
    FT(0x10u) = 0u;
    A_BSRR = 1u << 23;
    GPIOB_BSRR = 1u << 16;
    REG32(0x48000020u) = (REG32(0x48000020u) & ~(15u << 28)) | (1u << 28);
    GPIOB_AFRL = (GPIOB_AFRL & ~15u) | 1u;
    FT(0x20u) = 0x110u; /* CH2/CH3 only; no TIM1 pin outputs. */
    /* Vendor MM32SPIN05PF HAL: AF push-pull | GPIO_Speed_50MHz ->0xB. */
    A_CRL = (A_CRL & ~(15u << 28)) | (11u << 28);
    GPIOB_CRL = (GPIOB_CRL & ~15u) | 11u;
    pwm_seen = pwm_draining = second_highs = second_active = 0u;
    pwm_watch_count = 0u;
    pwm_watch_tick = parallel_log[4];
    seconds_log[53] = parallel_log[4];
    seconds_log[54] = 0u; /* Normal-mode calibration pending at a released gap. */
    FT(0x0cu) = pwm_ramp_active ? 16u : 0u; /* Ramp notification, never motor edges. */
    pwm_dma_arm(960u);
    BT(0) = 1u;
    FT(0) = (3u << 5) | 1u;
}
/* A late release interrupt cannot produce a shortened pulse: leave CCER
 * disabled and try the next up-counting released gap. Only this bounded
 * critical section rearms the independent counter/DMA and opens outputs. */
static __attribute__((noinline)) uint32_t pwm_resume_window(void)
{
    uint32_t count=FT(0x24u), middle=fine_period/2u;
    uint32_t high=fine_period-fine_sec_width/2u;
    if (fine_hold_seconds)
    {
        uint32_t normal=pwm_ramp_normal, mid=normal/2u;
        uint32_t hi=normal-pwm_ramp_width(normal)/2u;
        if (mid>middle) middle=mid;
        if (hi<high) high=hi;
    }
    /* CC4 is the sole warm-release owner. Accept only its bounded up-count
     * service slot, not an arbitrary point discovered by a software poll. */
    return !(FT(0)&16u) && count>=middle+256u &&
        count<=middle+384u && count+128u<high;
}
static __attribute__((noinline)) void pwm_ramp_relaunch(void)
{
    /* Called with IRQs masked, outputs off and the pulse observer stopped. */
    uint32_t period=pwm_ramp_normal, width=pwm_ramp_width(period);
    uint32_t low=width/2u, high=period-low, middle=period/2u;
    uint32_t a_mode=(FT(0x18u)>>12)&7u;
    FT(0x2cu)=period;
    FT(0x38u)=a_mode==6u?low:high;
    FT(0x3cu)=a_mode==6u?high:low;
    FT(0x34u)=middle;
    fine_period=period; fine_sec_width=width;
    pwm_ramp_step=pwm_ramp_last=0u; pwm_ramp_active=1u;
    ++pwm_ramp_launches;
    FT(0x40u)=low+(middle-low)/2u;
}
static __attribute__((noinline)) void pwm_try_resume(void)
{
    if (!pwm_resume_pending || mode_restart_state || minute_log[229] ||
        parallel_log[2] == 6u || parallel_log[2] == 14u)
        return;
    if (FT(0x08u) != MM32_TIMER_STANDALONE_SMCR ||
        BT(0x08u) != MM32_PULSE_COUNTER_SMCR)
    {
        pwm_fault_snapshot(10u);
        fail(10u);
        return;
    }
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    if (pwm_resume_window())
    {
        BT(0) = 0u;
        if (fine_hold_seconds)
        {
            pwm_ramp_relaunch();
        }
        BT(0x2cu) = fine_hold_seconds ? 65535u : 959u;
        BT(0x24u) = 0u;
        pwm_dma_arm(960u);
        pwm_seen = pwm_draining = second_highs = second_active = 0u;
        pwm_watch_count = 0u;
        pwm_watch_tick = parallel_log[4];
        seconds_log[53] = parallel_log[4];
        seconds_log[54] = 0u;
        ++seconds_log[58];
        pwm_resume_pending = 0u;
        FT(0x0cu) = pwm_ramp_active ? 16u : 0u;
        BT(0) = 1u;
        FT(0x20u) = 0x110u; /* LAST, while both OC references are low. */
    }
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
}

/* No timer writes here. The existing CC4 release/ramp installs the new
 * pair in a gap low under both profiles, without stopping TIM3 or using UG.
 * Retain the previous pair when the reference is unavailable/unqualified. */
static __attribute__((noinline)) void pwm_refresh_stop_rate(void)
{
    if (!fine_hold_seconds || FT(0x20u) || pwm_ramp_active ||
        pwm_resume_pending || pwm_draining || pwm_seen != 960u ||
        pulse_diag[1] != 1u || !pulse_diag[14] || pulse_diag[13])
        return;
    uint32_t cycles = pulse_diag[16]; /* Already filtered, accepted HCLK*8. */
    if (cycles < 50000u * 1024u || cycles > 75000u * 1024u || !pwm_fixed_period)
        return;
    uint32_t period = (uint32_t)(((uint64_t)cycles * 123u + 131072u) / 262144u);
    uint32_t old = pwm_fixed_period, limit = old / 100u;
    /* Bound each correction to1% so the old/new released gaps overlap.
     * Two counts of hysteresis avoid chasing reference quantisation noise. */
    if (period > old + limit) period = old + limit;
    if (period + limit < old) period = old - limit;
    if (period + 2u >= old && period <= old + 2u)
        return;
    pwm_fixed_period = period;
    pwm_fixed_width = pwm_ramp_width(period);
    pwm_ramp_normal = (period * 128u + 61u) / 123u;
    ++seconds_log[55]; /* Existing rate-adjustment counter; no new SRAM. */
}
static __attribute__((noinline)) void pwm_resume_lap(void)
{
    if (!pwm_engine || !fine_enabled || pwm_draining || pwm_resume_pending ||
        pwm_min_phase == 2u || pwm_seen != 960u ||
        BT(0x34u) != 960u || BT(0x2cu) != 65535u || GD(0x04u) ||
        !(REG32(0x40020000u) & 0x20u) || (FT(0) & 0x61u) != 0x61u ||
        FT(0x08u) != MM32_TIMER_STANDALONE_SMCR ||
        BT(0x08u) != MM32_PULSE_COUNTER_SMCR || FT(0x20u) ||
        ((FT(0x18u) >> 12) & 7u) != (second_polarity ? 7u : 6u))
    {
        pwm_fault_snapshot(7u);
        fail(10u);
        return;
    }
    audit_before_seconds_rise(parallel_log[4]);
    pwm_refresh_stop_rate();
    /* Minute timing may follow fresh RTC calibration, without changing any
     * seconds PWM register or resetting the independent minute timer. */
    uint32_t cycles = (rtc_pace[1] + 1u) * 1024u + release_state[1];
    fine_min_period = (cycles + 1024u) / 2048u;
    fine_min_width = (fine_min_period + 1u) / 2u;
    pwm_resume_pending = 1u;
    pwm_resume_tick = parallel_log[4];
    /* Notify in both directions, but pwm_try_resume permits only the up
     * gap: the next full pulse then has the retained required polarity. */
    uint32_t middle = fine_period/2u;
    if (fine_hold_seconds && pwm_ramp_normal/2u > middle) middle=pwm_ramp_normal/2u;
    FT(0x40u) = middle + 256u;
    FT(0x10u) = ~16u;
    FT(0x0cu) |= 16u;
    /* A queued minute rise has not powered a coil yet. Leave its request
     * intact and let the ordinary runtime queue it after seconds commit.
     * Powered minute falls and all safety drains retain their priorities. */
    if (pwm_min_phase == 1u)
    {
        MT(0x0cu) = 0u;
        MT(0x10u) = ~2u;
        pwm_min_phase = 0u;
    }
}
static void pwm_drain(void)
{
    pwm_resume_pending = 0u;
    pwm_ramp_active = 0u;
    FT(0x0cu) &= ~16u;
    if (!pwm_engine || !pwm_running() || pwm_draining)
        return;
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    /* At most one more pulse: hardware finishes at the next released gap. */
    BT(0x2cu) = 65535u; /* Also permit target 960 in continuous normal modes. */
    pwm_dma_arm((BT(0x24u) & 65535u) + 1u);
    pwm_draining = 1u;
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
}
static void pwm_minutes_queue(void)
{
    if (!request_pulses || pwm_min_phase || pwm_resume_pending || parallel_log[2] != 7u)
        return;
    pwm_min_phase = 1u;
    MT(0x34u) = (MT(0x24u) + 16u) & 65535u;
    MT(0x10u) = ~2u;
    MT(0x0cu) = 2u;
}
void TIM14_Handler(void)
{
    SLEEP_IRQ_NOTE();
    if (!(MT(0x10u) & MT(0x0cu) & 2u))
        return;
    MT(0x10u) = ~2u;
    if (!pwm_engine || !fine_enabled || parallel_log[2] == 6u)
        return;
    uint32_t deadline = MT(0x34u);
    if (((MT(0x24u) - deadline) & 65535u) > fine_min_period / 4u)
    {
        pwm_fault_snapshot(4u);
        fail(10u);
        return;
    }
    if (pwm_min_phase == 1u && request_pulses)
    {
        GPIOB_CRL = (GPIOB_CRL & ~0xff0u) | 0x220u;
        GPIOB_BSRR = minute_polarity ? 2u : 4u;
        minute_polarity ^= 1u;
        minute_active = 1u;
        pwm_min_phase = 2u;
        minute_end = parallel_log[4] + 4u;
        /* A rise may wait for clock housekeeping; never subtract that delay
         * from its powered width. Subsequent gaps retain the same profile. */
        MT(0x34u) = (MT(0x24u) + fine_min_width) & 65535u;
    }
    else if (pwm_min_phase == 2u && minute_active)
    {
        GPIOB_BSRR = 6u << 16;
        minute_active = 0u;
        ++parallel_log[13];
        if (++fine_minute_steps == 6u)
        {
            fine_minute_steps = 0u;
            parallel_log[22] = (parallel_log[22] + 1u) % 720u;
        }
        if (request_pulses)
            --request_pulses;
        if (request_pulses && parallel_log[2] != 14u)
        {
            pwm_min_phase = 1u;
            MT(0x34u) = (deadline + fine_min_period - fine_min_width) & 65535u;
        }
        else
        {
            pwm_min_phase = 0u;
            MT(0x0cu) = 0u;
        }
    }
    else
    {
        pwm_min_phase = 0u;
        MT(0x0cu) = 0u;
    }
    motor_guard_kick();
}
/* Only change settings after a delivered pulse, in a gap low under BOTH
 * old and new compare thresholds. A delayed notification defers a change;
 * it cannot truncate a pulse or emit catch-up edges. */
static __attribute__((noinline)) void pwm_ramp_service(void)
{
    if (!pwm_ramp_active || !fine_hold_seconds || pwm_draining || !pwm_running())
    {
        pwm_ramp_active=0u; FT(0x0cu)&=~16u; return;
    }
    if (FT(0x08u)!=MM32_TIMER_STANDALONE_SMCR || BT(0x08u)!=MM32_PULSE_COUNTER_SMCR)
    {
        pwm_fault_snapshot(10u); fail(10u); return;
    }
    uint32_t seen=BT(0x24u)&65535u;
    if (seen==pwm_ramp_last) return;
    uint32_t step=pwm_ramp_step+1u;
    if (step>32u || seen>64u || !pwm_fixed_period || pwm_ramp_normal<pwm_fixed_period)
    {
        pwm_fault_snapshot(11u); fail(10u); return;
    }
    uint32_t period=pwm_ramp_normal-((pwm_ramp_normal-pwm_fixed_period)*step)/32u;
    uint32_t width=pwm_ramp_width(period), low=width/2u, high=period-low;
    uint32_t old_low=fine_sec_width/2u, old_high=fine_period-old_low;
    uint32_t lower=low>old_low?low:old_low, upper=high<old_high?high:old_high;
    uint32_t middle=period/2u, old_middle=fine_period/2u;
    uint32_t irq;
    __asm volatile("mrs %0, primask\n cpsid i":"=r"(irq)::"memory");
    uint32_t count=FT(0x24u), down=FT(0)&16u;
    if (down ? (count>lower+128u && count+128u<middle && count+128u<old_middle) :
               (count>middle+128u && count>old_middle+128u && count+128u<upper))
    {
        uint32_t a_mode=(FT(0x18u)>>12)&7u;
        FT(0x2cu)=period;
        FT(0x38u)=a_mode==6u?low:high;
        FT(0x3cu)=a_mode==6u?high:low;
        FT(0x34u)=middle;
        fine_period=period; fine_sec_width=width;
        pwm_ramp_step=step; pwm_ramp_last=seen; ++pwm_ramp_updates;
        if (step==32u) { pwm_ramp_active=0u; FT(0x0cu)&=~16u; }
    }
    if (pwm_ramp_active)
    {
        uint32_t lo=fine_sec_width/2u, mid=fine_period/2u, hi=fine_period-lo;
        /* Opposite next direction: after its pulse-count compare, so one
         * notice per complete delivered pulse, never per blank hold cycle. */
        FT(0x40u)=down ? mid+(hi-mid)/2u : lo+(mid-lo)/2u;
    }
    __asm volatile("msr primask, %0"::"r"(irq):"memory");
}
static __attribute__((noinline)) void pwm_update_normal_rate(void)
{
    if (pwm_resume_pending || pwm_ramp_active)
        return; /* CC4 belongs to the pending safe output release. */
    if (fine_hold_seconds || !seconds_log[54] || pwm_draining ||
        BT(0x2cu) != 959u || !pwm_running())
    {
        FT(0x0cu) &= ~16u;
        return;
    }
    uint32_t cycles = (rtc_pace[1] + 1u) * 1024u + release_state[1];
    uint32_t period = (cycles + 1024u) / 2048u;
    uint32_t width = 2u * ((cycles * 3u + 8192u) / 16384u);
    uint32_t low = width / 2u, high = period - low;
    uint32_t old_low = fine_sec_width / 2u, old_high = fine_period - old_low;
    uint32_t middle = period / 2u, old_middle = fine_period / 2u;
    uint32_t lower = low > old_low ? low : old_low;
    uint32_t upper = high < old_high ? high : old_high;
    uint32_t margin = 128u; /* 256 us nominal: no edge/compare during writes. */
    if (period > 65535u || !low || low >= high)
    {
        pwm_fault_snapshot(6u);
        fail(10u);
        return;
    }
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    uint32_t count = FT(0x24u), down = FT(0) & 16u;
    /* Already PAST both old/new count compares in this released gap. Moving
     * CCR1 cannot count this gap twice or omit its next completed pulse.
     * Both outputs must remain low under BOTH old/new compare thresholds. */
    if (down ? !(count > lower + margin &&
                 count + margin < middle && count + margin < old_middle) :
               !(count > middle + margin && count > old_middle + margin &&
                 count + margin < upper))
    {
        /* The 128 Hz sampler can phase-lock to a gap boundary. Request a
         * calibration-only CC4 notification within the released gap. No
         * edge or pulse count depends on its timely delivery. */
        FT(0x40u) = old_middle + (old_middle - old_low) / 2u;
        FT(0x10u) = ~16u;
        FT(0x0cu) |= 16u;
        __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
        return;
    }
    FT(0x0cu) &= ~16u;
    uint32_t a_mode = (FT(0x18u) >> 12) & 7u;
    FT(0x2cu) = period;
    FT(0x38u) = a_mode == 6u ? low : high;
    FT(0x3cu) = a_mode == 6u ? high : low;
    FT(0x34u) = middle;
    fine_period = period;
    fine_sec_width = width;
    if (!pwm_min_phase)
    {
        fine_min_period = period;
        fine_min_width = (period + 1u) / 2u;
    }
    seconds_log[54] = 0u;
    ++seconds_log[55];
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
}
static void pwm_poll(uint32_t tick)
{
    if (!fine_enabled || !parallel_log[1] || parallel_log[2] == 6u)
        return;
    if (!pwm_launch_pending &&
        (!(FT(0) & 1u) || FT(0x08u) != MM32_TIMER_STANDALONE_SMCR ||
         BT(0x08u) != MM32_PULSE_COUNTER_SMCR ||
         (FT(0x20u) && FT(0x20u) != 0x110u) ||
         (FT(0x20u) == 0x110u && !GD(0x04u))))
    {
        pwm_fault_snapshot(8u);
        fail(10u);
        return;
    }
    if (pwm_resume_pending)
    {
        if (tick - pwm_resume_tick > 128u)
        {
            pwm_fault_snapshot(9u);
            fail(10u);
            return;
        }
        /* TIM3 CC4 alone commits a warm release; polling only supervises. */
    }
    uint32_t count = BT(0x24u) & 65535u;
    if (pwm_ramp_active && count>64u)
    {
        pwm_fault_snapshot(11u); fail(10u); return;
    }
    if (!pwm_launch_pending && !FT(0x20u))
    {
        if (GD(0x04u) || !(REG32(0x40020000u) & 0x20u))
        {
            pwm_fault_snapshot(8u);
            fail(10u);
            return;
        }
        /* DMA has removed motor drive. Internal blank cycles must never
         * advance hand position, even across a debugger/overnight delay. */
        BT(0) = 0u;
        count = BT(0x34u);
    }
    uint32_t delta = !fine_hold_seconds ?
        (count + 960u - pwm_seen) % 960u : count - pwm_seen;
    uint32_t elapsed = tick - seconds_log[53];
    seconds_log[53] = tick;
    if (elapsed > seconds_log[48])
        seconds_log[48] = elapsed;
    if (delta > seconds_log[51])
        seconds_log[51] = delta;
    /* 128 Hz observation versus ~16.65 Hz complete pulses. A complete pulse
     * cannot normally be missed. Stop on a real sampling outage rather than
     * fabricating sensor histories. Compare flags are irrelevant. */
    if (delta > 1u || count > BT(0x34u) ||
        (elapsed > 2u && pwm_running()))
    {
        pwm_fault_snapshot(delta > 1u || count > BT(0x34u) ? 1u : 5u);
        fail(10u);
        return;
    }
    if (delta)
    {
        ++seconds_log[49];
        pwm_seen = count;
        second_polarity ^= 1u;
        ++parallel_log[12];
        if (!minute_log[229] && !fine_hold_seconds && pwm_draining)
        {
            /* Deliberately aborted continuous lap: retain electrical position
             * for safe parking, but do not demand a new optical qualification
             * from a partial lap (including a drain across counter wrap). */
            ++seconds_log[248];
            parallel_log[30] = 0u;
        }
        else if (!minute_log[229])
        {
            uint32_t result = parallel_seconds_runtime_done(second_highs);
            if (result == 2u)
            {
                fail(5u);
                return;
            }
            if (result == 1u)
            {
                audit_seconds_reference();
                parallel_log[31] = seconds_log[254] - 960u;
                if (!fine_hold_seconds && !pwm_draining && BT(0x2cu) == 959u)
                {
                    /* Electrical phase keeps running, including across 00.
                     * Only optical tracking resets for the next revolution. */
                    parallel_seconds_runtime_begin();
                    ++fine_laps;
                    seconds_log[54] = 1u;
                }
                else
                    parallel_log[30] = 1u;
            }
        }
        second_highs = 0u;
    }
    pwm_watchdog(tick);
    if (parallel_log[2] == 6u)
        return;
    /* Finalise the previous pulse BEFORE sampling the next. Reject only a
     * sample straddling a hardware-count boundary, not the pulse itself. */
    second_active = pwm_powered();
    uint32_t high = (B_IDR >> 14) & 1u;
    if (pwm_running() && (BT(0x24u) & 65535u) != count)
        ++seconds_log[52];
    else if (second_active && audit_seconds_ready(tick))
        second_highs += high;
    pwm_update_normal_rate();
}

void DMA1_Channel2_3_Handler(void)
{
    SLEEP_IRQ_NOTE();
    pwm_fault_snapshot(8u);
    fail(10u); /* Only transfer errors are enabled; never resume after one. */
}
static void pwm_watchdog(uint32_t tick)
{
    if (!pwm_running())
        return;
    uint32_t count = BT(0x24u) & 65535u;
    if (count != pwm_watch_count)
    {
        pwm_watch_count = count;
        pwm_watch_tick = tick;
    }
    else if (tick - pwm_watch_tick > 16u)
    {
        pwm_fault_snapshot(3u);
        fail(10u); /* Independent SysTick coil-off supervision. */
    }
}
