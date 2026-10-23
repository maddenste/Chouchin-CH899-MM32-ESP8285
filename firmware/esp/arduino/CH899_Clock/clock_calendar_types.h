// Copyright (C) 2026 Steve Madden | SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
// Shared calendar container only. No HC32 UART code or baud imported.
struct txw_hc32_time {
    uint16_t year;
    uint8_t month, day, weekday, hour, minute, second;
    int16_t utc_offset_minutes;
};
