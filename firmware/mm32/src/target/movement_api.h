#ifndef MM32_MOVEMENT_API_H
#define MM32_MOVEMENT_API_H

#include "../mm32_uart.h"

/* Public interfaces shared by the controller, reference acquisition, LEDs,
 * RTC and UART transport. Private scheduler helpers stay controller-local. */
extern volatile uint32_t parallel_log[32];
extern volatile uint32_t minute_log[256];
extern volatile uint32_t seconds_log[256];
extern volatile uint32_t daily_log[16];
extern volatile uint32_t ap_recovery[10];

/* Named allocations in the stable minute_log layout. Word 186 was the
 * unused legacy fine_late counter; it must NOT alias audit status word 160. */
enum {
    MM32_AUDIT_FIRST = 160u,
    MM32_AUDIT_WORDS = 20u,
    MM32_CORRECTION_URGENT = 186u
};
_Static_assert(MM32_CORRECTION_URGENT < MM32_AUDIT_FIRST ||
               MM32_CORRECTION_URGENT >= MM32_AUDIT_FIRST + MM32_AUDIT_WORDS,
               "correction state overlaps alignment audit");

void parallel_minute_sample(uint32_t high, uint32_t request);
void parallel_minute_request_done(void);
uint32_t parallel_seconds_pulse_done(uint32_t highs);
void parallel_seconds_runtime_begin(void);
uint32_t parallel_seconds_runtime_done(uint32_t highs);

void parallel_leds_init(void);
void parallel_leds_off(void);
void parallel_leds_tick(uint32_t tick);
void parallel_leds_fault_start(uint32_t tick);
void parallel_leds_daily_start(void);
void parallel_leds_daily_received(uint32_t tick);
void parallel_leds_rec_start(uint32_t tick);
void parallel_leds_power_down(uint32_t tick, uint32_t success);

uint32_t rtc_motion_error(void);
uint32_t rtc_motion_set(const Mm32UartEvent *event);
uint32_t rtc_motion_read(uint32_t *hour, uint32_t *minute, uint32_t *second);
void rtc_motion_release(void);
uint32_t rtc_counter_start(void);
uint32_t rtc_counter_read(uint32_t *value);
uint32_t rtc_counter_pause(void);
uint32_t rtc_motion_stamp(void);
uint32_t rtc_event_stamp(const Mm32UartEvent *event);
uint32_t rtc_event_advance(Mm32UartEvent *event, uint32_t seconds);

void parallel_uart_settings(const Mm32UartEvent *event);
void uart_probe_rx_reset(void);
void uart_probe_consume(uint8_t byte);
void uart_probe_poll_once(void);
void UART2_Handler(void);

#endif
