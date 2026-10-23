#include "movement_api.h"
#include "alignment_calibration.h"
/* Stable state layout retained for safety logic and RAM mode controls. */
volatile uint32_t seconds_log[256];
static uint32_t pulse_highs;
static uint32_t home_update(void)
{
    uint32_t high = pulse_highs >= 2u, pulse = seconds_log[5];
    if (!seconds_log[240])
    {
        if (!high)
        {
            seconds_log[244] = 0u;
            if (++seconds_log[243] >= 4u)
                seconds_log[242] = 1u;
        }
        else
        {
            seconds_log[243] = 0u;
            if (seconds_log[242] && ++seconds_log[244] == 2u)
            {
                seconds_log[240] = pulse;
                seconds_log[241] = pulse + SECONDS_REFERENCE_OFFSET;
                seconds_log[246] = 2u;
            }
        }
    }
    else if (!seconds_log[245])
    {
        if (high)
        {
            if (++seconds_log[246] > 32u)
                return 5u;
        }
        else
        {
            if (seconds_log[246] < 4u)
                return 5u;
            seconds_log[245] = 1u;
        }
    }
    else if (high)
        return 5u;
    if (seconds_log[240] && pulse >= seconds_log[241])
    {
        if (!seconds_log[245])
            return 5u;
        seconds_log[247] = 1u;
        return 1u;
    }
    return pulse >= 1100u ? 4u : 0u;
}
uint32_t parallel_seconds_pulse_done(uint32_t highs)
{
    pulse_highs = highs;
    ++seconds_log[5];
    return home_update();
}
/* Ordinary laps contain exactly 960 completed pulses. The qualified optical
 * reference plus homing offset is an alignment observation, not permission
 * to shorten or lengthen a lap. Homing above remains sensor-positioned.
 * Words248..255: steps, clear, high streak, anchor, exited, width, target, laps. */
void parallel_seconds_runtime_begin(void)
{
    for (uint32_t i = 248u; i < 255u; ++i)
        seconds_log[i] = 0u;
}
uint32_t parallel_seconds_runtime_done(uint32_t highs)
{
    uint32_t p = ++seconds_log[248], high = highs >= 4u;
    if (!seconds_log[251])
    {
        if (!high)
        {
            ++seconds_log[249];
            seconds_log[250] = 0u;
        }
        else if (seconds_log[249] >= 4u && ++seconds_log[250] == 2u)
        {
            seconds_log[251] = p;
            seconds_log[254] = p + SECONDS_REFERENCE_OFFSET;
            seconds_log[253] = 2u;
            /* A missing/out-of-phase reference cannot drive indefinitely. */
            if (p < 764u || p > 1020u)
                return 2u;
        }
    }
    else if (!seconds_log[252])
    {
        if (high)
        {
            if (++seconds_log[253] > 32u)
                return 2u;
        }
        else
        {
            if (seconds_log[253] < 4u)
                return 2u;
            seconds_log[252] = 1u;
        }
    }
    else if (high)
        return 2u;
    if (p >= 960u)
    {
        /* A normal reference is qualified/exited well before this boundary.
         * Missing, unfinished or corrupted tracking cannot authorize a new
         * lap. Stop safely after the completed pulse; never seek with extras. */
        if (p != 960u || !seconds_log[254] || !seconds_log[252])
            return 2u;
        ++seconds_log[255];
        return 1u;
    }
    return 0u;
}
