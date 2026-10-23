// Copyright (C) 2026 Steve Madden
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

// Optional DST marks an upcoming offset, not an ordinary time correction.
inline size_t formatMm32Time(char *buffer, size_t capacity, const char *localText,
                            uint8_t hour, uint8_t minute, uint8_t movement,
                            uint8_t parking, bool dstPending = false) {
  if (!buffer || !capacity || !localText || hour > 23 || minute > 59 ||
      movement > 3 || parking > 2) return 0;
  const int count = snprintf(buffer, capacity, "+TIME:%s %02u:%02u%u%u%s\r\n",
                             localText, hour, minute, movement, parking,
                             dstPending ? " DST" : "");
  return count > 0 && static_cast<size_t>(count) < capacity ? static_cast<size_t>(count) : 0;
}
