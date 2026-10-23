
#include <stdint.h>
#include <new>
#include "clock_session.h"
#include "time_confirmation.h"
enum class NetworkState {Connecting,Connected,WaitingForNtp,Portal,Offline};
NetworkState networkState;
uint32_t now,connectStartedAt,lastSyncAt,networkRetryStartedAt,timeRecordsSent;
const uint32_t WIFI_CONNECT_TIMEOUT_MS=10000,WIFI_RETRY_INTERVAL_MS=15000,DAILY_SYNC_MS=86400000;
bool restartScheduled,factoryResetPending,sleepMessageSent,scanRunning,scanRequested;
bool timeAnnouncementActive,firstTimeAnnouncementPending,ntpRequested,ntpResponseReceived;
ClockWebSession webSession(2000,10000,60000);
TimeConfirmation timeConfirmation;
unsigned transportStops;
void stopNtpTransport(){++transportStops;}
const int WL_CONNECTED=3;
int link,portals,disconnects,ntps,mdns;
bool portalActive,configurationUsable;
const int WIFI_AP_STA=3;
int wifiMode,begins;
struct String {const char *s; const char *c_str()const{return s;} bool isEmpty()const{return !s || !*s;}};
struct Config {String ssid,password;} config;
String deviceSetupName(){return {"Clock-Setup"};}
uint32_t millis(){return now;}
struct Wifi {int status(){return link;} void disconnect(bool,bool=false){++disconnects;}
 void mode(int value){wifiMode=value;} void softAP(const char*){++portals;}
 int softAPIP(){return 1;} void begin(const char*,const char*){++begins;}} WiFi;
struct Dns {void start(int,const char*,int){}} captiveDns;
void startMdns(){++mdns;}
void beginNtpSync(){++ntps;networkState=NetworkState::WaitingForNtp;}
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
extern "C" unsigned retryCase(unsigned scenario) {
 now=connectStartedAt=lastSyncAt=networkRetryStartedAt=0;
 portals=disconnects=ntps=begins=transportStops=0;
 portalActive=false;configurationUsable=true;config.ssid={"saved"};config.password={"secret"};
 restartScheduled=factoryResetPending=sleepMessageSent=scanRunning=scanRequested=false;
 timeAnnouncementActive=firstTimeAnnouncementPending=ntpRequested=ntpResponseReceived=true;
 timeRecordsSent=9;timeConfirmation.reset();new (&webSession) ClockWebSession(2000,10000,60000);
 link=0;beginNetworkWake();
 now=10000;serviceNetwork();
 if(networkState!=NetworkState::Portal || begins!=1 || portals!=1 ||
    timeAnnouncementActive || ntpRequested || ntpResponseReceived || timeRecordsSent || transportStops!=1)return 1;
 if(scenario==0){ // Arbitrarily many attempts, not a finite retry budget.
   for(unsigned i=0;i<1000;++i){
     now+=14999;serviceNetwork();if(networkState!=NetworkState::Portal)return 2;
     ++now;serviceNetwork();if(networkState!=NetworkState::Connecting)return 3;
     now+=10000;serviceNetwork();if(networkState!=NetworkState::Portal)return 4;
   }
   return begins==1001 && portals==1?0:5;
 }
 if(scenario==1){ // Late spontaneous SDK connection gets fresh NTP once.
   link=WL_CONNECTED;now=10001;serviceNetwork();serviceNetwork();
   return ntps==1 && networkState==NetworkState::WaitingForNtp?0:6;
 }
 if(scenario==2){ // Loss after synchronisation must invalidate old proof.
   link=WL_CONNECTED;now=10001;serviceNetwork();networkState=NetworkState::Connected;
   timeAnnouncementActive=ntpResponseReceived=true;timeRecordsSent=9;
   link=0;now=11000;serviceNetwork();
   if(timeAnnouncementActive || ntpResponseReceived || timeRecordsSent)return 7;
   link=WL_CONNECTED;serviceNetwork();return ntps==2?0:8;
 }
 if(scenario>=3 && scenario<=5){
   restartScheduled=scenario==3;factoryResetPending=scenario==4;sleepMessageSent=scenario==5;
   now=25000;serviceNetwork();return begins==1?0:9;
 }
 if(scenario==6 || scenario==7){
   scanRunning=scenario==6;scanRequested=scenario==7;now=25000;serviceNetwork();
   if(begins!=1)return 10;
   scanRunning=scanRequested=false;serviceNetwork();return begins==2?0:11;
 }
 if(scenario==8){
   now=25000;webSession.note("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",true,now);serviceNetwork();
   if(begins!=1)return 12;
   webSession.stop();serviceNetwork();return begins==2?0:13;
 }
 if(scenario==9 || scenario==10){
   configurationUsable=scenario==10;config.ssid={scenario==10?"":"saved"};
   now=25000;serviceNetwork();return begins==1 && portals==1?0:14;
 }
 if(scenario==11){
   networkRetryStartedAt=0xfffffff0u;now=0x00003a87u;serviceNetwork();
   if(begins!=1)return 15;
   ++now;serviceNetwork();return begins==2?0:16;
 }
 if(scenario==12){
   networkState=NetworkState::Offline;now=25000;serviceNetwork();return begins==1?0:17;
 }
 return 18;
}
// Diagnostic reproduction: late association and transient loss during NTP.
// Return state plus counters; no production changes.
extern "C" unsigned recoveryObservation(unsigned scenario) {
 now=connectStartedAt=lastSyncAt=0;portals=disconnects=ntps=mdns=0;
 portalActive=false;configurationUsable=true;config.ssid={"saved"};config.password={"secret"};
 begins=0;link=0;beginNetworkWake();
 if(scenario==0) {
   now=10001;serviceNetwork(); // Association exceeds ten seconds.
   link=WL_CONNECTED;now=12000;serviceNetwork(); // Link becomes available late.
 } else {
   link=WL_CONNECTED;now=1000;serviceNetwork(); // Begin NTP.
   link=0;now=2000;serviceNetwork(); // Brief disconnect.
   link=WL_CONNECTED;now=3000;serviceNetwork();
 }
 for(unsigned i=0;i<120;++i){now+=1000;serviceNetwork();}
 return static_cast<unsigned>(networkState) | (ntps<<8) | (begins<<16);
}
extern "C" unsigned networkCase(unsigned scenario,unsigned elapsed){
 now=elapsed;connectStartedAt=lastSyncAt=0;portals=disconnects=ntps=mdns=0;
 configurationUsable=false;
 restartScheduled=factoryResetPending=sleepMessageSent=scanRunning=scanRequested=false;
 portalActive=false;
 link=(scenario==1 || scenario==4)?3:0;
 networkState=scenario<2?NetworkState::Connecting:
              scenario==2?NetworkState::Connected:
              scenario==3?NetworkState::WaitingForNtp:
              scenario==4?NetworkState::Connected:NetworkState::Portal;
 serviceNetwork();
 return portals | (disconnects<<4) | (ntps<<8) | (mdns<<12);
}
extern "C" unsigned wakeCase(unsigned configured,unsigned connection){
 now=0;portalActive=false;configurationUsable=configured;portals=begins=0;
 config.ssid={configured==2?"":"Home"};config.password={""};
 beginNetworkWake();link=connection?3:0;
 serviceNetwork();
 now=10001;serviceNetwork();
 return portals | (begins<<4) | (portalActive?256:0) | (wifiMode<<12);
}
