#ifndef MM32_UART_H
#define MM32_UART_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    MM32_UART_NONE = 0,
    MM32_UART_USER_ACK,
    MM32_UART_CLEAN_ACK,
    MM32_UART_TICK,
    MM32_UART_TIME,
    MM32_UART_SLEEP
} Mm32UartKind;

typedef struct
{
    uint16_t year;
    int16_t utc_offset_minutes;
    uint8_t month;
    uint8_t day;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;
    uint8_t scheduled_hour;
    uint8_t scheduled_minute;
    Mm32UartKind kind;
    uint8_t settings_present;
    uint8_t movement_mode;
    uint8_t night_parking;
    uint8_t dst_pending; /* Optional DST suffix; fits existing tail padding. */
} Mm32UartEvent;

/* Full CRLF-terminated ESP wire record, not passive-monitor display text.
   Returns false on damage, unknown commands, or overflow. Accepts the optional
   movement/seconds-parking suffix; legacy records leave existing settings intact.
   On failure, the caller's event remains unchanged. No hardware access. */
bool mm32_uart_parse_esp_line(const uint8_t *bytes, uint16_t length, Mm32UartEvent *event);

#endif
