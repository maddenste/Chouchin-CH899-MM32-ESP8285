// Copyright (C) 2026 Steve Madden | SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>

// ESP user RTC API offsets are WORDS. Use bytes 384..399 of the user area,
// beyond eboot's reserved first 128 bytes. This is not EEPROM/flash storage.
constexpr uint32_t SAVE_SLEEP_RTC_WORD = 96;
constexpr uint32_t SAVE_SLEEP_MAGIC = 0x53535232; // SSR2
struct SaveSleepTicket {
  uint32_t magic, fingerprint, inverseFingerprint, inverseMagic;
};
static_assert(sizeof(SaveSleepTicket) == 16, "RTC ticket must be word-aligned");
bool saveSleepPending = false;

bool validSaveSleepTicket(const SaveSleepTicket &t, uint32_t fingerprint) {
  return t.magic == SAVE_SLEEP_MAGIC && t.inverseMagic == ~SAVE_SLEEP_MAGIC &&
      t.fingerprint == fingerprint && t.inverseFingerprint == ~fingerprint;
}

bool clearSaveSleepTicket() {
  SaveSleepTicket cleared{};
  return ESP.rtcUserMemoryWrite(SAVE_SLEEP_RTC_WORD,
      reinterpret_cast<uint32_t *>(&cleared), sizeof(cleared));
}

bool armSaveSleepTicket(uint32_t fingerprint) {
  SaveSleepTicket ticket{SAVE_SLEEP_MAGIC, fingerprint, ~fingerprint, ~SAVE_SLEEP_MAGIC};
  SaveSleepTicket check{};
  if (ESP.rtcUserMemoryWrite(SAVE_SLEEP_RTC_WORD,
          reinterpret_cast<uint32_t *>(&ticket), sizeof(ticket)) &&
      ESP.rtcUserMemoryRead(SAVE_SLEEP_RTC_WORD,
          reinterpret_cast<uint32_t *>(&check), sizeof(check)) &&
      validSaveSleepTicket(check, fingerprint)) return true;
  clearSaveSleepTicket();
  return false; // Settings are still saved; ordinary MM32 power-off remains.
}

bool takeSaveSleepTicket(uint32_t fingerprint, bool usableConfig) {
  SaveSleepTicket ticket{};
  const bool read = ESP.rtcUserMemoryRead(SAVE_SLEEP_RTC_WORD,
      reinterpret_cast<uint32_t *>(&ticket), sizeof(ticket));
  // Consume before starting Wi-Fi/NTP. A later reset cannot replay this job.
  const bool cleared = clearSaveSleepTicket();
  const auto *reset = ESP.getResetInfoPtr();
  return read && cleared && usableConfig && reset &&
      reset->reason == REASON_SOFT_RESTART && validSaveSleepTicket(ticket, fingerprint);
}
