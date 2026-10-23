// Real extracted UART/reset code, with RAM-backed flash and serial adapters.
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <new>
#include "clean_reset_gate.h"
#include "clock_session.h"
#include "time_confirmation.h"
TimeConfirmation timeConfirmation;
#define F(s) s
unsigned nowMs=0,acks=0,userAcks=0,restarts=0,clears=0;
uint32_t millis(){return nowMs;}
struct String {String(const char *s=""){(void)s;}};
struct Eeprom {
 uint8_t bytes[512];bool succeeds=true;unsigned commits=0;
 uint8_t read(unsigned i){return bytes[i];}
 void write(unsigned i,uint8_t b){bytes[i]=b;}
 bool commit(){++commits;return succeeds;}
}EEPROM;
struct SerialPort {
 uint8_t input[1024];unsigned size=0,at=0,flushed=0;
 int available(){return size-at;}
 int read(){return input[at++];}
 void print(const char *s){if(!strcmp(s,"CLEAN_OK\r\n"))++acks;if(!strcmp(s,"USER_OK\r\n"))++userAcks;}
 void flush(){++flushed;}
}Serial;
struct Wifi {void persistent(bool){}void disconnect(bool,bool){++clears;}}WiFi;
struct Esp {void restart(){++restarts;}}ESP;
struct ClockConfig {unsigned dummy=0;}config;
constexpr size_t EEPROM_BYTES=512,UART_LINE_CAPACITY=96;
constexpr uint32_t CLEAN_CONFIRM_MIN_MS=1000,CLEAN_CONFIRM_MAX_MS=4000;
constexpr uint32_t FACTORY_WIFI_CLEAR_DELAY_MS=50,RESTART_DELAY_MS=250;
bool configurationUsable=false,factoryResetPending=false,settingsEraseUncommitted=false;
bool saveSleepPending=false,sdkCredentialsCleared=false,restartScheduled=false;
bool cleanResetArmed=false,timeAnnouncementActive=false,firstTimeAnnouncementPending=false;
bool ntpRequested=false,ntpResponseReceived=false,scanRequested=false,scanReady=false,scanFailed=false;
bool uartLineDiscarding=false;
uint32_t cleanResetArmedAt=0,restartScheduledAt=0;
char uartLine[UART_LINE_CAPACITY]={};size_t uartLineLength=0;
String scanResultJson;
ClockWebSession webSession(2000,10000,60000);
bool clearSaveSleepTicket(){saveSleepPending=false;return true;}
void stopNtpTransport(){}
void scheduleRestart();
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

void resetFixture(){
 timeConfirmation.reset();
 memset(EEPROM.bytes,255,512);EEPROM.commits=0;EEPROM.succeeds=true;
 Serial=SerialPort();nowMs=acks=userAcks=restarts=clears=0;
 configurationUsable=factoryResetPending=settingsEraseUncommitted=false;
 saveSleepPending=sdkCredentialsCleared=restartScheduled=cleanResetArmed=false;
 uartLineLength=0;uartLineDiscarding=false;
 cleanResetArmedAt=restartScheduledAt=0;
}
void feed(const uint8_t *data,unsigned n){
 memcpy(Serial.input,data,n);Serial.size=n;Serial.at=0;serviceMm32Uart();
}
void feed(const char *s){feed((const uint8_t*)s,strlen(s));}
extern "C" unsigned uartCase(unsigned scenario){
 resetFixture();
 if(scenario!=0)EEPROM.bytes[20]=42;
 configurationUsable=scenario==2;
 if(scenario==0){feed("CLEAN\r\n");return acks==1 && !EEPROM.commits && !restartScheduled?0:1;}
 if(scenario==3 || scenario==4){
  const uint8_t bad[]={ 'C','L','E','A','N',0,'X','\n' };
  if(scenario==3){feed(bad,sizeof(bad));nowMs=2000;feed(bad,sizeof(bad));}
  else {uint8_t longLine[120];memset(longLine,'X',113);memcpy(longLine+113,"CLEAN\n",6);feed(longLine,119);nowMs=2000;feed(longLine,119);}
  if(acks || EEPROM.commits || restartScheduled)return 2;
  feed("USER\n");return userAcks==1?0:3;
 }
 if(scenario==5){feed("NOT_A_COMMAND\n");feed("USER\r\n");return userAcks==1 && !EEPROM.commits?0:4;}
 feed("CLEAN\r\n");if(acks || EEPROM.commits || !cleanResetArmed)return 5;
 if(scenario==6){nowMs=999;feed("CLEAN\n");return !acks && !EEPROM.commits && cleanResetArmed?0:6;}
 if(scenario==7){nowMs=4001;feed("CLEAN\n");if(acks || EEPROM.commits || cleanResetArmedAt!=4001)return 7;nowMs=6001;}
 else nowMs=2000;
 if(scenario==8)EEPROM.succeeds=false;
 feed("CLEAN\r\n");
 if(scenario==8){
  if(acks || restartScheduled || !settingsEraseUncommitted || !hasSavedConfig())return 8;
  nowMs=4000;feed("CLEAN\n");if(acks)return 9;
  nowMs=6000;EEPROM.succeeds=true;feed("CLEAN\n");
 }
 if(acks!=1 || !factoryResetPending || !restartScheduled || configurationUsable || hasSavedConfig())return 10;
 unsigned commits=EEPROM.commits;
 feed("CLEAN\n");if(acks!=2 || EEPROM.commits!=commits)return 11;
 nowMs=restartScheduledAt+49;serviceRestart();if(clears || restarts)return 12;
 nowMs=restartScheduledAt+50;serviceRestart();if(clears!=1 || restarts)return 13;
 nowMs=restartScheduledAt+250;serviceRestart();return restarts==1 && clears==1?0:14;
}

extern "C" unsigned echoUartCase(unsigned scenario){
 resetFixture();
 const char wire[]="+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030\r\n";
 timeConfirmation.recordSent(wire,strlen(wire),nowMs);
 if(scenario==1){feed("\n+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0031\r\n");}
 else if(scenario==2){feed("\n+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030X\r\n");}
 else if(scenario==3){nowMs=2001;feed(wire);}
 else if(scenario==4){feed("\n+TIME:Thu Oct 22 14:20:30 2026 +0100 10:0030");return timeConfirmation.confirmed()?2:0;}
 else if(scenario==5){
   uint8_t noise[140];memset(noise,'X',139);noise[139]='\n';feed(noise,140);
   feed("\n");feed(wire);
 } else {feed("\n");feed(wire);}
 if(timeConfirmation.confirmed()!=(scenario==0 || scenario==5))return 1;
 feed("USER\r\n");return userAcks==1?0:3;
}
