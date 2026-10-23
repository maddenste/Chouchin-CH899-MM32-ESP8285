// Actual extracted HTTP host/origin/token/session functions, fake HTTP adapter.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <new>
#include "clock_session.h"
class String {
 char text[256];
public:
 String(const char *s=""){snprintf(text,sizeof(text),"%s",s);}
 const char *c_str()const{return text;}
 bool isEmpty()const{return !text[0];}
 size_t length()const{return strlen(text);}
 bool operator==(const String&b)const{return !strcmp(text,b.text);}
 bool operator!=(const String&b)const{return !(*this==b);}
 void toLowerCase(){for(unsigned i=0;text[i];++i)if(text[i]>='A'&&text[i]<='Z')text[i]+='a'-'A';}
 bool endsWith(const char *s)const{size_t n=strlen(s);return n<=length() && !strcmp(text+length()-n,s);}
 bool startsWith(const char *s)const{return !strncmp(text,s,strlen(s));}
 void remove(size_t n){if(n<sizeof(text))text[n]=0;}
 String substring(size_t n)const{return text+(n<length()?n:length());}
};
unsigned nowMs=0;uint32_t millis(){return nowMs;}
const int HTTP_GET=0,HTTP_POST=1,WL_CONNECTED=3;
constexpr char AP_NAME[]="WiFi-Clock-Setup";
struct Ip {const char *s;String toString()const{return s;}};
struct Wifi {
 int link=3;int status(){return link;}
 Ip softAPIP(){return {"192.168.4.1"};}Ip localIP(){return {"192.168.0.111"};}
 void macAddress(uint8_t *p){uint8_t m[]={0x02,0x00,0x00,0xab,0xcd,0xef};memcpy(p,m,6);}
}WiFi;
struct Web {
 const char *host="192.168.0.111",*origin="http://192.168.0.111",*token="0123456789abcdef0123456789abcdef";
 const char *bodyToken="",*page="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",*start="1";
 unsigned code=0,headers=0;int verb=HTTP_POST;
 String hostHeader(){return host;}
 String header(const char *s){return !strcmp(s,"Origin")?origin:token;}
 String arg(const char *s){return !strcmp(s,"page")?page:!strcmp(s,"start")?start:bodyToken;}
 int method(){return verb;}
 void sendHeader(const char*,const char*){++headers;}
 void send(unsigned c,const char*,const char*){code=c;}
}web;
String requestToken("0123456789abcdef0123456789abcdef");
bool portalActive=true,closeSleepPending=false;
uint32_t closeSleepRequestedAt=0;
enum class NetworkState {Offline,Portal,Connecting,Connected,WaitingForNtp};
NetworkState networkState=NetworkState::Connected;
ClockWebSession webSession(2000,10000,60000);
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

void resetFixture(){
 web=Web();WiFi=Wifi();nowMs=0;portalActive=true;closeSleepPending=false;
 closeSleepRequestedAt=0;
 networkState=NetworkState::Connected;
 requestToken="0123456789abcdef0123456789abcdef";
 new (&webSession)ClockWebSession(2000,10000,60000);
}
extern "C" unsigned apiCase(unsigned scenario){
 resetFixture();unsigned expected=0;bool allowBody=false;
 if(scenario==1){web.host="WIFI-CLOCK-ABCDEF:80";web.origin="http://wifi-clock-abcdef";}
 if(scenario==2){web.host="192.168.4.1";web.origin="http://192.168.4.1";WiFi.link=0;}
 if(scenario==3){web.host="attacker.example";web.origin="http://attacker.example";expected=403;}
 if(scenario==4){web.origin="http://attacker.example";expected=403;}
 if(scenario==5){web.origin="https://192.168.0.111";expected=403;}
 if(scenario==6){web.token="wrong";expected=403;}
 if(scenario==7){web.token="";web.bodyToken="0123456789abcdef0123456789abcdef";allowBody=true;}
 if(scenario==8){web.token="";web.bodyToken="0123456789abcdef0123456789abcdef";web.verb=HTTP_GET;allowBody=true;expected=403;}
 if(scenario==9){requestToken="";web.token="";expected=403;}
 if(scenario==10){web.origin="";}
 if(scenario==11){web.origin="null";expected=403;}
 if(scenario<=11){bool ok=apiRequestAllowed(true,allowBody);return ok==(expected==0) && web.code==expected && web.headers==4?0:1;}
 if(scenario==12){keepWebSessionAlive();return web.code==204 && webSession.active(0)?0:2;}
 if(scenario==13){
  keepWebSessionAlive();web.page="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";keepWebSessionAlive();
  web.page="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";closeWebSession();
  return webSession.active(0) && !closeSleepPending?0:3;
 }
 if(scenario==14){closeWebSession();keepWebSessionAlive();return !webSession.active(0) && closeSleepPending?0:4;}
 if(scenario==15){web.page="short";keepWebSessionAlive();return web.code==400 && !webSession.active(0)?0:5;}
 if(scenario==16){
  keepWebSessionAlive();web.start="0";nowMs=60000;keepWebSessionAlive();
  return !webSession.active(nowMs)?0:6;
 }
 if(scenario==17){
  networkState=NetworkState::Offline;keepWebSessionAlive();return web.code==503?0:7;
 }
 return deviceHostname()=="WiFi-Clock-ABCDEF" && deviceSetupName()=="WiFi-Clock-Setup"?0:8;
}
extern "C" unsigned refreshCloseCase(){
 resetFixture();keepWebSessionAlive();nowMs=1000;closeWebSession();
 if(!closeSleepPending || closeSleepRequestedAt!=1000)return 1;
 nowMs=2000;closeWebSession();if(closeSleepRequestedAt!=1000)return 2;
 web.page="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";keepWebSessionAlive();
 if(!webSession.active(nowMs))return 3;
 web.page="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";nowMs=3000;closeWebSession();
 return webSession.active(nowMs) && closeSleepRequestedAt==1000?0:4;
}
