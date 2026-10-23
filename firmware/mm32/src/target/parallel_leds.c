#include "movement_api.h"
#define REG32(a) (*(volatile uint32_t *)(a))

/* Physically verified active-low LEDs and cadence, driven from SysTick.
 * Only PA15/PB3 are touched; never motor pins, selectors or the timebase.
 * Telemetry word28: 0 inactive,1 red/requesting,2 blue/received,3 finished.
 * Word29: blue confirmation start tick. Blue confirms TIME receipt, not
 * completed mechanical alignment. State6 is the latched fault indication:
 * simultaneous red/blue flash count with ten seconds dark between groups. */
static void pins_off(void)
{
    REG32(0x48000010u) = 1u << 15;
    REG32(0x48000410u) = 1u << 3;
}
void parallel_leds_off(void)
{
    if (parallel_log[28] == 0u)
    {
        return;
    }
    pins_off();
    parallel_log[28] = 0u;
}
void parallel_leds_init(void)
{
    pins_off(); /* Preload inactive levels before making the pins outputs. */
    REG32(0x48000024u) &= ~(15u << 28);
    REG32(0x48000420u) &= ~(15u << 12);
    REG32(0x48000004u) = (REG32(0x48000004u) & ~(15u << 28)) | (2u << 28);
    REG32(0x48000400u) = (REG32(0x48000400u) & ~(15u << 12)) | (2u << 12);
    parallel_log[28] = 1u;
}
void parallel_leds_tick(uint32_t tick)
{
    if (parallel_log[28] == 6u)
    {
        uint32_t code = parallel_log[3];
        if (!code || code > 10u)
        {
            pins_off();
            return;
        }
        uint32_t duration = (code - 1u) * 64u + 8u;
        uint32_t elapsed = tick - parallel_log[29];
        if (elapsed >= duration + 1280u)
        {
            parallel_log[29] = tick;
            elapsed = 0u;
        }
        uint32_t on = elapsed < duration && elapsed % 64u < 8u;
        REG32(0x48000010u) = on ? 1u << 31 : 1u << 15;
        REG32(0x48000410u) = on ? 1u << 19 : 1u << 3;
        return;
    }
    if (parallel_log[28] == 5u)
    {
        uint32_t elapsed = tick - parallel_log[29];
        uint32_t flash = ((elapsed / 8u) % 8u) == 6u;
        uint32_t blue = (elapsed / 64u) & 1u;
        /* Existing 62.5ms flash every 0.5s, alternating colour. */
        REG32(0x48000010u) = flash && !blue ? 1u << 31 : 1u << 15;
        REG32(0x48000410u) = flash && blue ? 1u << 19 : 1u << 3;
        return;
    }
    if (parallel_log[28] == 1u || parallel_log[28] == 4u)
    {
        REG32(0x48000010u) = ((tick / 8u) % 8u) == 6u ? 1u << 31 : 1u << 15;
        return;
    }
    if (parallel_log[28] == 2u)
    {
        uint32_t elapsed = tick - parallel_log[29];
        if (elapsed >= 384u)
        {
            pins_off();
            parallel_log[28] = 3u;
        }
        else
        {
            /* Six flashes, 62.5ms on every 0.5s, then both off.
             * Initial 0.375s dark interval retains the established cadence. */
            REG32(0x48000410u) = ((elapsed / 8u) % 8u) == 6u ? 1u << 19 : 1u << 3;
        }
    }
}

void parallel_leds_fault_start(uint32_t tick)
{
    parallel_leds_init(); /* Also covers a fault before normal start(). */
    pins_off();
    parallel_log[29] = tick;
    parallel_log[28] = 6u;
    parallel_leds_tick(tick);
}

void parallel_leds_rec_start(uint32_t tick)
{
    if (parallel_log[28] == 5u)
        return;
    pins_off();
    parallel_log[29] = tick;
    parallel_log[28] = 5u;
}

void parallel_leds_daily_start(void)
{
    pins_off();
    parallel_log[28] = 4u;
}
void parallel_leds_daily_received(uint32_t tick)
{
    (void)tick; /* Receipt alone does not signal power-down. */
}
void parallel_leds_power_down(uint32_t tick, uint32_t success)
{
    if (parallel_log[28] == 5u)
        return; /* REC indication outlives radio shutdown. */
    pins_off();
    parallel_log[29] = tick;
    parallel_log[28] = success ? 2u : 0u;
}
