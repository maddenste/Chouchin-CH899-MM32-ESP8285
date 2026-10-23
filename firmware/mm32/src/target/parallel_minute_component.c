#include "movement_api.h"
/* Qualified minute reference acquisition; GPIO is owned by the controller. */
volatile uint32_t minute_log[256];
static void finish_search_request(void)
{
    if (minute_log[243])
        return;
    if (minute_log[247])
    {
        minute_log[246] = minute_log[248] = minute_log[241] = 0u;
    }
    else if (minute_log[246] < 12u)
    {
        if (++minute_log[246] == 12u)
            minute_log[248] = 1u;
    }
    minute_log[247] = 0u;
}
static void acquire_reference(uint32_t high, uint32_t step)
{
    if (minute_log[243])
        return;
    minute_log[247] |= high;
    if (!high)
    {
        if (minute_log[240] < 2u)
            ++minute_log[240];
        minute_log[241] = 0u;
        return;
    }
    if (!minute_log[248])
        return;
    if (!minute_log[241] || minute_log[242] != step)
    {
        minute_log[242] = step;
        minute_log[241] = 1u;
    }
    else
    {
        minute_log[241] = 2u;
        minute_log[243] = step;
        minute_log[244] = step + 8u;
    }
}
void parallel_minute_sample(uint32_t high, uint32_t request)
{
    acquire_reference(high, request);
    ++minute_log[6];
    minute_log[7] += high;
}
void parallel_minute_request_done(void)
{
    ++minute_log[5];
    finish_search_request();
}
