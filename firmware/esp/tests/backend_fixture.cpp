
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "clock_validation.h"
#include "clock_protocol.h"
extern "C" {
#include "clock_calendar.h"
}
static size_t min(size_t a,size_t b) { return a<b?a:b; }
class String {
  char text[254];
public:
  String(const char *s="") { size_t n=strlen(s);if(n>253)n=253;memcpy(text,s,n);text[n]=0; }
  size_t length() const { return strlen(text); }
  const char *c_str() const { return text; }
  bool isEmpty() const { return !text[0]; }
  char operator[](size_t i) const { return text[i]; }
  bool operator==(const String &other) const { return strcmp(text,other.text)==0; }
  bool operator!=(const String &other) const { return strcmp(text,other.text)!=0; }
  void trim() { size_t n=length();while(n && text[n-1]==' ')text[--n]=0;
    size_t i=0;while(text[i]==' ')++i;if(i)memmove(text,text+i,n-i+1); }
};
struct FakeEEPROM {
  uint8_t bytes[512];bool succeeds=true;unsigned commits=0;
  template<class T> void get(unsigned n,T &value) { memcpy(&value,bytes+n,sizeof(T)); }
  template<class T> void put(unsigned n,const T &value) { memcpy(bytes+n,&value,sizeof(T)); }
  bool commit() { ++commits;return succeeds; }
} EEPROM;
struct FakeWeb {
  const char *mode="0",*park="1",*hour="10",*minute="00",*network="Home",*password="";
  unsigned status=0;
  String arg(const char *key) {
    if(!strcmp(key,"minute_hand"))return strlen(mode)==1 && mode[0]>='0' && mode[0]<='3' ? ((mode[0]-'0')&1 ? "jump":"gradual"):"invalid";
    if(!strcmp(key,"second_hand"))return strlen(mode)==1 && mode[0]>='0' && mode[0]<='3' ? ((mode[0]-'0')&2 ? "pause_at_12":"continuous"):"invalid";
    if(!strcmp(key,"night_parking"))return !strcmp(park,"0")?"off":!strcmp(park,"1")?"night":!strcmp(park,"2")?"on":"invalid";
    if(!strcmp(key,"ntpBackupHost"))return "";
    if(!strcmp(key,"syncHour"))return hour;
    if(!strcmp(key,"syncMinute"))return minute;
    if(!strcmp(key,"ssid"))return network;
    if(!strcmp(key,"password"))return password;
    if(!strcmp(key,"ntpHost"))return "pool.ntp.org";
    if(!strcmp(key,"timezone"))return "GMT0BST,M3.5.0/1,M10.5.0/2";
    return "";
  }
  void send(unsigned code,const char *,const char *) { status=code; }
} web;
unsigned armCalls=0;
bool armSaveSleepTicket(uint32_t){++armCalls;return true;}
bool restartScheduled=false,configurationUsable=false;
bool apiRequestAllowed(bool,bool) { return true; }
void scheduleRestart() { restartScheduled=true; }

constexpr char DEFAULT_NTP_HOST[] = "pool.ntp.org";
constexpr char DEFAULT_NTP_BACKUP[] = "";
constexpr char DEFAULT_TIMEZONE[] = "GMT0BST,M3.5.0/1,M10.5.0/2";
constexpr size_t EEPROM_BYTES = 512;
constexpr uint32_t LEGACY_CONFIG_MAGIC = 0x43483939;
constexpr uint32_t PREVIOUS_CONFIG_MAGIC = 0x4348393A;
constexpr uint32_t EXTENDED_CONFIG_MAGIC = 0x4348393B;
constexpr uint32_t CONFIG_MAGIC = 0x4348393C;
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

static void resetFixture() {
  armCalls=0;
  config=ClockConfig();config.ssid="Home";config.password="saved-secret";
  web=FakeWeb();EEPROM=FakeEEPROM();restartScheduled=false;configurationUsable=true;
}
extern "C" unsigned storageCase(unsigned mode,unsigned park,unsigned hour,unsigned minute) {
  resetFixture();ClockConfig wanted=config;wanted.movementMode=mode;wanted.secondsParking=park;
  wanted.syncHour=hour;wanted.syncMinute=minute;
  if(!saveConfig(wanted))return 1;
  config=ClockConfig();if(!loadConfig())return 2;
  if(config.movementMode!=mode || config.secondsParking!=park || config.syncHour!=hour || config.syncMinute!=minute)return 3;
  if(strcmp(config.password.c_str(),"saved-secret"))return 4;
  EEPROM.bytes[24]^=1;if(loadConfig())return 5;return 0;
}
extern "C" unsigned legacyCase(unsigned version) {
  resetFixture();LegacyStoredConfig old={};old.magic=version?PREVIOUS_CONFIG_MAGIC:LEGACY_CONFIG_MAGIC;
  strcpy(old.ssid,"Home");strcpy(old.password,"saved-secret");strcpy(old.ntpHost,"pool.ntp.org");strcpy(old.timezone,"GMT0BST,M3.5.0/1,M10.5.0/2");
  old.syncHour=10;old.syncMinute=17;old.checksum=configChecksum((uint8_t*)&old,offsetof(LegacyStoredConfig,checksum));
  memset(EEPROM.bytes,255,512);EEPROM.put(0,old);
  if(!loadConfig())return 1;
  if(config.syncMinute!=(version?17:0) || config.movementMode!=0 || config.secondsParking!=1)return 2;
  if(strcmp(config.password.c_str(),"saved-secret") || EEPROM.commits)return 3;
  if(!saveConfig(config))return 4;config=ClockConfig();if(!loadConfig())return 5;return 0;
}
extern "C" unsigned httpCase(unsigned mode,unsigned park,unsigned variant) {
  resetFixture();char m[2]={(char)('0'+mode),0},p[2]={(char)('0'+park),0};web.mode=m;web.park=p;
  web.hour="23";web.minute="50";
  if(variant==1)web.mode="4";if(variant==2)web.park="3";if(variant==3)web.minute="60";
  if(variant==4)web.hour="24";if(variant==5)web.mode="";if(variant==6)web.park="01";
  if(variant==7)EEPROM.succeeds=false;
  if(variant==8){restartScheduled=true;}
  if(variant==9)web.minute="-1";
  updateConfig();
  if(variant) {
    if(armCalls)return 8;
    if(web.status!=(variant==7?500:variant==8?409:400))return 1;
    if(config.movementMode!=0 || config.secondsParking!=0 || config.syncHour!=10)return 2;
    if((variant<7 || variant==9) && EEPROM.commits)return 3;return 0;
  }
  if(armCalls!=1)return 9;
  if(web.status!=200 || !restartScheduled || EEPROM.commits!=1)return 4;
  if(config.movementMode!=mode || config.secondsParking!=park || config.syncHour!=23 || config.syncMinute!=50)return 5;
  if(strcmp(config.password.c_str(),"saved-secret"))return 6;
  config=ClockConfig();if(!loadConfig() || config.movementMode!=mode || config.secondsParking!=park)return 7;
  return 0;
}
char wire[64];
extern "C" unsigned minuteHttpCase(unsigned hour,unsigned minute) {
  resetFixture();char h[4],m[4];
  h[0]='0'+hour/10;h[1]='0'+hour%10;h[2]=0;
  m[0]='0'+minute/10;m[1]='0'+minute%10;m[2]=0;
  web.hour=h;web.minute=m;updateConfig();
  if(web.status!=200 || config.syncHour!=hour || config.syncMinute!=minute || !config.ntpBackupHost.isEmpty())return 1;
  config=ClockConfig();if(!loadConfig() || config.syncHour!=hour || config.syncMinute!=minute || !config.ntpBackupHost.isEmpty())return 2;
  return 0;
}
extern "C" unsigned formatCase(unsigned mode,unsigned park,unsigned hour,unsigned minute) {
  return formatMm32Time(wire,sizeof(wire),"Sat Oct 10 22:15:30 2026 +0100",hour,minute,mode,park);
}

extern "C" unsigned extendedLegacyCase(unsigned mode,unsigned park) {
  resetFixture();PreviousStoredConfig old={};old.magic=EXTENDED_CONFIG_MAGIC;
  strcpy(old.ssid,"Home");strcpy(old.password,"saved-secret");strcpy(old.ntpHost,"ntp.example.com");strcpy(old.timezone,"GMT0BST,M3.5.0/1,M10.5.0/2");
  old.syncHour=10;old.syncMinute=15;old.movementMode=mode;old.secondsParking=park;
  old.checksum=configChecksum((uint8_t*)&old,offsetof(PreviousStoredConfig,checksum));
  EEPROM.put(0,old);if(!loadConfig())return 1;
  if(config.syncMinute!=15 || config.movementMode!=mode || config.secondsParking!=park || EEPROM.commits)return 2;
  if(strcmp(config.password.c_str(),"saved-secret") || strcmp(config.ntpBackupHost.c_str(),DEFAULT_NTP_BACKUP))return 3;
  return 0;
}
