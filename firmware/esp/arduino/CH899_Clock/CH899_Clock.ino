/*
  Copyright (C) 2026 Steve Madden
  SPDX-License-Identifier: GPL-3.0-or-later

  CH899 Clock replacement ESP8285 firmware

  Known compatible UART protocol:
    MM32 -> ESP: USER\n
    MM32 -> ESP: CLEAN\n
    ESP  -> MM32: USER_OK\r\n
    ESP  -> MM32: CLEAN_OK\r\n
    ESP  -> MM32: +TICK\r\n
    ESP  -> MM32: +TIME:Tue Sep  8 12:53:31 2026 +0100 10:00\r\n
  Serial is reserved for the MM32 clock controller.
*/

#include <Arduino.h>
#include <DNSServer.h>
#include <EEPROM.h>
#include <ESP8266WebServer.h>
#include <ESP8266WiFi.h>
#include <time.h>
#include <sys/time.h>
#include <WiFiUdp.h>
extern "C" {
#include "clock_calendar.h"
#include "clock_ntp_packet.h"
}
#include "clean_reset_gate.h"
#include "clock_validation.h"
#include "clock_protocol.h"
#include "clock_session.h"
#include "web_ui.h"

// Requires Arduino IDE Flash Size: "Mapping defined by Hardware and Sketch".
// This selects the hardware-sized map without a filesystem. The web page is
// compiled into flash; settings live in EEPROM. OTA is deliberately omitted
// from this application, not prevented by the flash map itself.
FLASH_MAP_SETUP_CONFIG(FLASH_MAP_NO_FS)

namespace {
constexpr uint32_t MM32_BAUD = 38400; // Matched to MM32 RC6AL; not the ROM flashing baud.
// A normal MM32-scheduled wake is short.  Give a saved network enough time to
// obtain DHCP. The setup AP remains available throughout every powered wake.
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 10000;
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 15000;
constexpr uint32_t NTP_TIMEOUT_MS = 5000;
constexpr uint32_t DAILY_SYNC_MS = 24UL * 60UL * 60UL * 1000UL;
constexpr uint32_t TIME_ANNOUNCE_INTERVAL_MS = 1000;
constexpr uint32_t MM32_TICK_INTERVAL_MS = 2000;
constexpr uint32_t WEB_SESSION_TIMEOUT_MS = 10000;
constexpr uint32_t WEB_SESSION_MAX_MS = 60UL * 1000UL;
constexpr uint32_t CLEAN_CONFIRM_MIN_MS = 1000;
constexpr uint32_t CLEAN_CONFIRM_MAX_MS = 4000;
constexpr uint32_t FACTORY_WIFI_CLEAR_DELAY_MS = 50;
constexpr uint32_t RESTART_DELAY_MS = 250;
// In the observed stock M.SET session, the ESP repeats the time record once
// per second after NTP succeeds. The MM32 ends the wake session; this firmware
// never drives a sleep pin.
constexpr char FIRMWARE_VERSION[] = "WiFi Clock v1.5";
constexpr char AP_NAME[] = "WiFi-Clock-Setup";
constexpr char DEFAULT_NTP_HOST[] = "pool.ntp.org";
constexpr char DEFAULT_NTP_BACKUP[] = "";
constexpr char DEFAULT_TIMEZONE[] = "GMT0BST,M3.5.0/1,M10.5.0/2";
constexpr size_t EEPROM_BYTES = 512;
constexpr uint32_t LEGACY_CONFIG_MAGIC = 0x43483939;  // "CH99"
constexpr uint32_t PREVIOUS_CONFIG_MAGIC = 0x4348393A;
constexpr uint32_t EXTENDED_CONFIG_MAGIC = 0x4348393B;
constexpr uint32_t CONFIG_MAGIC = 0x4348393C;

DNSServer captiveDns;
ESP8266WebServer web(80);

struct ClockConfig {
  String ssid;
  String password;
  String ntpHost = DEFAULT_NTP_HOST;
  String ntpBackupHost = DEFAULT_NTP_BACKUP;
  // POSIX TZ rule; this default handles UK GMT/BST correctly.
  String timezone = DEFAULT_TIMEZONE;
  uint8_t syncHour = 10;
  uint8_t syncMinute = 0;
  uint8_t movementMode = 0;
  uint8_t secondsParking = 0;
} config;

struct LegacyStoredConfig {
  uint32_t magic;
  char ssid[33];
  char password[65];
  char ntpHost[254];
  char timezone[97];
  uint8_t syncHour;
  uint8_t syncMinute;
  uint32_t checksum;
};
struct PreviousStoredConfig {
  uint32_t magic;
  char ssid[33];
  char password[65];
  char ntpHost[254];
  char timezone[97];
  uint8_t syncHour;
  uint8_t syncMinute;
  uint8_t movementMode;
  uint8_t secondsParking;
  uint32_t checksum;
};
struct StoredConfig {
  uint32_t magic;
  char ssid[33];
  char password[65];
  char ntpHost[128];
  char ntpBackupHost[128];
  char timezone[97];
  uint8_t syncHour, syncMinute, movementMode, secondsParking;
  uint32_t checksum;
};
static_assert(offsetof(PreviousStoredConfig, syncMinute) == offsetof(LegacyStoredConfig, syncMinute), "Legacy layout changed");
static_assert(sizeof(StoredConfig) <= EEPROM_BYTES, "Settings exceed EEPROM allocation");
// Keep Arduino's generated prototypes from referring to ClockConfig before
// its definition when preprocessing this sketch.
bool saveConfig(const ClockConfig &candidate);
void scheduleRestart();

enum class NetworkState { Offline, Portal, Connecting, Connected, WaitingForNtp };
NetworkState networkState = NetworkState::Offline;
bool portalActive = false;
bool configurationUsable = false;
bool ntpRequested = false;
bool ntpFallbackAttempted = false;
bool ntpResponseReceived = false;
bool timeAnnouncementActive = false;
bool firstTimeAnnouncementPending = false;
ClockWebSession webSession(MM32_TICK_INTERVAL_MS, WEB_SESSION_TIMEOUT_MS, WEB_SESSION_MAX_MS);
bool scanRequested = false;
bool scanRunning = false;
bool scanReady = false;
bool scanFailed = false;
String scanResultJson;
uint32_t scanCompletedAt = 0;
constexpr uint32_t SCAN_CACHE_MS = 15000;
String requestToken;
bool restartScheduled = false;
bool factoryResetPending = false;
bool settingsEraseUncommitted = false;
bool sdkCredentialsCleared = false;
bool cleanResetArmed = false;
uint32_t cleanResetArmedAt = 0;
uint32_t restartScheduledAt = 0;
uint32_t connectStartedAt = 0;
uint32_t networkRetryStartedAt = 0;
uint32_t ntpStartedAt = 0;
uint32_t lastSyncAt = 0;
uint32_t lastTimeAnnouncementAt = 0;
uint32_t timeRecordsSent = 0;
bool closeSleepPending = false;
uint32_t closeSleepRequestedAt = 0;
bool sleepMessageSent = false;
constexpr size_t UART_LINE_CAPACITY = 96; // Complete MM32 +TIME echoes, not only short commands.
char uartLine[UART_LINE_CAPACITY] = {};
size_t uartLineLength = 0;
bool uartLineDiscarding = false;
#include "esp_ui_backend.h"

uint32_t configChecksum(const uint8_t *data, const size_t length) {
  uint32_t hash = 2166136261UL;
  for (size_t i = 0; i < length; ++i) hash = (hash ^ data[i]) * 16777619UL;
  return hash;
}

void copyText(char *destination, const size_t destinationSize, const String &source) {
  const size_t count = min(destinationSize - 1, source.length());
  memcpy(destination, source.c_str(), count);
  destination[count] = '\0';
}

String jsonEscape(const String &input) {
  String result;
  result.reserve(input.length() + 8);
  for (size_t i = 0; i < input.length(); ++i) {
    const uint8_t c = static_cast<uint8_t>(input[i]);
    if (c < 0x20) {
      char escaped[7];
      snprintf(escaped, sizeof(escaped), "\\u%04x", static_cast<unsigned>(c));
      result += escaped;
    } else {
      if (c == '"' || c == '\\') result += '\\';
      result += static_cast<char>(c);
    }
  }
  return result;
}

String deviceHostname() {
  // Match HC32: uppercase, zero-padded final three station MAC bytes.
  uint8_t mac[6];
  WiFi.macAddress(mac);
  char hostname[18];
  snprintf(hostname, sizeof(hostname), "WiFi-Clock-%02X%02X%02X",
           static_cast<unsigned>(mac[3]), static_cast<unsigned>(mac[4]),
           static_cast<unsigned>(mac[5]));
  return String(hostname);
}

String deviceSetupName() {
  return String(AP_NAME);
}

String normalizeHost(String host) {
  host.toLowerCase();
  if (host.endsWith(":80")) host.remove(host.length() - 3);
  return host;
}

bool knownHost(const String &host) {
  if (host == normalizeHost(deviceHostname())) return true;
  if (portalActive && host == WiFi.softAPIP().toString()) return true;
  return WiFi.status() == WL_CONNECTED && host == WiFi.localIP().toString();
}

void responseHeaders() {
  web.sendHeader("Cache-Control", "no-store");
  web.sendHeader("X-Content-Type-Options", "nosniff");
  web.sendHeader("X-Frame-Options", "DENY");
  web.sendHeader("Referrer-Policy", "no-referrer");
}

bool apiRequestAllowed(bool needsToken, bool allowBodyToken) {
  responseHeaders();
  const String host = normalizeHost(web.hostHeader());
  if (!knownHost(host)) {
    web.send(403, "application/json", "{\"error\":\"Open the clock using its IP address\"}");
    return false;
  }
  String origin = web.header("Origin");
  origin.toLowerCase();
  if (!origin.isEmpty() && (!origin.startsWith("http://") ||
      normalizeHost(origin.substring(7)) != host)) {
    web.send(403, "application/json", "{\"error\":\"Request must come from the clock setup page\"}");
    return false;
  }
  const bool validToken = !requestToken.isEmpty() &&
      (web.header("X-Clock-Token") == requestToken ||
       (allowBodyToken && web.method() == HTTP_POST && web.arg("token") == requestToken));
  if (needsToken && !validToken) {
    web.send(403, "application/json", "{\"error\":\"This page has expired. Reconnect and refresh it\"}");
    return false;
  }
  return true;
}

void createRequestToken() {
  uint8_t bytes[16];
  ESP.random(bytes, sizeof(bytes));
  char token[33];
  const char digits[] = "0123456789abcdef";
  for (size_t i = 0; i < sizeof(bytes); ++i) {
    token[i * 2] = digits[bytes[i] >> 4];
    token[i * 2 + 1] = digits[bytes[i] & 15];
  }
  token[32] = 0;
  requestToken = token;
}

bool safeText(const String &input, const size_t maxLength) {
  if (input.length() > maxLength) return false;
  for (size_t i = 0; i < input.length(); ++i) {
    if (static_cast<uint8_t>(input[i]) < 0x20) return false;
  }
  return true;
}

bool parseScheduleValue(const String &text, uint8_t maximum, uint8_t &value) {
  return clock_validation::parseScheduleValue(text.c_str(), text.length(), maximum, value);
}

bool loadConfig() {
  PreviousStoredConfig stored{};
  uint32_t magic = 0;
  EEPROM.get(0, magic);
  String backup = DEFAULT_NTP_BACKUP;
  if (magic == CONFIG_MAGIC) {
    StoredConfig current{};
    EEPROM.get(0, current);
    if (current.checksum != configChecksum(reinterpret_cast<const uint8_t *>(&current), offsetof(StoredConfig, checksum)) ||
        !memchr(current.ssid, 0, sizeof(current.ssid)) ||
        !memchr(current.password, 0, sizeof(current.password)) ||
        !memchr(current.ntpHost, 0, sizeof(current.ntpHost)) ||
        !memchr(current.ntpBackupHost, 0, sizeof(current.ntpBackupHost)) ||
        !memchr(current.timezone, 0, sizeof(current.timezone))) return false;
    copyText(stored.ssid, sizeof(stored.ssid), current.ssid);
    copyText(stored.password, sizeof(stored.password), current.password);
    copyText(stored.ntpHost, sizeof(stored.ntpHost), current.ntpHost);
    copyText(stored.timezone, sizeof(stored.timezone), current.timezone);
    stored.syncHour = current.syncHour; stored.syncMinute = current.syncMinute;
    stored.movementMode = current.movementMode; stored.secondsParking = current.secondsParking;
    backup = current.ntpBackupHost;
  } else {
    EEPROM.get(0, stored);
    const bool legacy = magic == LEGACY_CONFIG_MAGIC;
    if (legacy || magic == PREVIOUS_CONFIG_MAGIC) {
      LegacyStoredConfig previous{};
      EEPROM.get(0, previous);
      if (previous.checksum != configChecksum(reinterpret_cast<const uint8_t *>(&previous), offsetof(LegacyStoredConfig, checksum))) return false;
      stored.movementMode = 0; stored.secondsParking = 1;
      if (legacy) stored.syncMinute = 0;
    } else if (magic != EXTENDED_CONFIG_MAGIC || stored.checksum !=
        configChecksum(reinterpret_cast<const uint8_t *>(&stored), offsetof(PreviousStoredConfig, checksum))) return false;
  }
  if (stored.syncHour > 23 || stored.syncMinute > 59 ||
      stored.movementMode > 3 || stored.secondsParking > 2 ||
      !memchr(stored.ssid, 0, sizeof(stored.ssid)) ||
      !memchr(stored.password, 0, sizeof(stored.password)) ||
      !memchr(stored.ntpHost, 0, sizeof(stored.ntpHost)) ||
      !memchr(stored.timezone, 0, sizeof(stored.timezone))) return false;
  if (!safeText(stored.ssid, 32) || !safeText(stored.password, 64) ||
      !safeText(stored.ntpHost, 253) || !safeText(stored.timezone, 96)) return false;
  config.ssid = stored.ssid; config.password = stored.password;
  config.ntpHost = stored.ntpHost[0] ? stored.ntpHost : DEFAULT_NTP_HOST;
  config.ntpBackupHost = backup.isEmpty() ? String(DEFAULT_NTP_BACKUP) : backup;
  config.timezone = stored.timezone[0] ? stored.timezone : DEFAULT_TIMEZONE;
  config.syncHour = stored.syncHour; config.syncMinute = stored.syncMinute;
  config.movementMode = stored.movementMode; config.secondsParking = stored.secondsParking;
  // No EEPROM write on migration. Old five-minute schedules remain active
  // until an explicit save; the unchanged HC32 page explains its rounding.
  return !config.ssid.isEmpty() && config.ntpHost.length() <= 127 &&
      config.ntpBackupHost.length() <= 127 &&
      clock_validation::validNtpHost(config.ntpHost.c_str(), config.ntpHost.length()) &&
      (config.ntpBackupHost.isEmpty() || clock_validation::validNtpHost(config.ntpBackupHost.c_str(), config.ntpBackupHost.length())) &&
      clock_validation::validPosixTimezone(config.timezone.c_str(), config.timezone.length()) &&
      txw_clock_timezone_supported(config.timezone.c_str());
}

bool saveConfig(const ClockConfig &candidate) {
  StoredConfig stored{};
  stored.magic = CONFIG_MAGIC;
  copyText(stored.ssid, sizeof(stored.ssid), candidate.ssid);
  copyText(stored.password, sizeof(stored.password), candidate.password);
  copyText(stored.ntpHost, sizeof(stored.ntpHost), candidate.ntpHost);
  copyText(stored.ntpBackupHost, sizeof(stored.ntpBackupHost), candidate.ntpBackupHost);
  copyText(stored.timezone, sizeof(stored.timezone), candidate.timezone);
  stored.syncHour = candidate.syncHour;
  stored.syncMinute = candidate.syncMinute;
  stored.movementMode = candidate.movementMode;
  stored.secondsParking = candidate.secondsParking;
  stored.checksum = configChecksum(reinterpret_cast<const uint8_t *>(&stored), offsetof(StoredConfig, checksum));
  EEPROM.put(0, stored);
  return EEPROM.commit();
}

bool eraseSavedConfig() {
  for (size_t address = 0; address < EEPROM_BYTES; ++address) {
    EEPROM.write(address, 0xFF);
  }
  settingsEraseUncommitted = !EEPROM.commit();
  return !settingsEraseUncommitted;
}

bool hasSavedConfig() {
  // Unusable/corrupt settings still need erasing. Only an actually blank
  // EEPROM may acknowledge repeated CLEAN without another flash write.
  if (settingsEraseUncommitted) return true;
  for (size_t address = 0; address < EEPROM_BYTES; ++address)
    if (EEPROM.read(address) != 0xFF) return true;
  return false;
}

bool prepareFactoryReset() {
  saveSleepPending = false;
  clearSaveSleepTicket();
  // Quiesce every protocol producer before the potentially slow flash commit.
  // USER requests can still be acknowledged by the UART parser while the
  // deferred restart is pending.
  timeAnnouncementActive = false;
  firstTimeAnnouncementPending = false;
  ntpRequested = false;
  stopNtpTransport();
  ntpResponseReceived = false;
  webSession.stop();
  scanRequested = false;
  scanReady = false;
  scanFailed = false;
  scanResultJson = String();

  if (!eraseSavedConfig()) return false;
  config = ClockConfig{};
  configurationUsable = false;
  factoryResetPending = true;
  sdkCredentialsCleared = false;
  return true;
}

void acknowledgeClean() {
  Serial.print(F("CLEAN_OK\r\n"));
  // The stock firmware restarts shortly after the acknowledgement. Ensure the
  // complete record has physically left the UART before starting that timer.
  Serial.flush();
}

void startPortal() {
  if (!portalActive) {
    WiFi.mode(WIFI_AP_STA);
    const String apName = deviceSetupName();
    WiFi.softAP(apName.c_str());
    captiveDns.start(53, "*", WiFi.softAPIP());
    portalActive = true;
  }
  networkState = NetworkState::Portal;
}

void discardWifiScan() {
  scanRequested = false;
  scanReady = false;
  scanFailed = false;
  scanResultJson = String();
  // scanDelete() frees results, but does not cancel an SDK scan in progress.
  // Keep tracking that scan until completion, then discard its late results.
  // Never wait here: MM32 UART handling must remain responsive while offline.
  if (scanRunning && WiFi.scanComplete() == WIFI_SCAN_RUNNING) return;
  scanRunning = false;
  WiFi.scanDelete();
}

void beginStationConnection() {
  if (!configurationUsable || config.ssid.isEmpty()) {
    if (!portalActive) startPortal();
    return;
  }
  WiFi.mode(WIFI_AP_STA); // Keep setup reachable while joining saved Wi-Fi.
  WiFi.begin(config.ssid.c_str(), config.password.c_str());
  connectStartedAt = millis();
  networkState = NetworkState::Connecting;
}

void beginNetworkWake() {
  if (!configurationUsable) WiFi.disconnect(false, true);
  startPortal(); // Every wake, including successful scheduled Wi-Fi wakes.
  if (configurationUsable) beginStationConnection();
}

void sendTimeToClock(const tm &localTime) {
  char timeText[48];
  if (!strftime(timeText, sizeof(timeText), "%a %b %e %T %Y %z", &localTime)) return;
  const time_t now = time(nullptr);
  uint8_t wakeHour = config.syncHour, wakeMinute = config.syncMinute;
  bool dstPending = false;
  // RC6AU queues a flagged upcoming-offset TIME until old RTC :00.
  // Keep current seconds; never transmit the future boundary timestamp.
  if (now > 1700000000 && static_cast<uint64_t>(now) <= UINT32_MAX) {
    dstPending = txw_clock_upcoming_dst_text(static_cast<uint32_t>(now), config.timezone.c_str(),
        timeText, sizeof(timeText));
    txw_clock_next_wake(static_cast<uint32_t>(now), config.timezone.c_str(),
        config.syncHour, config.syncMinute, &wakeHour, &wakeMinute);
  }
  char record[64];
  const size_t length = formatMm32Time(record, sizeof(record), timeText,
      wakeHour, wakeMinute, config.movementMode, config.secondsParking, dstPending);
  if (length) {
    if (Serial.write(reinterpret_cast<const uint8_t *>(record), length) == length) {
      timeConfirmation.recordSent(record, length, millis());
      ++timeRecordsSent;
    } else timeConfirmation.transmitFailed();
  } else timeConfirmation.transmitFailed();
}

void serviceWebSession() {
  if (networkState == NetworkState::Offline) {
    webSession.stop();
    return;
  }
  if (webSession.takeTick(millis())) Serial.print("+TICK\r\n");
}

void beginTimeAnnouncement() {
  timeAnnouncementActive = true;
  firstTimeAnnouncementPending = true;
  const uint32_t nowMs = millis();
  lastTimeAnnouncementAt = nowMs;
}

void serviceTimeAnnouncement() {
  if (!timeAnnouncementActive || restartScheduled) return;
  // Save confirmation gets at most five fresh TIME attempts. A received
  // match stays valid while an active page defers SLEEP; do not overwrite it.
  if (saveSleepPending && !timeConfirmation.canSend()) return;

  const uint32_t nowMs = millis();
  if (firstTimeAnnouncementPending) {
    firstTimeAnnouncementPending = false;
    const bool pageIsActive = webSession.active(nowMs);
    if (pageIsActive) {
      // Give the MM32 a full second to process a page-session keepalive before
      // it receives the first time-completion record.
      Serial.print("+TICK\r\n");
      webSession.markTick(nowMs);
      lastTimeAnnouncementAt = nowMs;
      return;
    }
  }
  if (nowMs - lastTimeAnnouncementAt < TIME_ANNOUNCE_INTERVAL_MS - 25u) return;

  timeval precise{};
  if (gettimeofday(&precise, nullptr) != 0 || precise.tv_sec <= 1700000000 ||
      precise.tv_usec > 20000) return; // Missed this edge: wait for the next, never send late.
  Serial.flush(); // Drain older TICK/ACK bytes before the whole-second TIME.
  if (gettimeofday(&precise, nullptr) != 0 || precise.tv_usec > 20000) return;
  const time_t now = precise.tv_sec;
  tm localTime{};
  localtime_r(&now, &localTime);
  sendTimeToClock(localTime);
  lastTimeAnnouncementAt = nowMs;
}

void beginNtpSync() {
  if (WiFi.status() != WL_CONNECTED) return;
  ntpRequested = true; ntpResponseReceived = false;
  ntpFallbackAttempted = false; ntpStartedAt = millis();
  timeAnnouncementActive = false; firstTimeAnnouncementPending = false;
  timeRecordsSent = 0; sleepMessageSent = false;
  timeConfirmation.reset();
  networkState = NetworkState::WaitingForNtp;
  stopNtpTransport();
  ntpUdp.begin(0);
  setenv("TZ", config.timezone.c_str(), 1); tzset();
  startNtpAttempt(0);
}

void serviceNtp() {
  if (!ntpRequested || WiFi.status() != WL_CONNECTED) return;
  // Both requests remain valid: first validated response wins.
  for (unsigned packets = 0; packets < 4; ++packets) {
    const int length = ntpUdp.parsePacket();
    if (length <= 0) break;
    const uint32_t receivedMicros = micros();
    uint8_t packet[48];
    const IPAddress from = ntpUdp.remoteIP();
    const uint16_t port = ntpUdp.remotePort();
    const int got = ntpUdp.read(packet, sizeof(packet));
    while (ntpUdp.available()) ntpUdp.read();
    if (got != 48 || port != 123) continue;
    uint32_t utc = 0, usec = 0;
    for (unsigned i = 0; i < 2; ++i) {
      if (!ntpAttempts[i].pending || from != ntpAttempts[i].ip ||
          !txw_ntp_parse_precise(packet, sizeof(packet), ntpAttempts[i].nonce,
              receivedMicros - ntpAttempts[i].sentMicros, &utc, &usec) ||
          utc > 4102444799UL) continue; // MM32 supports 2000..2099.
      usec += micros() - receivedMicros;
      timeval value{static_cast<time_t>(utc + usec / 1000000u), static_cast<long>(usec % 1000000u)};
      if (settimeofday(&value, nullptr) != 0) continue;
      ntpResponseReceived = true; ntpRequested = false; lastSyncAt = millis();
      networkState = NetworkState::Connected;
      stopNtpTransport();
      beginTimeAnnouncement();
      return;
    }
  }
  const uint32_t elapsed = millis() - ntpStartedAt;
  if (!ntpFallbackAttempted && elapsed >= NTP_TIMEOUT_MS) {
    ntpFallbackAttempted = true;
    startNtpAttempt(1);
  }
  // Bounded retry cadence, still accepting late valid replies for this wake.
  for (unsigned i = 0; i < 2; ++i) {
    if ((i == 0 || ntpFallbackAttempted) &&
        millis() - ntpAttempts[i].sentAt >= 15000) startNtpAttempt(i);
  }
}

void enterNetworkRetry() {
  // Never announce stale time or use an earlier acquisition's confirmation.
  // Retain Save intent, credentials, AP and page ownership for this wake.
  timeAnnouncementActive = false;
  firstTimeAnnouncementPending = false;
  ntpRequested = false;
  ntpResponseReceived = false;
  timeRecordsSent = 0;
  timeConfirmation.reset();
  stopNtpTransport();
  WiFi.disconnect(false);
  networkRetryStartedAt = millis();
  startPortal();
}

void serviceNetwork() {
  if (networkState == NetworkState::Offline || restartScheduled ||
      factoryResetPending || sleepMessageSent) return;
  if (networkState == NetworkState::Connecting) {
    if (WiFi.status() == WL_CONNECTED) {
      beginNtpSync();
    } else if (millis() - connectStartedAt >= WIFI_CONNECT_TIMEOUT_MS) {
      enterNetworkRetry();
    }
    return;
  }
  if ((networkState == NetworkState::Connected ||
       networkState == NetworkState::WaitingForNtp) && WiFi.status() != WL_CONNECTED) {
    enterNetworkRetry();
    return;
  }
  if (networkState == NetworkState::Portal && configurationUsable && !config.ssid.isEmpty()) {
    if (WiFi.status() == WL_CONNECTED) {
      beginNtpSync(); // SDK recovered the link while the setup AP stayed open.
    } else if (millis() - networkRetryStartedAt >= WIFI_RETRY_INTERVAL_MS &&
               !webSession.active(millis()) && !scanRunning && !scanRequested) {
      beginStationConnection();
    }
    return;
  }
  if (networkState == NetworkState::Connected &&
      millis() - lastSyncAt > DAILY_SYNC_MS) beginNtpSync();
}

void handleUartLine(const char *line) {
  if (timeConfirmation.acceptEcho(line, millis())) return;
  if (strcmp(line, "USER") == 0) {
    Serial.print(F("USER_OK\r\n"));
  } else if (strcmp(line, "CLEAN") == 0) {
    // Stock does not act on the first CLEAN: it waits for the MM32's repeat at
    // roughly two seconds. This confirmation prevents a damaged or isolated
    // line from erasing settings. Once blank, acknowledge retries without
    // another flash write or software-restart loop.
    if (factoryResetPending) {
      acknowledgeClean();
      return;
    }

    const uint32_t nowMs = millis();
    const uint32_t elapsedMs = nowMs - cleanResetArmedAt;
    const clock_protocol::CleanDecision decision = clock_protocol::decideClean(
        hasSavedConfig(), cleanResetArmed, elapsedMs,
        CLEAN_CONFIRM_MIN_MS, CLEAN_CONFIRM_MAX_MS);

    switch (decision) {
      case clock_protocol::CleanDecision::AcknowledgeOnly:
        cleanResetArmed = false;
        acknowledgeClean();
        return;
      case clock_protocol::CleanDecision::Arm:
      case clock_protocol::CleanDecision::Rearm:
        cleanResetArmed = true;
        cleanResetArmedAt = nowMs;
        return;
      case clock_protocol::CleanDecision::Wait:
        return;
      case clock_protocol::CleanDecision::Confirm:
        cleanResetArmed = false;
        if (!prepareFactoryReset()) return;  // No acknowledgement: MM32 retries.
        acknowledgeClean();
        scheduleRestart();
        return;
    }
  }
  // Intentionally ignore unknown commands until they are captured and decoded.
}

void serviceMm32Uart() {
  while (Serial.available()) {
    const char received = static_cast<char>(Serial.read());
    if (received == '\r') continue;
    if (received == '\n') {
      if (!uartLineDiscarding && uartLineLength) {
        uartLine[uartLineLength] = '\0';
        handleUartLine(uartLine);
      }
      uartLineLength = 0;
      uartLineDiscarding = false;
    } else if (static_cast<uint8_t>(received) < 0x20 ||
               static_cast<uint8_t>(received) > 0x7E) {
      // Embedded NUL/control/noise bytes must not truncate into USER/CLEAN.
      uartLineLength = 0;
      uartLineDiscarding = true;
    } else if (!uartLineDiscarding) {
      if (uartLineLength + 1 < UART_LINE_CAPACITY) {
        uartLine[uartLineLength++] = received;
      } else {
        // Discard the complete oversized record. Never treat its tail as a
        // fresh command after noise or an unexpected future message.
        uartLineLength = 0;
        uartLineDiscarding = true;
      }
    }
  }
}

void serveIndex() {
  responseHeaders();
  if (!knownHost(normalizeHost(web.hostHeader()))) {
    // Captive-portal probes use unrelated hostnames. Move the actual page to
    // this socket's local IP so its API origin can be checked unambiguously.
    web.sendHeader("Location", String("http://") + web.client().localIP().toString() + "/");
    web.send(302, "text/plain", "Open the clock setup page");
    return;
  }
  web.sendHeader("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
  web.send_P(200, PSTR("text/html; charset=utf-8"), CLOCK_WEB_UI);
}

void keepWebSessionAlive() {
  if (!apiRequestAllowed(true, false)) return;
  // A request already buffered before disconnection must not revive a session.
  if (networkState == NetworkState::Offline) {
    web.send(503, "application/json", "{\"error\":\"Wi-Fi is off for this wake\"}");
    return;
  }
  const String page = web.arg("page");
  if (!ClockWebSession::validId(page.c_str())) {
    web.send(400, "application/json", "{\"error\":\"Invalid page session\"}");
    return;
  }
  webSession.note(page.c_str(), web.arg("start") == "1", millis());
  web.send(204, "text/plain", "");
}

void closeWebSession() {
  if (!apiRequestAllowed(true, true)) return;
  const String page = web.arg("page");
  if (!ClockWebSession::validId(page.c_str())) {
    web.send(400, "application/json", "{\"error\":\"Invalid page session\"}");
    return;
  }
  webSession.close(page.c_str());
  if (!webSession.active(millis()) && !closeSleepPending) {
    closeSleepRequestedAt = millis();
    closeSleepPending = true;
  }
  web.send(204, "text/plain", "");
}

void scheduleRestart() {
  restartScheduled = true;
  restartScheduledAt = millis();
}

void serviceRestart() {
  if (!restartScheduled) return;
  const uint32_t elapsed = millis() - restartScheduledAt;
  if (factoryResetPending && !sdkCredentialsCleared &&
      elapsed >= FACTORY_WIFI_CLEAR_DELAY_MS) {
    // Our credentials live in EEPROM, but an application-only flash can leave
    // old SDK station credentials behind. Clear those persistently as part of
    // Factory reset without claiming to erase every historical flash byte.
    WiFi.persistent(true);
    WiFi.disconnect(true, true);
    WiFi.persistent(false);
    sdkCredentialsCleared = true;
  }
  if (elapsed >= RESTART_DELAY_MS) ESP.restart();
}

void eraseConfigAndRestart() {
  if (!apiRequestAllowed(true, false)) return;
  if (restartScheduled) {
    web.send(409, "application/json", "{\"error\":\"Clock is restarting\"}");
    return;
  }
  if (!prepareFactoryReset()) {
    web.send(500, "application/json", "{\"error\":\"settings could not be erased\"}");
    return;
  }
  web.send(202, "application/json", "{\"reset\":\"scheduled\"}");
  scheduleRestart();
}

void sendStatus() {
  if (!apiRequestAllowed(false, false)) return;
  const bool connected = WiFi.status() == WL_CONNECTED;
  const char *mode = connected ? "station" : (portalActive ? "portal" : "offline");
  const String body = String("{\"apiVersion\":1,\"mode\":\"") + mode +
      "\",\"firmwareVersion\":\"" + FIRMWARE_VERSION +
      "\",\"buildId\":\"ESP8285 MM32 v1.5 R12 20261023\",\"ip\":\"" +
      (connected ? WiFi.localIP().toString() : WiFi.softAPIP().toString()) +
      "\",\"connected\":" + (connected ? "true" : "false") +
      ",\"timeSynced\":" + (ntpResponseReceived ? "true" : "false") +
      ",\"timezone\":\"" + jsonEscape(config.timezone) + "\"," +
      dstFields(config.timezone) + "}";
  web.send(200, "application/json", body);
}

void sendConfig() {
  if (!apiRequestAllowed(false, false)) return;
  const String body = String("{\"ssid\":\"") + jsonEscape(config.ssid) +
      "\",\"ntpHost\":\"" + jsonEscape(config.ntpHost) +
      "\",\"ntpBackupHost\":\"" + jsonEscape(config.ntpBackupHost) +
      "\",\"timezone\":\"" + jsonEscape(config.timezone) +
      "\",\"syncHour\":" + String(config.syncHour) +
      ",\"syncMinute\":" + String(config.syncMinute) +
      ",\"movementMode\":" + String(config.movementMode) +
      ",\"secondsParking\":" + String(config.secondsParking) +
      ",\"minuteHand\":\"" + (config.movementMode & 1 ? "jump" : "gradual") +
      "\",\"secondHand\":\"" + (config.movementMode & 2 ? "pause_at_12" : "continuous") +
      "\",\"nightParking\":\"" + (config.secondsParking == 2 ? "on" : config.secondsParking == 1 ? "night" : "off") +
      "\",\"hasPassword\":" + (config.password.isEmpty() ? "false" : "true") +
      ",\"requestToken\":\"" + requestToken + "\"}";
  web.send(200, "application/json", body);
}

void updateConfig() {
  if (!apiRequestAllowed(true, false)) return;
  if (restartScheduled) {
    web.send(409, "application/json", "{\"error\":\"Clock is restarting\"}");
    return;
  }
  const String ssid = web.arg("ssid");
  const String password = web.arg("password");
  String ntpHost = web.arg("ntpHost");
  String ntpBackupHost = web.arg("ntpBackupHost");
  String timezone = web.arg("timezone");
  ntpHost.trim(); ntpBackupHost.trim();
  timezone.trim();
  if (ntpHost.isEmpty()) ntpHost = DEFAULT_NTP_HOST;
  if (ntpBackupHost.isEmpty()) ntpBackupHost = DEFAULT_NTP_BACKUP;
  if (timezone.isEmpty()) timezone = DEFAULT_TIMEZONE;
  uint8_t syncHour = 0;
  uint8_t syncMinute = 0;
  uint8_t movementMode = 0, secondsParking = 0;
  const String minuteHand = web.arg("minute_hand"), secondHand = web.arg("second_hand");
  const String parking = web.arg("night_parking");
  if (minuteHand == "jump") movementMode |= 1;
  if (secondHand == "pause_at_12") movementMode |= 2;
  if (parking == "night") secondsParking = 1;
  if (parking == "on") secondsParking = 2;
  if (ssid.isEmpty() || !safeText(ssid, 32) || !safeText(password, 64) ||
      !safeText(ntpHost, 127) || !safeText(ntpBackupHost, 127) || !safeText(timezone, 96) ||
      !parseScheduleValue(web.arg("syncHour"), 23, syncHour) ||
      !parseScheduleValue(web.arg("syncMinute"), 59, syncMinute) ||
      !clock_validation::supportedDailyUpdate(syncHour, syncMinute) ||
      (minuteHand != "gradual" && minuteHand != "jump") ||
      (secondHand != "continuous" && secondHand != "pause_at_12") ||
      (parking != "off" && parking != "night" && parking != "on")) {
    web.send(400, "application/json", "{\"error\":\"Invalid configuration\"}");
    return;
  }
  if (!clock_validation::validNtpHost(ntpHost.c_str(), ntpHost.length()) ||
      (!ntpBackupHost.isEmpty() && !clock_validation::validNtpHost(ntpBackupHost.c_str(), ntpBackupHost.length()))) {
    web.send(400, "application/json", "{\"error\":\"Enter an NTP hostname or IPv4 address, without a URL, port or path\"}");
    return;
  }
  if (!clock_validation::validPosixTimezone(timezone.c_str(), timezone.length()) ||
      !txw_clock_timezone_supported(timezone.c_str())) {
    web.send(400, "application/json", "{\"error\":\"Enter a valid POSIX time-zone rule. Daylight-saving rules need both start and end dates\"}");
    return;
  }
  ClockConfig candidate = config;
  // The setup page intentionally does not reveal a saved Wi-Fi password.
  // Retain a blank password only for the SAME network; never reuse another
  // network's credentials. A newly selected open network can then be saved.
  if (!password.isEmpty() || ssid != config.ssid) candidate.password = password;
  candidate.ssid = ssid;
  candidate.ntpHost = ntpHost;
  candidate.ntpBackupHost = ntpBackupHost;
  candidate.timezone = timezone;
  candidate.syncHour = syncHour;
  candidate.syncMinute = syncMinute;
  candidate.movementMode = movementMode;
  candidate.secondsParking = secondsParking;
  if (!saveConfig(candidate)) {
    web.send(500, "application/json", "{\"error\":\"Could not save configuration\"}");
    return;
  }
  config = candidate;
  configurationUsable = true;
  uint32_t savedFingerprint = 0;
  EEPROM.get(offsetof(StoredConfig, checksum), savedFingerprint);
  const bool sleepAfterSave = armSaveSleepTicket(savedFingerprint);
  // Save and schedule the restart in ONE transaction. A lost second browser
  // request must not leave new settings saved but unapplied for this wake.
  web.send(200, "application/json", sleepAfterSave ?
      "{\"saved\":true,\"reboot\":\"scheduled\",\"sleepAfterSave\":true}" :
      "{\"saved\":true,\"reboot\":\"scheduled\",\"sleepAfterSave\":false}");
  scheduleRestart();
}

void serviceWifiScan() {
  if (networkState == NetworkState::Offline) {
    discardWifiScan();
    return;
  }
  if (scanRunning) {
    const int found = WiFi.scanComplete();
    if (found == WIFI_SCAN_RUNNING) return;
    scanRunning = false;
    scanFailed = found < 0;
    if (!scanFailed) {
      scanResultJson = "{\"networks\":[";
      for (int i = 0; i < found && i < 40; ++i) {
        if (i) scanResultJson += ',';
        scanResultJson += "{\"ssid\":\"" + jsonEscape(WiFi.SSID(i)) +
            "\",\"rssi\":" + String(WiFi.RSSI(i)) + "}";
      }
      scanResultJson += "]}";
      scanReady = true;
      scanCompletedAt = millis();
    }
    // Release ALL SDK BSS records even if the page disappeared before polling.
    WiFi.scanDelete();
  }
  if (scanReady && millis() - scanCompletedAt >= SCAN_CACHE_MS) {
    scanResultJson = String();
    scanReady = false;
  }
  if (scanRequested && !restartScheduled && networkState != NetworkState::Connecting) {
    scanRequested = false;
    scanReady = false;
    scanFailed = false;
    scanResultJson = String();
    // A synchronous scan suspends loop(), including MM32 handshakes/ticks.
    // Starting during Connecting also aborts association in core 3.1.2.
    scanRunning = WiFi.scanNetworks(true) == WIFI_SCAN_RUNNING;
    scanFailed = !scanRunning;
  }
}

void scanNetworks() {
  if (!apiRequestAllowed(true, false)) return;
  if (networkState == NetworkState::Offline) {
    web.send(503, "application/json", "{\"error\":\"Wi-Fi is off for this wake\"}");
    return;
  }
  if (web.arg("start") == "1" && !scanRunning) scanRequested = true;
  if (scanRequested || scanRunning) {
    web.send(202, "application/json", "{\"scanning\":true}");
    return;
  }
  if (scanFailed || !scanReady) {
    web.send(503, "application/json", "{\"error\":\"Network scan failed; try again or enter a network manually\"}");
    return;
  }
  web.send(200, "application/json", scanResultJson);
}

void setupWebServer() {
  web.collectHeaders("Origin", "X-Clock-Token");
  web.on("/", HTTP_GET, serveIndex);
  web.on("/api/v1/status", HTTP_GET, sendStatus);
  web.on("/api/v1/dst-preview", HTTP_POST, previewDst);
  web.on("/api/v1/config", HTTP_GET, sendConfig);
  web.on("/api/v1/config", HTTP_POST, updateConfig);
  web.on("/api/v1/scan", HTTP_GET, scanNetworks);
  web.on("/api/v1/keepalive", HTTP_POST, keepWebSessionAlive);
  web.on("/api/v1/session/close", HTTP_POST, closeWebSession);
  web.on("/api/v1/factory-reset", HTTP_POST, eraseConfigAndRestart);
  web.on("/api/v1/reboot", HTTP_POST, []() {
    if (!apiRequestAllowed(true, false)) return;
    web.send(202, "application/json", "{\"reboot\":\"scheduled\"}");
    if (!restartScheduled) scheduleRestart();
  });
  web.on("/generate_204", HTTP_GET, serveIndex);
  web.on("/hotspot-detect.html", HTTP_GET, serveIndex);
  web.onNotFound([]() {
    if (web.uri().startsWith("/api/") || web.method() != HTTP_GET) {
      web.send(404, "application/json", "{\"error\":\"Unknown endpoint\"}");
    } else serveIndex();
  });
  web.begin();
}
}  // namespace

void setup() {
  Serial.begin(MM32_BAUD);
  Serial.setDebugOutput(false);
  WiFi.persistent(false);
  WiFi.setSleepMode(WIFI_NONE_SLEEP);
  // Time is accepted only from the validated UDP NTP transport below.
  EEPROM.begin(EEPROM_BYTES);
  configurationUsable = loadConfig();
  uint32_t savedFingerprint = 0;
  EEPROM.get(offsetof(StoredConfig, checksum), savedFingerprint);
  saveSleepPending = takeSaveSleepTicket(savedFingerprint, configurationUsable);
  const String hostname = deviceHostname();
  WiFi.hostname(hostname.c_str());
  createRequestToken();
  setupWebServer();
  beginNetworkWake();
}

void loop() {
  serviceMm32Uart();
  // Do not accept another slow HTTP body/response after acknowledging restart.
  if (restartScheduled) {
    serviceRestart();
    yield();
    return;
  }
  serviceNetwork();
  serviceNtp();
  serviceTimeAnnouncement();
  serviceWebSession();
  serviceCloseSleep();
  if (portalActive) captiveDns.processNextRequest();
  web.handleClient();
  serviceWifiScan();
  serviceRestart();
  yield();
}
