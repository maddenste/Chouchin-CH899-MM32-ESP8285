// Execute the real UDP NTP/session adapter with fake network/clock services.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <new>
#include "clock_validation.h"
#include "clock_session.h"
#include "clock_protocol.h"
extern "C" {
#include "clock_calendar.h"
#include "clock_ntp_packet.h"
}
class String {
  char data[254];
public:
  String(const char *p=""){snprintf(data,sizeof(data),"%s",p);}
  String(long long v){snprintf(data,sizeof(data),"%lld",v);}
  String(unsigned int v):String((long long)v){}
  String(int v):String((long long)v){}
  const char *c_str()const{return data;}
  size_t length()const{return strlen(data);}
  bool isEmpty()const{return !data[0];}
  String operator+(const String &b)const{String out=*this;strncat(out.data,b.data,253-out.length());return out;}
  void trim(){}
};
struct IPAddress {unsigned value=0;bool operator!=(const IPAddress& b)const{return value!=b.value;}};
unsigned nowMs=0,acceptedUtc=0,announcements=0,sleeps=0,randomCounter=0,failedDns=0;
uint32_t millis(){return nowMs;}
uint32_t micros(){return nowMs*1000u;}
typedef long time_t;
struct timeval {time_t tv_sec;long tv_usec;};
time_t time(void*){return acceptedUtc;}
int settimeofday(const timeval *v,void*){acceptedUtc=v->tv_sec;return 0;}
int gettimeofday(timeval *v,void*){v->tv_sec=acceptedUtc;v->tv_usec=(nowMs%1000u)*1000u;return 0;}
int setenv(const char*,const char*,int){return 0;}
void tzset(){}
struct Config {String ntpHost="primary",ntpBackupHost="backup",timezone="GMT0BST,M3.5.0/1,M10.5.0/2";
 uint8_t syncHour=10,syncMinute=0,movementMode=3,secondsParking=0;}config;
struct tm {};
tm *localtime_r(const time_t*,tm *out){return out;}
size_t strftime(char *out,size_t n,const char*,const tm*){
 return snprintf(out,n,"Thu Oct 22 14:20:%02u 2026 +0100",nowMs/1000%60);
}
struct Wifi {
 int status(){return 3;}
 int hostByName(const char *p,IPAddress &ip,unsigned){ip.value=!strcmp(p,"primary")?1:2;return failedDns?0:1;}
}WiFi;
const int WL_CONNECTED=3;
constexpr unsigned REASON_SOFT_RESTART=4;
struct ResetInfo {unsigned reason=REASON_SOFT_RESTART;};
struct Random {
 uint32_t rtc[128]={};bool readFails=false,writeFails=false;ResetInfo reset;
 void random(uint8_t*p,size_t n){++randomCounter;for(size_t i=0;i<n;++i)p[i]=randomCounter+i;}
 bool rtcUserMemoryRead(unsigned offset,uint32_t*p,size_t n){if(readFails)return false;memcpy(p,rtc+offset,n);return true;}
 bool rtcUserMemoryWrite(unsigned offset,uint32_t*p,size_t n){if(writeFails)return false;memcpy(rtc+offset,p,n);return true;}
 ResetInfo *getResetInfoPtr(){return &reset;}
}ESP;
struct FakeUdp {
 unsigned sent[3]={},target=0,source=1,port=123;
 bool ready=false;
 uint8_t requests[3][48]={},reply[48]={};
 void stop(){ready=false;}
 void begin(unsigned){}
 int beginPacket(IPAddress ip,unsigned){target=ip.value;return 1;}
 void write(uint8_t*p,size_t n){memcpy(requests[target],p,n);}
 int endPacket(){++sent[target];return 1;}
 int parsePacket(){return ready?48:0;}
 IPAddress remoteIP(){IPAddress ip;ip.value=source;return ip;}
 unsigned remotePort(){return port;}
 int read(uint8_t*p,size_t n){memcpy(p,reply,n);ready=false;return n;}
 int read(){return 0;}
 int available(){return 0;}
};
typedef FakeUdp WiFiUDP;
unsigned serialEvents[16]={},serialCount=0;
struct SerialStub {
 char last[64]={};unsigned writes=0;bool partial=false;
 size_t write(const uint8_t *p,size_t n){++writes;memcpy(last,p,n);last[n]=0;return partial?n-1:n;}
 void print(const char*p){if(!strcmp(p,"SLEEP\r\n")){++sleeps;serialEvents[serialCount++]=2;}}
 void flush(){if(serialCount<16)serialEvents[serialCount++]=1;}
}Serial;
struct WebStub {String arg(const char*){return config.timezone;}void send(unsigned,const char*,const String&){} }web;
bool apiRequestAllowed(bool,bool){return true;}
enum class NetworkState {WaitingForNtp,Connected};
NetworkState networkState;
bool ntpRequested=false,ntpTimedOut=false,ntpResponseReceived=false,ntpFallbackAttempted=false;
bool timeAnnouncementActive=false,firstTimeAnnouncementPending=false;
bool closeSleepPending=false,sleepMessageSent=false,restartScheduled=false,factoryResetPending=false;
uint32_t closeSleepRequestedAt=0;
unsigned ntpStartedAt=0,lastSyncAt=0,timeRecordsSent=0;
uint32_t lastTimeAnnouncementAt=0;
constexpr uint32_t TIME_ANNOUNCE_INTERVAL_MS=1000;
const unsigned NTP_TIMEOUT_MS=5000;
const bool AUTO_SEND_TIME_TO_MM32=true;
ClockWebSession webSession(2000,10000,60000);
void beginTimeAnnouncement();
#include "esp_ui_backend.h"
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
void resetFixture(){
 timeConfirmation.reset();
 Serial=SerialStub();lastTimeAnnouncementAt=0;
 ESP=Random();saveSleepPending=false;serialCount=0;
 config=Config();
 nowMs=acceptedUtc=announcements=sleeps=randomCounter=failedDns=0;
 ntpRequested=ntpTimedOut=ntpResponseReceived=ntpFallbackAttempted=false;
 timeAnnouncementActive=firstTimeAnnouncementPending=false;
 closeSleepPending=sleepMessageSent=restartScheduled=factoryResetPending=false;
 closeSleepRequestedAt=0;
 ntpStartedAt=lastSyncAt=timeRecordsSent=0;
 ntpUdp=FakeUdp();
 new (&webSession) ClockWebSession(2000,10000,60000);
}
void reply(unsigned server,unsigned bad) {
 // Outage/retry scenarios deliver a fresh 20 ms network response after their
 // simulated wait. Slow-reply rejection has separate precision cases.
 ntpAttempts[server-1].sentMicros=micros()-20000u;
 ntpUdp.ready=true;ntpUdp.source=server;ntpUdp.port=123;
 memset(ntpUdp.reply,0,48);ntpUdp.reply[0]=0x24;ntpUdp.reply[1]=2;
 memcpy(ntpUdp.reply+24,ntpUdp.requests[server]+40,8);
 uint32_t stamp=1792890000u+2208988800u;
 for(unsigned i=0;i<4;++i)ntpUdp.reply[40+i]=(stamp>>(24-8*i))&255;
 if(bad==1)ntpUdp.reply[24]^=1;
 if(bad==2)ntpUdp.reply[1]=0;
 if(bad==3)ntpUdp.source=99;
 if(bad==4)ntpUdp.port=999;
}
extern "C" unsigned ntpScenario(unsigned scenario){
 resetFixture();beginNtpSync();
 if(ntpUdp.sent[1]!=1 || ntpUdp.sent[2]!=0)return 1;
 nowMs=4999;serviceNtp();if(ntpUdp.sent[2])return 2;
 if(scenario==0){reply(1,0);serviceNtp();return acceptedUtc==1792890000u && timeAnnouncementActive && !ntpRequested?0:3;}
 nowMs=5000;serviceNtp();if(ntpUdp.sent[2]!=1)return 4;
 if(scenario>=3 && scenario<=6){
   reply(1,scenario-2);serviceNtp();if(acceptedUtc || timeAnnouncementActive || !ntpRequested)return 5;
 }
 if(scenario==7){
   nowMs=15001;serviceNtp();if(ntpUdp.sent[1]!=2 || ntpUdp.sent[2]!=1)return 6;
 }
 reply(scenario==2?2:1,0);serviceNtp();
 return acceptedUtc==1792890000u && timeAnnouncementActive && !ntpRequested?0:7;
}
static void putNetworkWord(uint8_t *p,uint32_t value){
 for(unsigned i=0;i<4;++i)p[i]=(value>>(24-8*i))&255;
}
extern "C" unsigned ntpPrecisionCase(unsigned scenario){
 resetFixture();beginNtpSync();reply(1,0);
 uint32_t elapsed=20000,seconds=0,usec=0;
 putNetworkWord(ntpUdp.reply+44,0xc0000000u); // .750000, never truncate this.
 if(scenario==1)putNetworkWord(ntpUdp.reply+44,0xffffffffu);
 if(scenario==2)elapsed=300000;
 if(scenario==3){
   memcpy(ntpUdp.reply+32,ntpUdp.reply+40,4);
   putNetworkWord(ntpUdp.reply+36,0xc0000000u-42949673u); // 10 ms server processing.
 }
 if(scenario==4)ntpUdp.reply[24]^=1;
 if(scenario==6)elapsed=250000;
 if(scenario==7){elapsed=0;putNetworkWord(ntpUdp.reply+44,0);}
 if(scenario==8){putNetworkWord(ntpUdp.reply+40,100);putNetworkWord(ntpUdp.reply+44,0);}
 if(scenario==9)memcpy(ntpUdp.reply+32,ntpUdp.reply+40,4);
 int valid=txw_ntp_parse_precise(ntpUdp.reply,scenario==5?47:48,
      ntpAttempts[0].nonce,elapsed,&seconds,&usec);
 if(scenario==2 || scenario==4 || scenario==5 || scenario==9)return valid?1:0;
 if(!valid)return 2;
 uint32_t expected=1792890000u,frac=760000;
 if(scenario==1){++expected;frac=9999;}
 if(scenario==3)frac=755000;
 if(scenario==6)frac=875000;
 if(scenario==7)frac=0;
 if(scenario==8){expected=2085978596u;frac=10000;}
 return seconds!=expected || usec+1<frac || usec>frac+1?3:0;
}
extern "C" unsigned wholeSecondCase(){
 resetFixture();acceptedUtc=1792890000u;timeAnnouncementActive=true;
 firstTimeAnnouncementPending=false;lastTimeAnnouncementAt=0;
 nowMs=1100;serviceTimeAnnouncement();if(Serial.writes)return 1;
 nowMs=2000;serviceTimeAnnouncement();if(Serial.writes!=1)return 2;
 nowMs=2500;serviceTimeAnnouncement();if(Serial.writes!=1)return 3;
 nowMs=3000;serviceTimeAnnouncement();if(Serial.writes!=2)return 4;
 nowMs=3020;serviceTimeAnnouncement();if(Serial.writes!=2)return 5;
 nowMs=4020;serviceTimeAnnouncement();if(Serial.writes!=3)return 6;
 nowMs=5000;serviceTimeAnnouncement();if(Serial.writes!=4)return 7;
 nowMs=6021;serviceTimeAnnouncement();if(Serial.writes!=4)return 8;
 nowMs=7000;serviceTimeAnnouncement();return Serial.writes==5?0:9;
}
extern "C" unsigned prolongedWakeObservation(unsigned scenario){
 resetFixture();failedDns=(scenario==1);beginNtpSync();
 for(unsigned i=1;i<=120;++i){
   nowMs=i*1000;serviceNtp();serviceTimeAnnouncement();serviceCloseSleep();
 }
 // No authenticated time reply: must not invent time or send early SLEEP.
 if(acceptedUtc || Serial.writes || sleeps || !ntpRequested)return 1;
 if(scenario==1 && (ntpUdp.sent[1] || ntpUdp.sent[2]))return 2;
 if(scenario==0 && (!ntpUdp.sent[1] || !ntpUdp.sent[2]))return 3;
 // Network/server recovers: next retry and valid reply should resume output.
 failedDns=0;nowMs+=16000;serviceNtp();reply(1,0);serviceNtp();
 nowMs+=1000;serviceTimeAnnouncement();
 return acceptedUtc && Serial.writes==1 && !ntpRequested?0:4;
}
extern "C" unsigned optionalSecondaryScenario() {
 resetFixture();config.ntpBackupHost="";beginNtpSync();
 nowMs=5000;serviceNtp();
 if(ntpUdp.sent[2] || ntpAttempts[1].pending)return 1;
 nowMs=15001;serviceNtp();
 if(ntpUdp.sent[1]!=2 || ntpUdp.sent[2] || ntpAttempts[1].pending)return 2;
 reply(1,0);serviceNtp();
 return acceptedUtc==1792890000u && !ntpRequested?0:3;
}
extern "C" unsigned sleepScenario(unsigned scenario){
 resetFixture();nowMs=5000;closeSleepPending=true;ntpResponseReceived=true;timeRecordsSent=1;
 const char record[]="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030\r\n";
 timeConfirmation.recordSent(record,strlen(record),nowMs);
 timeConfirmation.acceptEcho("+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030",nowMs);
 if(scenario==1)ntpResponseReceived=false;
 if(scenario==2)timeRecordsSent=0;
 if(scenario==3)restartScheduled=true;
 if(scenario==4)factoryResetPending=true;
 if(scenario==5)webSession.note("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",true,0);
 serviceCloseSleep();serviceCloseSleep();
 return sleeps==(scenario?0u:1u)?0:1;
}

extern "C" unsigned ticketScenario(unsigned scenario){
 resetFixture();const uint32_t fingerprint=0x12345678;
 if(scenario==9){ESP.writeFails=true;return armSaveSleepTicket(fingerprint)?1:0;}
 if(scenario==10){ESP.readFails=true;return armSaveSleepTicket(fingerprint)?1:0;}
 if(!armSaveSleepTicket(fingerprint))return 2;
 if(scenario>=1 && scenario<=4)ESP.rtc[SAVE_SLEEP_RTC_WORD+scenario-1]^=1;
 if(scenario==5)ESP.reset.reason=0; // Cold power-on, even with old bytes.
 if(scenario==6)ESP.reset.reason=6; // External reset, not Save's restart.
 if(scenario==7)ESP.readFails=true;
 if(scenario==8)ESP.writeFails=true; // Cannot consume: must not enable.
 bool taken=takeSaveSleepTicket(fingerprint+(scenario==11),scenario!=12);
 if(taken!=(scenario==0))return 3;
 ESP.readFails=false;ESP.writeFails=false;
 if(scenario!=8 && takeSaveSleepTicket(fingerprint,true))return 4;
 return 0;
}

extern "C" unsigned saveSleepScenario(unsigned scenario){
 resetFixture();const uint32_t fingerprint=0x12345678;
 if(!armSaveSleepTicket(fingerprint))return 1;
 saveSleepPending=takeSaveSleepTicket(fingerprint,true);
 if(!saveSleepPending)return 2;
 // New boot has no retained NTP/TIME proof. Intent alone cannot cut power.
 serviceCloseSleep();if(sleeps)return 3;
 beginNtpSync();serviceCloseSleep();if(sleeps)return 4;
 if(scenario==1)return 0; // Failed/delayed NTP keeps AP and normal timeout.
 reply(1,0);serviceNtp();serviceCloseSleep();if(sleeps)return 5;
 timeRecordsSent=1; // Real producer increments only after a complete write.
 const char record[]="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030\r\n";
 timeConfirmation.recordSent(record,strlen(record),nowMs);
 timeConfirmation.acceptEcho("+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030",nowMs);
 if(scenario==2)webSession.note("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",true,0);
 if(scenario==3)restartScheduled=true;
 if(scenario==4)factoryResetPending=true;
 serviceCloseSleep();serviceCloseSleep();
 if(scenario>=2)return sleeps?6:0;
 if(sleeps!=1 || saveSleepPending || serialCount!=3)return 7;
 return serialEvents[0]==1 && serialEvents[1]==2 && serialEvents[2]==1?0:8;
}

extern "C" unsigned confirmationScenario(unsigned scenario){
 resetFixture();saveSleepPending=true;ntpResponseReceived=true;timeRecordsSent=1;
 const char wire[]="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030\r\n";
 const char echo[]="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030";
 timeConfirmation.recordSent(wire,strlen(wire),nowMs);
 serviceCloseSleep();if(sleeps)return 1; // Transmission alone is insufficient.
 char bad[80];strcpy(bad,echo);
 if(scenario==1)bad[strlen(bad)-1]='1'; // Different saver.
 if(scenario==2)bad[strlen(bad)-2]='0'; // Different movement.
 if(scenario==3)bad[24]='1'; // Different timestamp.
 if(scenario==4)bad[40]='1'; // Different wake schedule.
 if(scenario==5)nowMs=2001; // Too late, despite exact bytes.
 if(scenario==6)timeConfirmation.reset(); // Previous boot/acquisition.
 if(scenario==7)timeConfirmation.transmitFailed(); // Partial transmission.
 bool matched=timeConfirmation.acceptEcho(bad,nowMs);
 serviceCloseSleep();serviceCloseSleep();
 if(scenario && (matched || sleeps))return 2;
 if(!scenario && (!matched || sleeps!=1))return 3;
 return 0;
}

extern "C" unsigned confirmationBounded(unsigned scenario){
 resetFixture();
 const char wire[]="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030\r\n";
 const char echo[]="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030";
 for(unsigned i=0;i<5;++i){
   if(!timeConfirmation.canSend())return 1;
   if(scenario)timeConfirmation.transmitFailed();
   else timeConfirmation.recordSent(wire,strlen(wire),i*1000);
 }
 if(timeConfirmation.canSend())return 2;
 if(!scenario && !timeConfirmation.acceptEcho(echo,4500))return 3;
 timeConfirmation.reset();
 if(!timeConfirmation.canSend() || timeConfirmation.confirmed() ||
    timeConfirmation.acceptEcho(echo,4500))return 4;
 // Unsigned elapsed-time check remains valid across millis() rollover.
 timeConfirmation.recordSent(wire,strlen(wire),0xfffffff0u);
 return timeConfirmation.acceptEcho(echo,16)?0:5;
}

extern "C" unsigned announcementScenario(unsigned scenario){
 resetFixture();saveSleepPending=true;beginNtpSync();reply(1,0);serviceNtp();
 if(scenario==3)Serial.partial=true;
 if(scenario==6)config.movementMode=9; // Formatter failure must be bounded too.
 if(scenario==4)webSession.note("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",true,0);
 char first[64]={};
 for(unsigned i=0;i<12;++i){
   nowMs=i*1000;
   if(scenario==4)webSession.note("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",true,nowMs);
   serviceTimeAnnouncement();
   if(Serial.last[0] && !first[0])strcpy(first,Serial.last);
   if(Serial.last[0] && (scenario==0 || scenario==4)){
     char echo[64];strcpy(echo,Serial.last);echo[strlen(echo)-2]=0;
     timeConfirmation.acceptEcho(echo,nowMs);
   }
   if(scenario==2 && Serial.last[0]){
     char bad[64];strcpy(bad,Serial.last);bad[strlen(bad)-3]='1';bad[strlen(bad)-2]=0;
     if(timeConfirmation.acceptEcho(bad,nowMs))return 1;
   }
   if(scenario==5 && i==2){
     first[strlen(first)-2]=0;
     if(timeConfirmation.acceptEcho(first,nowMs))return 2; // Old attempt rejected.
     char echo[64];strcpy(echo,Serial.last);echo[strlen(echo)-2]=0;
     if(!timeConfirmation.acceptEcho(echo,nowMs))return 3;
   }
   serviceCloseSleep();
   if(sleeps)break; // MM32 removes ESP power after the confirmed SLEEP.
 }
 if(scenario==0)return sleeps==1 && Serial.writes==1?0:4;
 if(scenario==4){
   if(sleeps || Serial.writes!=1)return 5;
   webSession.stop();serviceCloseSleep();return sleeps==1?0:6;
 }
 if(scenario==5)return sleeps==1 && Serial.writes==2?0:7;
 return sleeps==0 && !timeConfirmation.canSend() && Serial.writes==(scenario==6?0u:5u)?0:8;
}

extern "C" const char *bridgeBegin(unsigned style){
 resetFixture();config.movementMode=style;saveSleepPending=true;
 beginNtpSync();reply(1,0);serviceNtp();nowMs=1000;serviceTimeAnnouncement();
 return Serial.last;
}
extern "C" unsigned bridgeEcho(const char *line){
 timeConfirmation.acceptEcho(line,nowMs);serviceCloseSleep();return sleeps;
}

char dstZone[128];
extern "C" const char *dstTransmit(unsigned utc,unsigned style,unsigned park){
 resetFixture();config.timezone=dstZone;config.movementMode=style;config.secondsParking=park;
 acceptedUtc=utc;nowMs=1000;tm localTime{};sendTimeToClock(localTime);
 return Serial.last;
}
extern "C" const char *dstSaveBegin(unsigned utc){
 const char *record=dstTransmit(utc,3,0);
 saveSleepPending=true;ntpResponseReceived=true;
 return record;
}
static void confirmRefreshTime(unsigned now){
 nowMs=now;
 const char *record="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030\r\n";
 timeConfirmation.recordSent(record,strlen(record),nowMs);
 timeConfirmation.acceptEcho("+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030",nowMs);
}
extern "C" unsigned refreshSleepScenario(unsigned scenario){
 resetFixture();ntpResponseReceived=true;timeRecordsSent=1;
 if(scenario==4){saveSleepPending=true;confirmRefreshTime(0);serviceCloseSleep();return sleeps==1?0:1;}
 const unsigned begin=scenario==3?0xfffff82fu:1000u;
 nowMs=begin;webSession.note("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",true,nowMs);
 webSession.close("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
 closeSleepPending=true;closeSleepRequestedAt=nowMs;
 confirmRefreshTime(begin);serviceCloseSleep();if(sleeps)return 2;
 if(scenario==1){
   nowMs=begin+2000;webSession.note("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",true,nowMs);
   serviceCloseSleep();if(sleeps || closeSleepPending)return 3;
   webSession.close("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
   nowMs=begin+6000;serviceCloseSleep();if(sleeps || !webSession.active(nowMs))return 4;
   webSession.close("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
   closeSleepPending=true;closeSleepRequestedAt=nowMs;
   confirmRefreshTime(begin+10999);serviceCloseSleep();if(sleeps)return 5;
   confirmRefreshTime(begin+11000);serviceCloseSleep();return sleeps==1?0:6;
 }
 if(scenario==2){
   timeConfirmation.reset();nowMs=begin+5000;serviceCloseSleep();if(sleeps)return 7;
   confirmRefreshTime(nowMs);ntpResponseReceived=false;serviceCloseSleep();if(sleeps)return 8;
   ntpResponseReceived=true;serviceCloseSleep();return sleeps==1?0:9;
 }
 confirmRefreshTime(begin+4999);serviceCloseSleep();if(sleeps)return 10;
 confirmRefreshTime(begin+5000);serviceCloseSleep();serviceCloseSleep();return sleeps==1?0:11;
}
