/* All runtime modes use autonomous_stop2go.h. Coarse motion is retained
 * for homing and fault parking, not as an alternative runtime pulse engine.
 * TIM3/SysTick retain equal priority; UART retains higher priority.
 */
#define FT(o) REG32(0x40000400u + (o))
#define fine_period minute_log[181]
#define fine_sec_width minute_log[182]
#define fine_min_width minute_log[183]
#define fine_min_period minute_log[184]
#define fine_laps minute_log[185]
#define fine_boundary minute_log[187]
#define fine_handover_tick release_state[5]
#define pwm_seen seconds_log[219]
#define pwm_draining seconds_log[220]
#define pwm_launch_pending seconds_log[60] /* Initialised, no waveform launched yet. */
/* Former fractional-scheduler words now belong exclusively to PWM. */
#define pwm_min_phase release_state[2]
#define pwm_watch_count release_state[3]
#define pwm_watch_tick release_state[4]
static uint32_t pwm_running(void);
static uint32_t pwm_powered(void);
#include "rtc_reference_state.h"
#include "reference_audit.h"
#include "autonomous_stop2go.h"

static void fine_stop(void)
{
    if (pwm_engine)
    {
        pwm_stop();
        return;
    }
    if (!fine_enabled)
        return;
    ++motor_timer_epoch;
    FT(0x0cu) = 0u;
    FT(0x00u) = 0u;
    FT(0x10u) = 0u;
    REG32(0xe000e280u) = 1u << 16;
    fine_enabled = 0u;
    motor_guard_kick();
}

static uint32_t fine_init(void)
{
    uint32_t ready = pwm_init();
    if (ready)
        pwm_launch_pending = 1u;
    return ready;
}

/* Runtime requests only queue work. Never launch a minute edge from SysTick. */
static void fine_minutes_rise(uint32_t deadline)
{
    if (pwm_engine)
        pwm_minutes_queue();
    (void)deadline;
}

static void fine_start_runtime(void)
{
    if (pwm_engine)
    {
        if (!parallel_log[30] && !minute_log[229])
        {
            pwm_launch();
            pwm_launch_pending = 0u;
        }
        if (parallel_log[2] == 7u && request_pulses)
            pwm_minutes_queue();
        return;
    }
}

static void fine_motor_irq_body(void)
{
    if (pwm_engine)
    {
        if (FT(0x10u) & FT(0x0cu) & 16u)
        {
            FT(0x10u) = ~16u;
            if (pwm_resume_pending)
                pwm_try_resume();
            else if (pwm_ramp_active)
                pwm_ramp_service();
            else
                pwm_update_normal_rate();
        }
        FT(0x10u) = ~2u; /* No CC1 bookkeeping IRQ is enabled in PWM. */
        return;
    }
}

void TIM3_Handler(void)
{
    fine_motor_irq_body();
    motor_guard_kick();
}

static void fine_runtime_tick(uint32_t tick, uint32_t stage, uint32_t boundary)
{
    if (pwm_engine)
    {
        second_active = pwm_powered();
        if (parallel_log[2] == 6u)
            return;
    }
    audit_tick(tick, stage);
    if (daily_log[13] == 2u)
        return;
    if (!pwm_engine && second_active && audit_seconds_ready(tick))
        second_highs += (B_IDR >> 14) & 1u;
    /* Homing-complete acquisition can release seconds before minute catch-up
     * finishes. Apply the same parking policy there, not only in stage 7.
     * Correction ownership is still checked below before any release. */
    uint32_t homed_catchup = (stage == 10u || stage == 11u) &&
                             parallel_log[7] && parallel_log[8];
    uint32_t night_hold = (stage == 7u || homed_catchup) && (fine_night_enabled == 2u ||
                                          (fine_night_enabled == 1u && parallel_log[16] < 6u));
    /* Scheduled overnight startup uses the normal first revolution.
     * After its first qualified 960-pulse lap, park the configured waveform
     * until 06:00. Permanent parking keeps its immediate-startup behaviour. */
    uint32_t first_overnight_lap = fine_night_enabled == 1u &&
                                   seconds_log[255] == 0u;
    if (night_hold && !fine_enabled && !second_active && !first_overnight_lap)
        parallel_log[30] = 1u;
    fine_night_parked = night_hold && parallel_log[30];
    /* Continuous modes count modulo 960 without stopping the waveform.
     * Extend ARR before the next wrap when a boundary-safe hold is needed;
     * CCR1=960 then triggers DMA output-disable at that completed pulse;
     * the seconds waveform timer remains continuously running. */
    if (pwm_engine && !fine_hold_seconds && pwm_running() &&
        ((daily_log[13] && !(correction_seconds_independent && daily_log[13] == 3u)) || night_hold ||
         (fine_night_enabled == 1u && parallel_log[16] == 23u &&
          parallel_log[15] == 59u && parallel_log[5] >= 58u)))
        BT(0x2cu) = 65535u;
    /* Remember every RTC boundary, even while seconds are still approaching
     * their reference. A late handover may put the following 58-second lap
     * just beyond :00; do not lose that edge and wait a whole minute.
     * The bounded grace uses unsigned subtraction, including tick wrap. */
    if (boundary)
    {
        fine_boundary = 1u;
        fine_handover_tick = tick;
    }
    if (tick - fine_handover_tick > 384u)
        fine_boundary = 0u;
    /* A correction must never use the ordinary late-reference grace to
     * start a parked hand at :01/:02. This owner survives minute catch-up;
     * an unusable :00 must wait for the following corrected minute. */
    if (correction_seconds_boundary_wait && parallel_log[5] != 0u)
        fine_boundary = 0u;
    /* Minute boundaries queue work even if seconds reach their reference late.
     * Actual minute edges belong exclusively to shared phase 1. */
    if (stage == 7u && !daily_log[13] && !minute_active && !request_pulses)
    {
        uint32_t distance = (clock_minute() + 720u - parallel_log[22]) % 720u;
        if (distance > 1u)
        {
            fail(9u);
            return;
        }
        if (fine_sweep_minutes)
        {
            uint32_t target = parallel_log[5] / 10u;
            if (distance == 1u && parallel_log[5] == 0u)
                request_pulses = 6u - fine_minute_steps;
            else if (!distance && target > fine_minute_steps)
                request_pulses = target - fine_minute_steps;
        }
        else if (boundary && distance && (!parallel_log[30] || night_hold))
            request_pulses = 6u;
        if (fine_enabled && request_pulses)
            fine_minutes_rise(FT(0x24u) & 65535u);
    }
    if (parallel_log[30])
    {
        if (stage == 7u && daily_log[13] == 1u && fine_minute_steps && !minute_active &&
            !request_pulses)
        {
            request_pulses = 6u - fine_minute_steps;
            fine_minutes_rise(FT(0x24u) & 65535u);
        }
        if (boundary)
            fine_boundary = 1u;
        /* Keep the minute timer and UART/scheduler alive while seconds park.
         * Pending corrections still own the mechanism; never bypass them. */
        if (night_hold && daily_log[13] != 1u && daily_log[13] != 2u)
        {
            goto fine_timer;
        }
        /* No minute advance at :58. A fresh :00 authorises the shared grid. */
        /* An exact corrected :00 can already have its minute marker queued
         * by stage 11. With no minute phase armed, launch that marker beside
         * the preserved seconds release below, just like an ordinary :00.
         * Already armed/powered minute work must still finish first. */
        if (daily_log[13] == 1u || daily_log[13] == 2u || !fine_boundary ||
            (minute_active && (!correction_seconds_independent || pwm_min_phase == 2u)) ||
            (request_pulses && !(pwm_engine && !pwm_min_phase)))
            return;
        if (stage == 7u)
        {
            uint32_t distance = (clock_minute() + 720u - parallel_log[22]) % 720u;
            if (distance > 1u)
            {
                fail(9u);
                return;
            }
            if (distance)
            {
                request_pulses = 6u - fine_minute_steps;
            }
        }
        parallel_seconds_runtime_begin();
        parallel_log[30] = 0u;
        /* RC6AH preserves the continuously running waveform and requests
         * output release in a safe up-counting gap. Rehoming/initial launch
         * still use the established full configuration. No active drive is
         * interrupted; already-armed minute work was drained above. */
        if (fine_enabled && (stage == 7u || (homed_catchup && !pwm_draining)) &&
            (fine_hold_seconds || (pwm_engine && !pwm_draining)) &&
            (!daily_log[13] || (correction_seconds_independent && daily_log[13] == 3u)) &&
            !second_active)
        {
            pwm_min_phase = 0u; /* No powered minute pulse can reach this path. */
            /* Safe restart after both old falls; seconds counts stay fixed. */
            fine_boundary = 0u;
            correction_seconds_boundary_wait = 0u;
            ++fine_laps;
            if (pwm_engine)
            {
                /* Starting already parked has initialised the minute timer,
                 * but no seconds waveform has run yet. Launch it once; only
                 * a genuinely frozen waveform may use phase resume. */
                if (pwm_launch_pending)
                {
                    pwm_launch();
                    pwm_launch_pending = 0u;
                }
                else
                    pwm_resume_lap();
                if (request_pulses)
                    pwm_minutes_queue();
            }
            /* Release on the next existing phase-0 deadline. */
            return;
        }
        fine_stop();
    }
fine_timer:
    if (!fine_enabled)
    {
        fine_boundary = 0u;
        if (!fine_init())
            return;
        pwm_min_phase = 0u;
        /* The shared cycle establishes all widths and deadlines together. */
        ++fine_laps;
        FT(0x10u) = 0u;
        fine_start_runtime();
    }
    else if (stage == 7u && request_pulses && !minute_active &&
             (pwm_engine || !(FT(0x0cu) & 8u)))
    {
        fine_minutes_rise(FT(0x24u) & 65535u);
    }
    (void)tick;
}

static void fine_seconds_drain(void)
{
    if (pwm_engine)
        pwm_drain();
    else
        FT(0x0cu) &= ~2u;
}
static void fine_motion_drain(void)
{
    if (pwm_engine)
    {
        pwm_drain();
        if (pwm_min_phase != 2u)
        {
            MT(0x0cu) = 0u;
            pwm_min_phase = 0u;
        }
    }
    else
        FT(0x0cu) &= 20u;
}
static uint32_t fine_motion_pending(void)
{
    return minute_active || (pwm_engine ? pwm_running() : second_active);
}
