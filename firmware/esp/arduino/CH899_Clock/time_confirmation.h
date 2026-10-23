// Copyright (C) 2026 Steve Madden | SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

// One in-flight exact wire record, scoped to this boot/NTP acquisition.
// The UART line reader removes CR/LF; compare every remaining byte.
class TimeConfirmation {
  char expected[64] = {};
  uint8_t attempts = 0;
  bool matched = false;
  uint32_t sentAt = 0;
public:
  void reset() { expected[0] = '\0'; attempts = 0; matched = false; }
  bool canSend() const { return !matched && attempts < 5; }
  bool confirmed() const { return matched; }
  void transmitFailed() {
    expected[0] = '\0'; matched = false;
    if (attempts < 5) ++attempts;
  }
  bool recordSent(const char *record, size_t length, uint32_t now) {
    if (!record || length < 2 || length - 2 >= sizeof(expected) ||
        record[length-2] != '\r' || record[length-1] != '\n') return false;
    memcpy(expected, record, length-2); expected[length-2] = '\0';
    matched = false;
    sentAt = now;
    if (attempts < 5) ++attempts;
    return true;
  }
  bool acceptEcho(const char *line, uint32_t now) {
    if (!line || !expected[0] || matched || now - sentAt > 2000u ||
        strcmp(expected, line)) return false;
    matched = true;
    return true;
  }
};
