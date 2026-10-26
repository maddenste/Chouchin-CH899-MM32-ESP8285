/* MM32 release candidate: independent homing, RTC-disciplined motor timing,
 * selectable movement, daily wake, overnight parking and safe latched faults.
 * RC6P uses hardware seconds PWM in all runtime modes. */
#define UART_BASE 0x40004400u
#include "movement_api.h"
_Static_assert(sizeof(Mm32UartEvent) == 20u, "TIME event ABI must not grow");
#define SLEEP_IRQ_NOTE() (++seconds_log[213])
#include "alignment_calibration.h"
#include "uart_transport.h"
#include "timer_errata.h"

/* Operational state shares reserved SRAM; mode-control addresses stay stable. */
#define release_state (seconds_log + 228u)

#define A_CRL REG32(0x48000000u)
#define A_BSRR REG32(0x48000010u)
#define B_CRH REG32(0x48000404u)
#define B_IDR REG32(0x48000408u)
#define PAIR ((1u << 13) | (1u << 15))
#define PAIR_MODES ((15u << 20) | (15u << 28))
/* 0 signature,1 command(1 start,0 abort),2 stage(1 home,4 wait00,
 * 7 run,5 finished,6 fault),3 fault,4 ticks,5 software second,
 * 6 clock valid,7 minute aligned,8 seconds aligned,9 release tick,
 * 10 seconds parked tick,11 minutes parked tick,12 run seconds pulses,
 * 13 run minute pulses,14 clock phase,15 software minute,16 software hour.
 * 17 last valid TIME count,18 first motor frame,19 selected sensor(1sec/2min),
 * 20 minute electrical pulses,21 homing seconds pulses.
 * Stages 10 catch-up / 11 wait00 use words:
 * 22 physical minute position modulo720,23 catch-up electrical pulses,
 * 24 catch-up target minute,25 catch-up start tick.
 * Word26 is the seconds-released flag and word27 is the minute
 * catch-up-ready tick. Word9 always retains the FIRST seconds release tick.
 * Initial time acquisition timeout 300s; minute search <=740 advances;
 * seconds <=1100 pulses. See README.md for the complete fault-code table. */
volatile uint32_t parallel_log[32];
#include "cpu_sleep.h"
static uint32_t used, frame, minute_due, minute_active, second_active;
static uint32_t second_highs, minute_polarity = 1u, second_polarity;
static uint32_t request_pulses, fine_pulses, dwell_fraction;
#define fine_enabled minute_log[180]
#define pwm_engine seconds_log[218]
#define alignment_pending minute_log[203]  /* bit0 minute, bit1 seconds */
#define alignment_recovery minute_log[204] /* 1 scheduled, 2 draining, 3 homing */
#define mode_latched minute_log[188]
#define fine_mode_active minute_log[189]
#define mode_restart_state minute_log[190] /* 0 idle,1 drain,2 ESP off,3 reset */
#define mode_restart_tick seconds_log[59]
#define fine_minute_steps minute_log[191]
#define fine_night_enabled minute_log[192]
#define fine_night_parked minute_log[193]
#define fine_settings_count minute_log[194]
#define fine_hold_seconds (fine_mode_active & 2u)
#define fine_sweep_minutes (!(fine_mode_active & 1u))
void parallel_uart_settings(const Mm32UartEvent *event)
{
    uint32_t irq_mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(irq_mask)::"memory");
    /* Settings are independent of the immutable, in-flight time snapshot. */
    if (daily_log[10] != event->scheduled_hour || daily_log[11] != event->scheduled_minute)
    {
        daily_log[10] = event->scheduled_hour;
        daily_log[11] = event->scheduled_minute;
        daily_log[3] = 0u;
    }
    if (!mode_latched && !event->settings_present && !minute_log[229] &&
        parallel_log[2] != 6u)
    {
        fine_mode_active = 0u; /* Legacy TIME without style uses the default. */
        mode_latched = 1u;
    }
    if (event->settings_present && event->movement_mode <= 3u && event->night_parking <= 2u &&
        !minute_log[229] && parallel_log[2] != 6u)
    {
        if (!mode_latched)
        {
            fine_mode_active = event->movement_mode;
            fine_night_enabled = event->night_parking;
            mode_latched = 1u;
        }
        else if ((event->movement_mode != fine_mode_active ||
                  event->night_parking != fine_night_enabled) && !mode_restart_state)
        {
            mode_restart_tick = parallel_log[4];
            mode_restart_state = 1u;
        }
        ++fine_settings_count;
    }
    __asm volatile("msr primask, %0" ::"r"(irq_mask) : "memory");
}
static void fine_stop(void);
static void pwm_fault_snapshot(uint32_t reason);
static void fine_seconds_drain(void);
static void fine_motion_drain(void);
static uint32_t fine_motion_pending(void);
static void motor_guard_kick(void);
/* Former unused sleep telemetry; functional scheduler state, not profiling.
 * These words do not change the established mode-control RAM addresses. */
#define motor_tick_pending seconds_log[214]
#define motor_timer_epoch seconds_log[215]
static void fine_runtime_tick(uint32_t tick, uint32_t stage, uint32_t boundary);
static uint32_t minute_fine, minute_end, next_user = 256u, tx_index = 5u;
/* Unused telemetry words: preserve Trial41 command address and stack headroom. */
#define manual_web_active (minute_log[217])
#define manual_web_deadline (minute_log[218])
#define manual_web_tick_seen (minute_log[219])
static void manual_web_poll(void);
static void runtime_time_poll(void);
/* Reserved parallel telemetry; no new globals or RAM-layout changes. */
#define esp_response_tick (minute_log[210])
#define esp_awake (minute_log[211])
#define esp_time_received (minute_log[212])
#define independent_catchup (minute_log[213])
/* Motor-local reference words, cleared on every new/recovery homing. */
#define minute_home_settle_due (minute_log[251])
#define minute_home_settling (minute_log[252])
#define seconds_home_settle_due (minute_log[254])
#define seconds_home_settling (minute_log[255])
#define HOME_SETTLE_TICKS 128u /* One nominal second after the final coil release. */
/* Authorized backward correction: wait for the clock, never wrap the dial. */
#define correction_wait_ahead (minute_log[207])
#define schedule_time_seen (minute_log[208])
#define rtc_read_recoveries (minute_log[209])
#define rtc_good_read_tick (minute_log[214])
#define rtc_failed_batches (minute_log[215])
#define rtc_read_reason (minute_log[216])
volatile uint32_t rtc_pace[16];
static uint32_t rtc_last, rtc_poll_tick, rtc_window_cycles;
static volatile uint32_t rtc_edge_tick, rtc_boundary;
static uint32_t rtc_clock_seeded;
/* pace: 0 cycles,1 reload,2 edges,3 window edges,4 ready,5 reads,
 * 6 failures,7 last RTC seconds-of-day,8 last edge tick. */
static void rtc_pace_poll(void);
static void quartz_poll(void);
static void rtc_window_tick(uint32_t tick);
static void rtc_window_reset(uint32_t stamp, uint32_t tick);
volatile uint32_t daily_log[16];
/* Independent deadline: receipt epoch still ages TIME across acquisition. */
static uint32_t correction_runtime_started, correction_runtime_stamp;
#define correction_boundary_due minute_log[150] /* Runtime deadline; zero at startup. */
#define correction_seconds_independent minute_log[151]
#define correction_seconds_boundary_wait minute_log[152]
#define correction_urgent minute_log[MM32_CORRECTION_URGENT] /* 0 ordinary,1 safe drain,2 released. */
static void daily_poll(void);
/* Preserve the fractional part while ageing an ordinary whole-second TIME.
 * No fractional UART field or timer/PWM reconfiguration is needed. */
static uint32_t time_age(Mm32UartEvent *e, uint32_t *origin)
{
    uint32_t seconds = (parallel_log[4] - *origin) / 128u;
    if (!rtc_event_advance(e, seconds))
        return 0u;
    *origin += seconds * 128u;
    return 1u;
}
static uint32_t time_publish(Mm32UartEvent *e, uint32_t origin)
{
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    if (!time_age(e, &origin))
    {
        __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
        return 0u;
    }
    uint32_t tick = parallel_log[4], stamp = rtc_event_stamp(e);
    rtc_clock_seeded = 1u;
    rtc_last = stamp % 86400u;
    rtc_edge_tick = origin;
    rtc_poll_tick = rtc_good_read_tick = tick;
    rtc_window_reset(stamp, tick);
    rtc_window_cycles = rtc_pace[0];
    rtc_failed_batches = 0u;
    rtc_pace[2] = rtc_pace[3] = 0u;
    rtc_pace[7] = rtc_last;
    rtc_pace[8] = origin;
    parallel_log[5] = e->second;
    parallel_log[15] = e->minute;
    parallel_log[16] = e->hour;
    rtc_boundary = (e->second == 0u && tick - origin <= 4u);
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
    return 1u;
}
static __attribute__((noinline)) void pending_time_poll(void)
{
    if (!(pending_time_meta & PENDING_TIME_VALID) || parallel_log[2] != 7u ||
        !parallel_log[6] ||
        /* An open session waiting for its first published TIME may consume
         * a record retained during catch-up. Do not replace a published
         * record that daily_poll has not yet frozen/processed. */
        (daily_log[0] == 2u && uart_probe_good_time != daily_log[5]) ||
        daily_log[0] == 7u || daily_log[13] ||
        mode_restart_state || alignment_recovery || minute_log[229] || minute_log[230])
        return;
    Mm32UartEvent e = {0};
    e.year = pending_time_date & 65535u;
    e.utc_offset_minutes = (int16_t)(pending_time_date >> 16);
    e.month = pending_time_clock & 255u;
    e.day = (pending_time_clock >> 8) & 255u;
    e.hour = (pending_time_clock >> 16) & 255u;
    e.minute = pending_time_clock >> 24;
    e.second = pending_time_meta & 255u;
    e.dst_pending = (pending_time_meta >> 8) & 1u;
    e.scheduled_hour = (pending_time_meta >> 16) & 255u;
    e.scheduled_minute = (pending_time_meta >> 24) & 127u;
    e.kind = MM32_UART_TIME;
    /* Age by monotonic ticks, not the RTC which may have just changed. */
    uint32_t origin = pending_time_tick;
    if (!time_age(&e, &origin))
        return; /* Keep the record pending rather than acknowledge-and-drop. */
    pending_time_meta = 0u;
    published_time_tick = origin; /* Keep the fractional remainder. */
    uart_probe_time_event = e;
    ++uart_probe_good_time;
    uint32_t received = rtc_event_stamp(&e), now = seconds_log[227];
    if ((received > now ? received - now : now - received) <= 2u)
    {
        if (!time_publish(&e, origin))
            return;
        schedule_time_seen = uart_probe_good_time;
        return; /* Catch-up retries already matching the clock need no hold. */
    }
    daily_log[0] = 2u;
    daily_log[4] = parallel_log[4];
    daily_log[14] = seconds_log[227];
    daily_log[5] = uart_probe_good_time - 1u;
    daily_log[15] = uart_probe_uart_errors;
}
/* Confirmation means validated TIME/settings processed, not RTC correction
 * or homing completed. Prefix LF terminates any partial USER request, then
 * echo the exact accepted record including its original line ending.
 * No IRQ masking, motor writes, extra line buffer or unbounded UART wait. */
static __attribute__((noinline)) void uart_time_echo(void)
{
    uint32_t start = parallel_log[4], budget = 65536u;
    uint32_t index = 0u;
    tx_index = 5u; /* Cancel a partial USER; its normal retry can start afresh. */
    for (;;)
    {
        if (!esp_awake || parallel_log[2] == 6u || parallel_log[2] == 14u ||
            minute_log[229] || minute_log[230])
            return;
        /* MM32SPIN05x_q SVD UART CSR TXEPT is bit0. Do not use the
         * incompatible SPIN06 header's bit3 (RXAVL_4BYTE on this chip). */
        while (!(UART1_CSR & 1u))
        {
            if (!--budget || parallel_log[4] - start >= 4u ||
                !esp_awake || parallel_log[2] == 6u || parallel_log[2] == 14u ||
                minute_log[229] || minute_log[230])
                return;
        }
        if (index > line_length)
            return;
        REG32(UART_BASE) = index ? line[index - 1u] : (uint8_t)'\n';
        ++index;
    }
}
static void daily_schedule(uint32_t now);
static uint32_t runtime_end;
static void fail(uint32_t code);
static void motors_off(void);
static void radio_off(void);
#define fault_tick_due release_state[6]
#define fault_start_tick release_state[7]
#define fault_seconds_left release_state[8]
#define fault_minutes_left release_state[9]
#define fault_drain release_state[10]
static void fault_shutdown(void)
{
    motors_off();
    radio_off();
    parallel_leds_off();
    REG32(0xe000e010u) = 0u; /* SysTick disabled: no periodic wake. */
    REG32(0xe000e180u) = 0xffffffffu;
    REG32(0xe000e280u) = 0xffffffffu;
    REG32(0xe000ed04u) = (1u << 25) | (1u << 27); /* clear SysTick/PendSV */
    REG32(0x4002101cu) &= ~2u;                    /* TIM3 peripheral clock off */
    parallel_log[1] = 0u;
    parallel_log[2] = 6u;
    release_state[0] = 2u; /* latched stop; reset is the only exit */
    /* Diagnostic-only wake: no RTC, buttons, UART or motor processing.
     * Nominal 128 Hz at 8 MHz, independent of failed RTC calibration. */
    parallel_leds_fault_start(parallel_log[4]);
    REG32(0xe000e014u) = 62499u;
    REG32(0xe000e018u) = 0u;
    REG32(0xe000e010u) = 7u;
}
static void fault_park_tick(uint32_t tick)
{
    if (tick - fault_start_tick > 76800u)
    {
        fault_shutdown();
        return;
    }
    if (fault_drain)
    {
        if (fine_motion_pending())
            return;
        fine_stop();
        request_pulses = 0u;
        fault_seconds_left =
            (480u + 960u - (parallel_log[30] ? 0u : seconds_log[248] % 960u)) % 960u;
        fault_minutes_left = (660u + 4320u - (parallel_log[22] * 6u + fine_minute_steps)) % 4320u;
        fault_drain = 0u;
        fault_tick_due = tick;
        A_CRL = (A_CRL & ~(15u << 28)) | (1u << 28);
        GPIOB_CRL = (GPIOB_CRL & ~0xfffu) | 0x221u;
        B_CRH = (B_CRH & ~PAIR_MODES) | (4u << 20) | (4u << 28);
    }
    if (second_active && (int32_t)(tick - runtime_end) >= 0)
    {
        A_BSRR = 1u << 23;
        GPIOB_BSRR = 1u << 16;
        second_active = 0u;
        --fault_seconds_left;
    }
    if (minute_active && (int32_t)(tick - minute_end) >= 0)
    {
        GPIOB_BSRR = 6u << 16;
        minute_active = 0u;
        --fault_minutes_left;
    }
    if (!fault_seconds_left && !fault_minutes_left)
    {
        fault_shutdown();
        return;
    }
    if ((int32_t)(tick - fault_tick_due) < 0)
        return;
    if (fault_seconds_left && !second_active)
    {
        if (!second_polarity)
            GPIOB_BSRR = 1u;
        else
            A_BSRR = 1u << 7;
        second_polarity ^= 1u;
        second_active = 1u;
        runtime_end = tick + 6u;
    }
    if (fault_minutes_left && !minute_active)
    {
        GPIOB_BSRR = minute_polarity ? 2u : 4u;
        minute_polarity ^= 1u;
        minute_active = 1u;
        minute_end = tick + 4u;
    }
    fault_tick_due = tick + 8u;
}
static uint32_t catchup_pulses;
static uint32_t clock_minute(void)
{
    return (parallel_log[16] % 12u) * 60u + parallel_log[15];
}
static void catchup_begin(uint32_t tick)
{
    if (parallel_log[2] != 1u)
        parallel_log[2] = 10u;
    independent_catchup = 1u;
    parallel_log[25] = tick;
    minute_due = tick + 1u;
    catchup_pulses = 0u;
    /* Seconds can already be running autonomously during initial catch-up.
     * Never steal PA7/PB0 from their timer while configuring minute pins. */
    if (!pwm_engine)
    {
        A_CRL = (A_CRL & ~(15u << 28)) | (1u << 28);
        GPIOB_CRL = (GPIOB_CRL & ~0xFFFu) | 0x221u;
    }
    else
        GPIOB_CRL = (GPIOB_CRL & ~0xFF0u) | 0x220u;
}
static uint32_t minute_home_ready(uint32_t tick)
{
    if (minute_home_settling && (int32_t)(tick - minute_home_settle_due) < 0)
        return 0u;
    minute_home_settling = 0u;
    return 1u;
}
static uint32_t seconds_home_ready(uint32_t tick)
{
    if (seconds_home_settling && (int32_t)(tick - seconds_home_settle_due) < 0)
        return 0u;
    seconds_home_settling = 0u;
    return 1u;
}
static void catchup_tick(uint32_t tick)
{
    /* Do not discard the released dwell of the final slow homing pulse
     * when catchup_begin replaces its ordinary scheduling deadline. */
    if (!minute_home_ready(tick))
        return;
    parallel_log[24] = clock_minute();
    if (tick - parallel_log[25] > 46080u)
    {
        fail(7u);
        return;
    }
    if (minute_active != 0u && tick == minute_end)
    {
        GPIOB_BSRR = 6u << 16;
        minute_active = 0u;
        ++parallel_log[23];
        if (++catchup_pulses == 6u)
        {
            catchup_pulses = 0u;
            parallel_log[22] = (parallel_log[22] + 1u) % 720u;
        }
    }
    if (minute_active == 0u && catchup_pulses == 0u &&
        (parallel_log[22] == parallel_log[24] ||
         (daily_log[13] == 3u &&
          (parallel_log[22] == (parallel_log[24] + 1u) % 720u || correction_wait_ahead))))
    {
        /* Catch-up must never truncate an independently running second pulse. */
        GPIOB_BSRR = 6u << 16;
        GPIOB_CRL = (GPIOB_CRL & ~0xFF0u) | 0x440u;
        if (parallel_log[2] != 1u)
        {
            GPIOB_BSRR = PAIR << 16;
            if (parallel_log[26])
            {
                B_CRH = (B_CRH & ~PAIR_MODES) | (2u << 20) | (2u << 28);
                GPIOB_BSRR = 1u << 13; /* Keep the runtime seconds reference enabled. */
            }
            else
                B_CRH = (B_CRH & ~PAIR_MODES) | (4u << 20) | (4u << 28);
            parallel_log[19] = 0u;
        }
        parallel_log[27] = tick;
        if (parallel_log[2] == 1u)
            independent_catchup = 2u;
        else
            parallel_log[2] = 11u;
        return;
    }
    /* Independent coils may overlap, as they already do in normal running.
     * Gating this eight-tick cadence on seconds power produces long gaps
     * when the 58-second seconds lap beats against minute catch-up. */
    if (minute_active == 0u && (int32_t)(tick - minute_due) >= 0)
    {
        GPIOB_CRL = (GPIOB_CRL & ~0xFF0u) | 0x220u;
        GPIOB_BSRR = minute_polarity != 0u ? 2u : 4u;
        minute_polarity ^= 1u;
        minute_active = 1u;
        minute_due = tick + 8u;
        minute_end = tick + 4u;
    }
}

static void motors_off(void)
{
    fine_stop();
    A_BSRR = 1u << 23;
    GPIOB_BSRR = (7u | PAIR) << 16;
    A_CRL = (A_CRL & ~(15u << 28)) | (4u << 28);
    GPIOB_CRL = (GPIOB_CRL & ~0xFFFu) | 0x444u;
    B_CRH = (B_CRH & ~PAIR_MODES) | (4u << 20) | (4u << 28);
    second_active = minute_active = 0u;
    parallel_log[19] = 0u;
}
static void radio_off(void)
{
    if (manual_web_active && !minute_log[229] && !minute_log[230])
        return;
    REG32(UART_BASE + 0x10u) = 0u;
    GPIOB_BRR = 1u << 4;
    UART1_GCR = 0u;
    A_CRL = (A_CRL & ~(15u << 8)) | (4u << 8);
    if (esp_awake)
    {
        esp_awake = 0u;
        parallel_leds_power_down(parallel_log[4],
                                 esp_time_received && !minute_log[229] && !minute_log[230]);
    }
}
__attribute__((noinline)) static void fail(uint32_t code)
{
    if (code == 10u && pwm_engine)
        pwm_fault_snapshot(100u);
    manual_web_active = 0u; /* Safety shutdown overrides the webpage lease. */
    rtc_motion_release();
    /* Only calendar/RTC faults after qualified homing can trust coordinates.
     * Never try diagnostic motion after electrical, timer or sensor faults. */
    if ((code == 8u || code == 9u) && parallel_log[2] == 7u && parallel_log[7] && parallel_log[8] &&
        !alignment_pending && !release_state[0])
    {
        radio_off();
        parallel_leds_off();
        parallel_log[3] = code;
        parallel_log[2] = 14u;
        release_state[0] = 1u;
        fault_drain = 1u;
        fault_start_tick = parallel_log[4];
        fine_motion_drain(); /* Both GPIO and autonomous PWM finish safely. */
        return;
    }
    motors_off();
    radio_off();
    parallel_leds_off();
    parallel_log[1] = 0u;
    parallel_log[2] = 6u;
    parallel_log[3] = code;
    fault_shutdown();
}
void Default_Handler(void)
{
    fail(3u);
    /* HardFault/NMI can block lower-priority SysTick servicing. Poll its
     * hardware wrap flag here instead; never attempt to resume execution. */
    for (;;)
    {
        if (REG32(0xe000e010u) & (1u << 16))
            parallel_leds_tick(++parallel_log[4]);
    }
}
static void radio_on(void)
{
    esp_sleep_requested = 0u; /* A previous session cannot close this wake. */
    uint32_t irq_mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(irq_mask)::"memory");
    if (minute_log[229])
    { /* REC wins even if main was interrupted mid-session. */
        __asm volatile("msr primask, %0" ::"r"(irq_mask) : "memory");
        return;
    }
    A_BSRR = 1u << 2;
    REG32(0x48000020u) = (REG32(0x48000020u) & ~0xFF00u) | 0x1100u;
    A_CRL = (A_CRL & ~0xFF00u) | 0x4A00u;
    REG32(0x4002101Cu) |= 1u << 17;
    if (!esp_awake)
        uart_power_wake_tick = parallel_log[4];
    uart_link_configure(); /* 38400 8N1; requires the matching ESP firmware. */
    REG32(0xe000ed20u) = (REG32(0xe000ed20u) & 0x00ffffffu) | 0x80000000u;
    legacy_esp_wake();
    if (!esp_awake)
    {
        esp_awake = 1u;
        esp_time_received = 0u;
        esp_response_tick = parallel_log[4];
    }
    parallel_leds_daily_start();
    __asm volatile("msr primask, %0" ::"r"(irq_mask) : "memory");
}
static void start(void)
{
    parallel_log[4] = 0u;
    RCC_AHBENR |= (1u << 17) | (1u << 18);
    motors_off();
    A_CRL = (A_CRL & ~(15u << 28)) | (1u << 28);
    GPIOB_CRL = (GPIOB_CRL & ~0xFFFu) | 0x221u;
    B_CRH = (B_CRH & ~(PAIR_MODES | (15u << 24))) | (2u << 20) | (2u << 28) | (4u << 24);
    /* Verified externally biased button inputs; never drive or add pulls. */
    B_CRH = (B_CRH & ~0xFF00u) | 0x4400u;
    /* Existing ESP firmware, original LF-terminated requests. */
    radio_on();
    parallel_leds_init();
    parallel_log[2] = 1u;
    parallel_log[18] = parallel_log[4] + 1u;
    minute_due = parallel_log[18];
}

#include "parallel_buttons_rebuild.h"

#include "ap_recovery.h"
/* Called from the main loop, never a blocking UART wait in the motor ISR.
 * A short IRQ exclusion publishes an atomic clock seed. Subsequent TIME
 * records cannot overwrite an in-flight correction. */
__attribute__((noinline)) void parallel_poll_once(void)
{
    static const uint8_t user[5] = {'U', 'S', 'E', 'R', '\n'};
    uint32_t stage = parallel_log[2];
    if (stage == 6u)
    {
        ap_recovery_poll();
        return;
    }
    if (stage == 14u)
        return;
    buttons_poll();
    pending_time_poll();
    manual_web_poll();
    runtime_time_poll();
    if (mode_restart_state)
        return;
    stage = parallel_log[2];
    if (buttons[9])
        return;
    if (buttons[10])
    {
        if (parallel_log[6])
            rtc_pace_poll();
        return;
    }
    if (stage == 0u || stage == 5u || stage == 6u)
        return;
    if (parallel_log[6] != 0u)
    {
        quartz_poll();
        rtc_pace_poll();
        quartz_poll(); /* Service a due countdown observation after calendar I/O. */
        /* Failed reads leave their raw bytes available for diagnosis. Do
         * not let the daily scheduler reinterpret those bytes as a time. */
        if (rtc_failed_batches || parallel_log[2] == 6u)
            return;
        if (((parallel_log[2] == 7u && parallel_log[26]) || buttons[8] || daily_log[0] == 2u) &&
            !buttons[10])
            daily_poll();
        return;
    }
    if (stage != 1u && stage != 4u)
    {
        return;
    }
    uart_probe_poll_once();
    if (mode_restart_state)
        return;
    if (uart_probe_good_time != 0u)
    {
        Mm32UartEvent e;
        e = uart_probe_time_event;
        uint32_t origin = published_time_tick;
        daily_log[0] = 7u; /* New arrivals go to the deferred mailbox during I2C. */
        if (e.kind != MM32_UART_TIME || e.year < 2000u || e.year > 2099u ||
            !time_age(&e, &origin) || !rtc_motion_set(&e) || !time_publish(&e, origin))
        {
            fail(8u);
            return;
        }
        if (parallel_log[2] == 6u)
            return;
        daily_log[0] = 1u;
        daily_log[12] = 1u;
        schedule_time_seen = uart_probe_good_time;
        __asm volatile("cpsid i" ::: "memory");
        parallel_log[5] = e.second;
        parallel_log[15] = e.minute;
        parallel_log[16] = e.hour;
        parallel_log[14] = 0u;
        parallel_log[17] = uart_probe_good_time;
        parallel_log[6] = 1u;
        __asm volatile("cpsie i" ::: "memory");
        radio_off();
        return;
    }
    if (parallel_log[4] >= next_user && tx_index == 5u)
    {
        tx_index = 0u;
        next_user = parallel_log[4] + 256u;
    }
    if (tx_index < 5u && (UART1_CSR & 1u) != 0u)
    {
        REG32(UART_BASE) = user[tx_index++];
    }
}

#include "fine_stop2go.h"
#include "motor_tick_guard.h"

/* The style is fixed for this boot. Never reset inside the UART parser or
 * while a coil is driven. Only this serialized motor tick owns the drain,
 * ESP-low interval and reset request. No minute-boundary wait is involved. */
static __attribute__((noinline)) uint32_t mode_restart_service(uint32_t tick)
{
    if (!mode_restart_state)
        return 0u;
    if (uart_echo_active)
        return 1u; /* Main-context TX is bounded; never wait for ESP/SLEEP. */
    if (mode_restart_state == 1u)
    {
        request_pulses = 0u; /* Cancel queued future minute pulses only. */
        if (fine_enabled)
            fine_motion_drain();
        if (minute_active && (!fine_enabled || parallel_log[2] != 7u) &&
            (int32_t)(tick - minute_end) >= 0)
        {
            GPIOB_BSRR = 6u << 16;
            minute_active = 0u;
        }
        if (!fine_enabled && second_active &&
            (parallel_log[26] ? (int32_t)(tick - runtime_end) >= 0 :
                               ((tick - parallel_log[18]) & 7u) == 6u))
        {
            A_BSRR = 1u << 23;
            GPIOB_BSRR = 1u << 16;
            second_active = 0u;
        }
        if (minute_active || (fine_enabled ? fine_motion_pending() : second_active))
        {
            if (tick - mode_restart_tick > 128u)
                fail(10u); /* Bounded drain: stop safely, never reset live coils. */
            return 1u;
        }
        fine_stop();
        motors_off();
        manual_web_active = esp_sleep_requested = 0u;
        radio_off();
        mode_restart_tick = tick;
        mode_restart_state = 2u;
    }
    else if (mode_restart_state == 2u && tick - mode_restart_tick >= 16u)
    {
        mode_restart_state = 3u;
        __asm volatile("dsb" ::: "memory");
        REG32(0xe000ed0cu) = 0x05fa0004u; /* AIRCR SYSRESETREQ. */
        __asm volatile("dsb" ::: "memory");
    }
    parallel_leds_tick(tick);
    return 1u;
}

static __attribute__((noinline)) void clock_tick_body(void)
{
    if (parallel_log[2] == 6u)
    {
        ap_recovery_tick(parallel_log[4] + 1u);
        parallel_leds_tick(++parallel_log[4]);
        return;
    }
    SLEEP_IRQ_NOTE();

    uint32_t tick = ++parallel_log[4], stage = parallel_log[2], boundary = 0u;
    if (mode_restart_service(tick))
        return;
    /* Hardware counts are authoritative. Observe them at 128 Hz, before
     * button/recovery state changes; never depend on TIM3 compare IRQ flags. */
    if (pwm_engine && fine_enabled)
    {
        pwm_poll(tick);
        if (parallel_log[2] == 6u)
            return;
    }
    if (stage == 14u)
    {
        fault_park_tick(tick);
        return;
    }
    rtc_pace[0] += rtc_pace[1] + 1u;
    rtc_window_tick(tick);
    if (stage == 0u)
    {
        if (parallel_log[1] == 0u)
        {
            return;
        }
        if (parallel_log[1] != 1u || used != 0u)
        {
            fail(1u);
            return;
        }
        used = 1u;
        start();
        return;
    }
    if (stage == 5u || stage == 6u)
    {
        return;
    }
    buttons_tick(tick);
    if (buttons[9])
        parallel_leds_tick(tick); /* Also while pulse drain returns. */
    /* A large unflagged correction owns a short, ISR-controlled drain,
     * never the remainder of a revolution. Do not cut an energised pulse.
     * Main applies the immutable TIME only after this acknowledgement.
     * REC/CLEAN retain priority; M.SET remains serviced by the main loop. */
    if (correction_urgent && stage == 7u)
    {
        if (buttons[9] || buttons[10])
            correction_urgent = 0u;
        else
        {
            request_pulses = 0u; /* Fresh homing will discard partial markers. */
            if (fine_enabled)
                fine_motion_drain();
            else
            {
                if (second_active && (int32_t)(tick - runtime_end) >= 0)
                {
                    A_BSRR = 1u << 23;
                    GPIOB_BSRR = 1u << 16;
                    second_active = 0u;
                }
                if (minute_active && (int32_t)(tick - minute_end) >= 0)
                {
                    GPIOB_BSRR = 6u << 16;
                    minute_active = 0u;
                }
            }
            if (!fine_motion_pending())
                correction_urgent = 2u;
            return; /* No new runtime edge while main verifies the RTC. */
        }
    }
    /* Complete this scheduled UART/time-correction session first. Recovery
     * reuses REC's pulse-draining handover, but never its permanent lockout. */
    if (alignment_recovery == 1u && stage == 7u && daily_log[0] != 2u && daily_log[0] != 7u &&
        !daily_log[13] && !buttons[9] && !buttons[10])
    {
        alignment_recovery = 2u;
        buttons[7] = 2u;
    }
    if (buttons_park_tick(tick, stage))
        return;
    stage = parallel_log[2];
    if (stage == 12u)
    {
        parallel_leds_tick(tick);
        return;
    }
    if (parallel_log[1] != 1u)
    {
        fail(parallel_log[1] == 0u ? 2u : 1u);
        return;
    }
    if (!buttons[9])
        parallel_leds_tick(tick);
    boundary = rtc_boundary;
    rtc_boundary = 0u;
    if (parallel_log[6] && tick - rtc_edge_tick > 384u &&
        (!rtc_failed_batches || tick - rtc_good_read_tick >= 384u) && !buttons[9] &&
        daily_log[13] != 2u)
    {
        fail(8u);
        return;
    }
    if (stage == 1u && tick - parallel_log[18] > 46080u)
    {
        fail(7u);
        return;
    }
    if (parallel_log[6] == 0u && tick - esp_response_tick >= 38400u && !buttons[9] && !buttons[10])
    {
        fail(6u);
        return;
    }
    if (stage == 1u && parallel_log[7] && parallel_log[6] && !buttons[9])
    {
        if (!independent_catchup)
            catchup_begin(tick);
        if (independent_catchup == 1u)
            catchup_tick(tick);
        if (parallel_log[2] == 6u)
            return;
    }
    if (stage == 4u)
    {
        if (parallel_log[6] != 0u)
        {
            catchup_begin(tick);
        }
        return;
    }
    if (stage == 10u)
    {
        catchup_tick(tick);
        stage = parallel_log[2];
        if (stage == 6u)
        {
            return;
        }
    }
    if (stage == 11u)
    {
        /* Stay in acquisition until both motors and RTC calibration are
         * ready. At the new 00 the minute may legitimately be one behind;
         * queue its six complete pulses alongside seconds, never early. */
        uint32_t distance = (clock_minute() + 720u - parallel_log[22]) % 720u;
        if (distance == 0u)
            correction_wait_ahead = 0u;
        if (((parallel_log[26] && distance == 0u) || boundary) && rtc_pace[4] && !minute_active &&
            !catchup_pulses && distance <= 1u && !correction_wait_ahead &&
            minute_home_ready(tick) && seconds_home_ready(tick))
        {
            parallel_log[2] = 7u;
            stage = 7u;
            if (correction_seconds_independent)
            {
                daily_log[13] = 0u;
                correction_seconds_independent = 0u;
            }
            if (distance)
            {
                request_pulses = 6u;
                minute_due = tick;
            }
            GPIOB_CRL = pwm_engine ? (GPIOB_CRL & ~0xFF0u) | 0x220u :
                                   (GPIOB_CRL & ~0xFFFu) | 0x221u;
        }
        else if (distance && !(daily_log[13] == 3u && (distance == 719u || correction_wait_ahead)))
        {
            catchup_begin(tick);
            stage = 10u;
        }
    }
    if (stage != 1u && parallel_log[26] == 0u)
    {
        if (stage != 7u && (daily_log[13] == 3u || !parallel_log[7] || !parallel_log[8]))
            return;
        if (daily_log[13] == 3u && stage != 7u)
            return;
        /* Also cover a zero-distance catch-up at a coincident :00 edge. */
        if (!minute_home_ready(tick) || !seconds_home_ready(tick))
            return;
        if (boundary == 0u || !rtc_pace[4])
        {
            return;
        }
        parallel_log[26] = 1u;
        parallel_log[9] = tick;
        parallel_log[18] = tick;
        /* A correction may retain a gated runtime waveform. Do not take
         * PA7/PB0 away from their timer when releasing that same waveform. */
        if (!pwm_engine)
        {
            A_CRL = (A_CRL & ~(15u << 28)) | (1u << 28);
            GPIOB_CRL = (GPIOB_CRL & ~15u) | 1u;
        }
        parallel_seconds_runtime_begin();
        GPIOB_BSRR = PAIR << 16;
        GPIOB_BSRR = 1u << 13;
        B_CRH = (B_CRH & ~PAIR_MODES) | (2u << 20) | (2u << 28);
        if (daily_log[13] == 3u)
            daily_log[13] = 0u;
    }
    if (stage != 1u && parallel_log[26])
    {
        fine_runtime_tick(tick, stage, boundary);
        return;
    }
    /* Runtime movement is owned by TIM3 above, never the coarse scheduler. */
    if (stage != 1u)
        return;
    frame = (tick - parallel_log[18]) & 7u;
    if (stage == 1u)
    {
        /* The selector from the previous ISR has settled for 7.8125ms.
         * Never count a minute-channel read towards seconds acquisition. */
        uint32_t high = (B_IDR >> 14) & 1u;
        if (parallel_log[19] == 1u && second_active != 0u)
        {
            second_highs += high;
        }
        if (parallel_log[19] == 2u && minute_active != 0u && minute_polarity == 0u &&
            !parallel_log[7])
        {
            parallel_minute_sample(high, minute_log[5] + 1u);
            if (minute_log[243] && !minute_log[249])
            {
                /* Retain the pulse on which the sensor qualified, not the
                 * end of its six-pulse request. This removes start-phase
                 * rounding from the final mechanical 12 position. */
                minute_log[249] = parallel_log[20] + 1u;
                minute_log[250] = minute_log[249] + MINUTE_REFERENCE_OFFSET;
            }
        }
    }
    if (frame == 0u && (parallel_log[8] == 0u || parallel_log[26] != 0u))
    {
        second_highs = 0u;
        if (second_polarity == 0u)
        {
            GPIOB_BSRR = 1u;
        }
        else
        {
            A_BSRR = 1u << 7;
        }
        second_polarity ^= 1u;
        second_active = 1u;
    }
    if (parallel_log[7] == 0u && tick >= minute_due && minute_active == 0u)
    {
        {
            GPIOB_BSRR = minute_polarity != 0u ? 2u : 4u;
            minute_polarity ^= 1u;
            minute_active = 1u;
            minute_due = tick + 8u;
            minute_end = tick + 4u;
        }
    }
    if (minute_active != 0u && tick == minute_end && !parallel_log[7])
    {
        GPIOB_BSRR = 6u << 16;
        minute_active = 0u;
        ++parallel_log[20];
        if (minute_fine != 0u)
        {
            ++fine_pulses;
            minute_log[253] = fine_pulses;
            /* Keep the tested mean 0.1s dwell after each final substep.
             * 12/13 ticks at 128Hz average 0.1s, after the released half
             * of the 8-tick electrical frame. No minute-marker pauses. */
            dwell_fraction += 4u;
            minute_due = tick + 16u;
            if (dwell_fraction >= 5u)
            {
                dwell_fraction -= 5u;
                ++minute_due;
            }
            if (fine_pulses % 6u == 0u)
            {
                ++minute_log[5];
            }
            if (parallel_log[20] >= minute_log[250])
            {
                minute_home_settle_due = tick + HOME_SETTLE_TICKS;
                minute_home_settling = 1u;
                parallel_log[7] = 1u;
                parallel_log[11] = tick;
                minute_log[245] = 1u;
            }
        }
        else if (++request_pulses == 6u)
        {
            request_pulses = 0u;
            parallel_minute_request_done();
            if (minute_log[243] != 0u)
            {
                minute_fine = 1u;
            }
            else if (minute_log[5] >= 740u)
            {
                fail(4u);
                return;
            }
        }
    }
    if (frame == 6u)
    {
        if (second_active != 0u)
        {
            A_BSRR = 1u << 23;
            GPIOB_BSRR = 1u << 16;
            second_active = 0u;
            if (stage == 1u)
            {
                uint32_t result = parallel_seconds_pulse_done(second_highs);
                parallel_log[21] = seconds_log[5];
                if (result == 1u)
                {
                    parallel_log[8] = 1u;
                    parallel_log[10] = tick;
                    seconds_home_settle_due = tick + HOME_SETTLE_TICKS;
                    seconds_home_settling = 1u;
                }
                else if (result != 0u)
                {
                    fail(5u);
                    return;
                }
            }
        }
    }
    if (parallel_log[7] != 0u && parallel_log[8] != 0u)
    {
        if (alignment_recovery == 3u)
        {
            alignment_pending = alignment_recovery = 0u;
            audit_seconds_status = audit_seconds_seen = 0u;
        }
        if (parallel_log[6] && !buttons[9] && independent_catchup)
        {
            /* Preserve any complete minute pulse already in progress. */
            GPIOB_BSRR = PAIR << 16;
            parallel_log[19] = 0u;
            parallel_log[2] = independent_catchup == 2u ? 11u : 10u;
            return;
        }
        motors_off();
        parallel_log[2] = 4u;
        if (buttons[9])
        {
            parallel_log[22] = 0u;
            parallel_log[2] = 12u;
            parallel_leds_off();
        }
        return; /* Even if completion coincides with 00, wait for next edge. */
    }
    if (stage == 1u)
    {
        GPIOB_BSRR = PAIR << 16;
        parallel_log[19] = (tick & 1u) != 0u ? 1u : 2u;
        GPIOB_BSRR = parallel_log[19] == 1u ? 1u << 13 : 1u << 15;
    }
}
/* Every wake uses the configured local HH:MM. No accelerated first wake. */
__attribute__((noinline)) static void daily_schedule(uint32_t now)
{
    uint32_t target = now - (now % 86400u) + daily_log[10] * 3600u + daily_log[11] * 60u;
    if (target <= now)
        target += 86400u;
    daily_log[3] = target;
}
static void daily_finish(uint32_t status, uint32_t now)
{
    radio_off();
    correction_boundary_due = 0u;
    correction_urgent = 0u;
    daily_log[0] = status;
    ++daily_log[2];
    daily_schedule(now);
}
/* Publish RTC ownership atomically with the motor-idle check. Otherwise a
 * minute edge or seconds release could start between the check and phase 2. */
static uint32_t correction_admit(void)
{
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    uint32_t ready = parallel_log[2] == 7u && daily_log[0] == 7u &&
        !buttons[9] && !buttons[10] && !mode_restart_state &&
        (correction_urgent ? correction_urgent == 2u :
         parallel_log[30] && !minute_active && !request_pulses && !fine_minute_steps);
    if (ready)
        daily_log[13] = 2u;
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
    return ready;
}
static void daily_poll(void)
{
    static const uint8_t request[5] = {'U', 'S', 'E', 'R', '\n'};
    if (!daily_log[12])
        return;
    uint32_t now = seconds_log[227];
    if (now == 0xffffffffu)
    {
        fail(8u);
        return;
    }
    if (!daily_log[3])
    {
        daily_schedule(now);
        if (daily_log[0] == 0u)
            daily_log[0] = 1u;
    }
    if (daily_log[0] == 7u)
    {
        /* A manual startup request may finish before homing; do not apply
         * a mechanical correction until normal runtime can park at12. */
        if (parallel_log[2] != 7u)
        {
            correction_runtime_started = 0u;
            return;
        }
        if (!correction_runtime_started)
        {
            correction_runtime_stamp = now;
            correction_runtime_started = 1u;
        }
        /* DST/small changes wait for next old-RTC :00; unflagged large
         * changes have a deadline of receipt. A busy poll must not miss
         * either deadline. Motor-safe admission still follows, and the
         * 70-second safety budget starts at this admission deadline. */
        if (correction_boundary_due && now < correction_boundary_due)
            return;
        if (now - correction_runtime_stamp > 70u)
        {
            fail(5u);
            return;
        }
        if (!correction_admit())
            return; /* Finish old powered pulses/partial markers first. */
        Mm32UartEvent e = uart_probe_time_event;
        uint32_t origin = correction_time_tick;
        if (!time_age(&e, &origin))
        {
            fail(8u);
            return;
        }
        if (!rtc_motion_set(&e) || !time_publish(&e, origin))
        {
            fail(8u);
            return;
        }
        /* Check and commit under the SAME mask: an ISR can take ownership
         * during calendar I2C or immediately before this critical section.
         * Keep the verified clock, never overwrite its motor handover. */
        uint32_t irq_mask;
        __asm volatile("mrs %0, primask\n cpsid i" : "=r"(irq_mask)::"memory");
        if (parallel_log[2] != 7u || buttons[9] || buttons[10] || mode_restart_state)
        {
            __asm volatile("msr primask, %0" ::"r"(irq_mask) : "memory");
            return;
        }
        now = seconds_log[227];
        uint32_t tick = parallel_log[4], sod = now % 86400u;
        /* A calendar correction is not a change to the oscillator rate.
         * Retain established calibration; restart only its measurement window.
         * A qualified 00 can release now; otherwise the next civil 00 releases. */
        /* time_publish already qualified the fractional :00 phase. */
        correction_wait_ahead =
            (daily_log[6] < daily_log[7] && parallel_log[22] != ((sod / 60u) % 720u));
        rtc_pace[7] = sod;
        rtc_pace[8] = tick;
        parallel_log[5] = sod % 60u;
        parallel_log[15] = (sod / 60u) % 60u;
        parallel_log[16] = sod / 3600u;
        parallel_log[26] = 0u;
        /* Ordinary corrections were admitted at the qualified reference;
         * urgent corrections drained a partial lap and rehome below.
         * Preserve the running TIM3 waveform and AF pins while outputs hold.
         * Permanent parking may have no launched seconds waveform yet;
         * its existing launch-pending flag remains authoritative. */
        if (pwm_engine && fine_enabled)
            parallel_log[30] = 1u;
        else
        {
            parallel_log[30] = 0u;
            fine_stop();
        }
        daily_log[13] = 3u; /* Wait for minute catch-up and a new RTC 00. */
        if (correction_urgent || (correction_boundary_due && daily_log[6] < daily_log[7] &&
            daily_log[7] - daily_log[6] > 60u))
        {
            /* A partial-lap immediate correction needs fresh mechanical
             * coordinates; a large backward DST correction does too.
             * RTC is now corrected.
             * Schedule the existing ISR-owned safe rehome; it preserves
             * RTC/settings/schedule and rebuilds motor state intentionally.
             * Do not publish a button action from main: the ISR owns that
             * drain handover. REC/CLEAN still take priority there. */
            daily_log[13] = 0u;
            correction_wait_ahead = 0u;
            alignment_recovery = 1u;
            ++daily_log[8];
            daily_finish(3u, now);
            __asm volatile("msr primask, %0" ::"r"(irq_mask) : "memory");
            return;
        }
        catchup_begin(tick);
        if (correction_boundary_due && pwm_engine && fine_enabled)
        {
            /* Runtime seconds own their corrected :00 independently of
             * minute catch-up. Keep phase3 for minute/backward-hold logic,
             * but permit the ISR's existing phase-safe seconds resume.
             * Only corrected :00 may authorise release. Preserve this wait
             * even if minute catch-up finishes before that boundary. */
            correction_seconds_independent = 1u;
            parallel_log[26] = 1u;
            parallel_log[9] = parallel_log[18] = tick;
            correction_seconds_boundary_wait = 1u;
            fine_boundary = rtc_boundary;
            fine_handover_tick = tick;
        }
        /* At an exact corrected 00, one forward marker is the ordinary
         * minute transition. Queue it alongside seconds through stage 11;
         * fast catch-up here would consume this edge and add a minute wait. */
        if (rtc_boundary && !correction_wait_ahead &&
            (clock_minute() + 720u - parallel_log[22]) % 720u == 1u)
            parallel_log[2] = 11u;
        __asm volatile("msr primask, %0" ::"r"(irq_mask) : "memory");
        ++daily_log[8];
        daily_finish(3u, now);
        return;
    }
    if (daily_log[0] != 2u)
    {
        if (now < daily_log[3] && !buttons[8])
            return;
        if (!buttons[8])
        {
            ++daily_log[1];
            if (alignment_pending)
                alignment_recovery = 1u;
        }
        buttons[8] = 0u;
        daily_log[0] = 2u;
        daily_log[4] = parallel_log[4];
        daily_log[14] = now;
        daily_log[5] = uart_probe_good_time;
        daily_log[15] = uart_probe_uart_errors;
        line_length = 0u;
        line_overflowed = 0u;
        parallel_leds_daily_start();
        next_user = parallel_log[4] + 256u;
        tx_index = 5u;
        radio_on();
    }
    uart_probe_poll_once();
    if (mode_restart_state)
        return;
    /* Receipt and mechanical application are separate. During hand setting
     * a fresh, validated TIME is already safe in the deferred mailbox and
     * has been echoed. Finish acquisition now; preserve the mailbox and its
     * receipt epoch for promotion after catch-up. A live webpage retains
     * the normal radio lease through radio_off's existing guard.
     * Never finish an in-flight RTC correction or use an older session's
     * retained record as evidence that this wake has succeeded. */
    if (parallel_log[6] && parallel_log[2] != 7u && !daily_log[13] &&
        !buttons[9] && !buttons[10] &&
        (pending_time_meta & PENDING_TIME_VALID) && esp_time_received &&
        uart_probe_good_time == daily_log[5] &&
        (int32_t)(pending_time_tick - daily_log[4]) >= -2)
    {
        daily_finish(3u, now);
        return;
    }
    if (uart_probe_good_time != daily_log[5])
    {
        Mm32UartEvent e = uart_probe_time_event;
        correction_time_tick = published_time_tick;
        /* Freeze the correction before RTC I/O can service another TIME.
         * Its independent settings still publish at receipt. */
        daily_log[0] = 7u;
        radio_off();
        uint32_t h, m, s;
        if (e.year < 2000u || e.year > 2099u || !rtc_motion_read(&h, &m, &s))
        {
            fail(8u);
            return;
        }
        /* The UART parser stores TIME separately, so subsequent TICK/ACK
         * records cannot replace it. Damaged lines were discarded at receipt. */
        now = seconds_log[227];
        daily_log[6] = rtc_event_stamp(&e);
        daily_log[7] = now;
        correction_seconds_independent = 0u;
        uint32_t difference = daily_log[6] > now ? daily_log[6] - now : now - daily_log[6];
        correction_urgent = (parallel_log[2] == 7u && !e.dst_pending && difference > 60u) ? 1u : 0u;
        correction_boundary_due = (parallel_log[2] == 7u) ?
            ((!e.dst_pending && difference > 60u) ? now : now + 60u - now % 60u) : 0u;
        correction_runtime_stamp = correction_boundary_due ? correction_boundary_due : now;
        correction_runtime_started = (parallel_log[2] == 7u);
        schedule_time_seen = uart_probe_good_time;
        parallel_leds_daily_received(parallel_log[4]);
        if (daily_log[6] == now)
        {
            if (!time_publish(&e, correction_time_tick))
            {
                fail(8u);
                return;
            }
            daily_finish(3u, now);
        }
        else
        {
            daily_log[0] = 7u;
            daily_log[13] = 1u;
        }
        return;
    }
    if (parallel_log[4] - esp_response_tick >= 38400u)
    {
        manual_web_active = 0u;
        daily_finish(5u, now);
        return;
    }
    if ((int32_t)(parallel_log[4] - next_user) >= 0 && tx_index == 5u)
    {
        tx_index = 0u;
        next_user = parallel_log[4] + 256u;
    }
    if (tx_index < 5u && (UART1_CSR & 1u))
    {
        REG32(UART_BASE) = request[tx_index++];
        if (tx_index == 5u)
            ++daily_log[9];
    }
}
/* SLEEP closes the ESP lease only, never the motor/RTC state. Process in the
 * main loop AFTER accepted TIME handling. Never cut power in the RX parser. */
static __attribute__((noinline)) void esp_sleep_poll(void)
{
    /* RTC I/O can receive TIME+SLEEP after this loop's webpage poll.
     * Process a newly retained runtime record before closing that lease. */
    runtime_time_poll();
    if (!esp_sleep_requested || buttons[10] || parallel_log[2] == 6u ||
        parallel_log[2] == 14u)
        return;
    /* Preserve a complete TIME that has arrived during RTC I/O but has not
     * yet been processed by the current daily acquisition session. */
    if (daily_log[0] == 2u && uart_probe_good_time != daily_log[5])
        return;
    if (!parallel_log[6] && uart_probe_good_time &&
        parallel_log[17] != uart_probe_good_time)
        return;
    esp_sleep_requested = 0u;
    minute_log[159] = parallel_log[4];
    manual_web_active = 0u; /* Explicit ESP request overrides webpage keepalive. */
    if (daily_log[0] == 2u && parallel_log[6])
        daily_finish(5u, seconds_log[227]); /* End an unsuccessful wake cleanly. */
    else
        radio_off();
}
int main(void)
{
    audit_enabled = 1u;
    mode_latched = mode_restart_state = fine_mode_active = 0u;
    parallel_log[0] = 0x4d5052a2u;
    rtc_pace[1] = 62499u;
    /* Arm once after C runtime initialization, before enabling SysTick.
     * Existing ISR owns peripheral setup; abort/fault/REC cannot rearm this. */
    parallel_log[1] = 1u;
    fine_night_enabled = 1u;
    /* Reserved former sleep-control word remains zero. */
    /* Sleep-now only. Keep every motor/peripheral clock unchanged. */
    REG32(0xe000ed10u) &= ~6u;
    /* SysTick, PendSV and TIM3 serialize all shared motor state. */
    REG32(0xe000ed20u) = (REG32(0xe000ed20u) & 0x0000ffffu) | 0x80800000u;
    REG32(0xE000E014u) = 62499u;
    REG32(0xE000E018u) = 0u;
    REG32(0xE000E010u) = 7u;
    for (;;)
    {
        if (parallel_log[2] == 6u)
        {
            ap_recovery_poll();
            __asm volatile("wfi");
            continue;
        }
        uint32_t sleep_epoch = seconds_log[213];
        if (mode_restart_state)
        {
            cpu_sleep_idle(sleep_epoch);
            continue;
        }
        parallel_poll_once();
        if (!mode_restart_state)
            esp_sleep_poll();
        cpu_sleep_idle(sleep_epoch);
    }
}
#include "quartz_reference.h"
#include "rtc_sync_windows.h"
