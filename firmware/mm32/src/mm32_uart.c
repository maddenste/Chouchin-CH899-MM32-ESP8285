#include "mm32_uart.h"

#define MAX_WIRE_LINE 96u /* New-port limit; stock MM32 buffer is unknown. */

typedef struct
{
    const uint8_t *bytes;
    uint16_t length;
    uint16_t pos;
} Scan;

static bool literal(Scan *scan, const char *text)
{
    uint16_t cursor = scan->pos;
    uint16_t index = 0u;
    while (text[index] != '\0')
    {
        if (cursor >= scan->length || scan->bytes[cursor] != (uint8_t)text[index])
        {
            return false;
        }
        ++cursor;
        ++index;
    }
    scan->pos = cursor;
    return true;
}

static bool digits(Scan *scan, uint8_t count, uint16_t *result)
{
    uint16_t cursor = scan->pos;
    uint16_t value = 0u;
    uint8_t index;
    for (index = 0u; index < count; ++index)
    {
        uint8_t byte;
        if (cursor >= scan->length)
        {
            return false;
        }
        byte = scan->bytes[cursor++];
        if (byte < (uint8_t)'0' || byte > (uint8_t)'9')
        {
            return false;
        }
        value = (uint16_t)(value * 10u + (uint16_t)(byte - (uint8_t)'0'));
    }
    scan->pos = cursor;
    *result = value;
    return true;
}

static bool weekday(Scan *scan)
{
    static const char *const names[7] = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"};
    uint8_t index;
    for (index = 0u; index < 7u; ++index)
    {
        Scan trial = *scan;
        if (literal(&trial, names[index]))
        {
            *scan = trial;
            return true;
        }
    }
    return false;
}

static uint8_t month(Scan *scan)
{
    static const char *const names[12] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
    uint8_t index;
    for (index = 0u; index < 12u; ++index)
    {
        Scan trial = *scan;
        if (literal(&trial, names[index]))
        {
            *scan = trial;
            return (uint8_t)(index + 1u);
        }
    }
    return 0u;
}

static bool valid_date(uint16_t year, uint8_t month_number, uint8_t day)
{
    static const uint8_t lengths[12] = {31u, 28u, 31u, 30u, 31u, 30u, 31u, 31u, 30u, 31u, 30u, 31u};
    uint8_t maximum;
    bool leap;
    if (year == 0u || month_number == 0u || month_number > 12u)
    {
        return false;
    }
    maximum = lengths[month_number - 1u];
    leap = (year % 4u == 0u) && ((year % 100u != 0u) || (year % 400u == 0u));
    if (month_number == 2u && leap)
    {
        maximum = 29u;
    }
    return day >= 1u && day <= maximum;
}

bool mm32_uart_parse_esp_line(const uint8_t *bytes, uint16_t length, Mm32UartEvent *event)
{
    Scan scan;
    Mm32UartEvent result = {0};
    uint16_t value;
    uint16_t offset_hour;
    uint16_t offset_minute;
    bool negative;
    if (bytes == 0 || event == 0 || length < 3u || length > MAX_WIRE_LINE)
    {
        return false;
    }
    scan.bytes = bytes;
    scan.length = length;
    scan.pos = 0u;
    if ((length == 7u && literal(&scan, "SLEEP\r\n")) ||
        (length == 6u && literal(&scan, "SLEEP\n")))
    {
        result.kind = MM32_UART_SLEEP;
        *event = result;
        return true;
    }
    scan.pos = 0u;
    if (literal(&scan, "USER_OK\r\n") && scan.pos == length)
    {
        result.kind = MM32_UART_USER_ACK;
    }
    else
    {
        scan.pos = 0u;
        if (literal(&scan, "CLEAN_OK\r\n") && scan.pos == length)
        {
            result.kind = MM32_UART_CLEAN_ACK;
        }
        else
        {
            scan.pos = 0u;
            if (literal(&scan, "+TICK\r\n") && scan.pos == length)
            {
                result.kind = MM32_UART_TICK;
            }
        }
    }
    if (result.kind != MM32_UART_NONE)
    {
        *event = result;
        return true;
    }
    scan.pos = 0u;
    if (!literal(&scan, "+TIME:") || !weekday(&scan) || !literal(&scan, " "))
    {
        return false;
    }
    result.month = month(&scan);
    if (result.month == 0u || !literal(&scan, " "))
    {
        return false;
    }
    /* strftime's %e emits a leading space for day 1..9. */
    if (scan.pos < scan.length && scan.bytes[scan.pos] == (uint8_t)' ')
    {
        ++scan.pos;
        if (!digits(&scan, 1u, &value))
        {
            return false;
        }
    }
    else if (!digits(&scan, 2u, &value))
    {
        return false;
    }
    result.day = (uint8_t)value;
    if (!literal(&scan, " ") || !digits(&scan, 2u, &value))
    {
        return false;
    }
    result.hour = (uint8_t)value;
    if (!literal(&scan, ":") || !digits(&scan, 2u, &value))
    {
        return false;
    }
    result.minute = (uint8_t)value;
    if (!literal(&scan, ":") || !digits(&scan, 2u, &value))
    {
        return false;
    }
    result.second = (uint8_t)value;
    if (!literal(&scan, " ") || !digits(&scan, 4u, &result.year) || !literal(&scan, " "))
    {
        return false;
    }
    if (scan.pos >= scan.length)
    {
        return false;
    }
    negative = scan.bytes[scan.pos] == (uint8_t)'-';
    if (!negative && scan.bytes[scan.pos] != (uint8_t)'+')
    {
        return false;
    }
    ++scan.pos;
    if (!digits(&scan, 2u, &offset_hour) || !digits(&scan, 2u, &offset_minute) ||
        !literal(&scan, " ") || !digits(&scan, 2u, &value))
    {
        return false;
    }
    result.scheduled_hour = (uint8_t)value;
    if (!literal(&scan, ":") || !digits(&scan, 2u, &value))
    {
        return false;
    }
    result.scheduled_minute = (uint8_t)value;
    /* Both compact 31 and spaced 3 1 are emitted by HC32-compatible ESPs.
     * Legacy records preserve settings; a malformed suffix rejects everything. */
    if (scan.pos < length && bytes[scan.pos] != '\r' &&
        !(scan.pos + 1u < length && bytes[scan.pos] == ' ' && bytes[scan.pos + 1u] == 'D'))
    {
        if (bytes[scan.pos] == ' ')
            ++scan.pos;
        if (!digits(&scan, 1u, &value) || value > 3u)
            return false;
        result.movement_mode = (uint8_t)value;
        if (scan.pos < length && bytes[scan.pos] == ' ')
            ++scan.pos;
        if (!digits(&scan, 1u, &value) || value > 2u)
            return false;
        result.night_parking = (uint8_t)value;
        result.settings_present = 1u;
    }
    if (literal(&scan, " DST"))
        result.dst_pending = 1u;
    if (!literal(&scan, "\r\n") || scan.pos != length)
        return false;
    if (result.year < 2000u || result.year > 2099u ||
        !valid_date(result.year, result.month, result.day) || result.hour > 23u ||
        result.minute > 59u || result.second > 59u || offset_hour > 23u || offset_minute > 59u ||
        result.scheduled_hour > 23u || result.scheduled_minute > 59u)
    {
        return false;
    }
    result.utc_offset_minutes = (int16_t)(offset_hour * 60u + offset_minute);
    if (negative)
    {
        result.utc_offset_minutes = (int16_t)-result.utc_offset_minutes;
    }
    result.kind = MM32_UART_TIME;
    *event = result;
    return true;
}
