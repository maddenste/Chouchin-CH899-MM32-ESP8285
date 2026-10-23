// Copyright (C) 2026 Steve Madden | SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "save_sleep.h"
#include "time_confirmation.h"
TimeConfirmation timeConfirmation;
// Included after the sketch's private configuration/session declarations.
struct NtpAttempt {
  IPAddress ip;
  uint64_t nonce = 0;
  uint32_t sentAt = 0;
  uint32_t sentMicros = 0;
  bool pending = false;
};
WiFiUDP ntpUdp;
NtpAttempt ntpAttempts[2];

void stopNtpTransport() {
  ntpUdp.stop();
  for (auto &attempt : ntpAttempts) attempt = NtpAttempt{};
}

void startNtpAttempt(unsigned index) {
  if (index > 1) return;
  auto &attempt = ntpAttempts[index];
  attempt.sentAt = millis();
  attempt.pending = false;
  const String &host = index ? config.ntpBackupHost : config.ntpHost;
  if (host.isEmpty()) return; // Optional secondary: no DNS or UDP when unset.
  if (WiFi.hostByName(host.c_str(), attempt.ip, 1000) != 1) return;
  ESP.random(reinterpret_cast<uint8_t *>(&attempt.nonce), sizeof(attempt.nonce));
  uint8_t packet[48];
  txw_ntp_make_request(packet, attempt.nonce);
  if (!ntpUdp.beginPacket(attempt.ip, 123)) return;
  ntpUdp.write(packet, sizeof(packet));
  attempt.sentMicros = micros();
  attempt.pending = ntpUdp.endPacket() == 1;
}

String dstFields(const String &rule) {
  const time_t now = time(nullptr);
  txw_clock_dst_change change{};
  if (!ntpResponseReceived || now <= 1700000000 ||
      static_cast<uint64_t>(now) > UINT32_MAX ||
      !txw_clock_next_dst_change(static_cast<uint32_t>(now), rule.c_str(), &change))
    return String("\"nextDst\":null");
  return String("\"nextDst\":{\"utc\":") + String(change.utc_seconds) +
      ",\"before\":" + String(change.before_minutes) +
      ",\"after\":" + String(change.after_minutes) + "}";
}

bool apiRequestAllowed(bool mutation, bool allowBodyToken);
void previewDst() {
  if (!apiRequestAllowed(true, false)) return;
  String rule = web.arg("timezone"); rule.trim();
  if (rule.length() > 96 ||
      !clock_validation::validPosixTimezone(rule.c_str(), rule.length()) ||
      !txw_clock_timezone_supported(rule.c_str())) {
    web.send(400, "application/json", "{\"error\":\"Use a valid fixed offset or Mmonth.week.day POSIX rule to preview DST.\"}");
    return;
  }
  web.send(200, "application/json", String("{\"timeSynced\":") +
      (ntpResponseReceived ? "true" : "false") + "," + dstFields(rule) + "}");
}

void serviceCloseSleep() {
  if (webSession.active(millis())) {
    closeSleepPending = false;
    return;
  }
  // pagehide also fires on refresh. Give the replacement page time to claim
  // a new session before sleeping; ordinary post-Save sleep has no close flag.
  if (closeSleepPending && millis() - closeSleepRequestedAt < 5000u) return;
  if ((!closeSleepPending && !saveSleepPending) || sleepMessageSent || restartScheduled ||
      factoryResetPending || !ntpResponseReceived || !timeRecordsSent ||
      !timeConfirmation.confirmed()) return;
  Serial.flush(); // Complete the new +TIME on the wire before SLEEP.
  Serial.print("SLEEP\r\n");
  Serial.flush();
  sleepMessageSent = true;
  closeSleepPending = false;
  saveSleepPending = false;
}
