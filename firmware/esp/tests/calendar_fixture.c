#include "clock_calendar.h"
#include "clock_ntp_packet.h"
char zone[128];
uint8_t wake[2], packet[64];
struct txw_clock_dst_change change;
struct txw_hc32_time civil;
char upcoming[48];
unsigned upcomingCase(unsigned now) {
    upcoming[0]=0;
    return txw_clock_upcoming_dst_text(now, zone, upcoming, sizeof(upcoming));
}
uint32_t reply_utc;
unsigned wakeCase(unsigned now, unsigned hour, unsigned minute) {
    return txw_clock_next_wake(now, zone, hour, minute, wake, wake+1);
}
unsigned dstCase(unsigned now) {
    return txw_clock_next_dst_change(now, zone, &change);
}
unsigned localCase(unsigned now) {
    return txw_clock_local_from_unix(now, zone, &civil);
}
unsigned packetCase(unsigned length) {
    return txw_ntp_parse_reply(packet, length, UINT64_C(0x0102030405060708), &reply_utc);
}
