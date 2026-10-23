// Copyright (C) 2026 Steve Madden
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef TXW_CLOCK_CALENDAR_H
#define TXW_CLOCK_CALENDAR_H

#include <stdint.h>
#include <stddef.h>
#include "clock_calendar_types.h"

// POSIX fixed offsets and Mmonth.week.weekday[/time] DST rules are supported.
int txw_clock_timezone_supported(const char *zone);
int txw_clock_local_from_unix(uint32_t utc_seconds, const char *zone,
                              struct txw_hc32_time *result);

struct txw_clock_dst_change {
    uint32_t utc_seconds;
    int16_t before_minutes;
    int16_t after_minutes;
};
int txw_clock_next_dst_change(uint32_t utc_seconds, const char *zone,
                              struct txw_clock_dst_change *change);
// MM32 RC6AO: wake one minute before the rounded transition boundary.
// Retain the saved schedule when it occurs earlier.
int txw_clock_next_wake(uint32_t utc_seconds, const char *zone,
                        uint8_t saved_hour, uint8_t saved_minute,
                        uint8_t *wake_hour, uint8_t *wake_minute);
// Overwrite TIME text only before the transition, using upcoming offset and
// CURRENT seconds. ESP's own clock/timezone is unchanged. Returns1 if prepared.
int txw_clock_upcoming_dst_text(uint32_t utc_seconds, const char *zone,
                                char *out, size_t capacity);

#endif
