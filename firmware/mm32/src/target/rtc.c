/* PCF8563 calendar access on PB8/PB9. Only registers 02..08 are written,
 * at acquisition or an authorized correction after movement has drained.
 * RTC controls, alarms, timer and CLKOUT configuration are preserved. */
#include "movement_api.h"
#define REG32(a) (*(volatile uint32_t *)(a))
#define GPIOB_BSRR REG32(0x48000410u)

#define RTC_CRH REG32(0x48000404u)
#define RTC_IDR REG32(0x48000408u)
#define RTC_SCL (1u << 8)
#define RTC_SDA (1u << 9)
#define RTC_BOTH (RTC_SCL | RTC_SDA)
extern volatile uint32_t pulse_diag[40]; /* RC6S reference state at AE0. */
static uint32_t counter_before_calendar(void);
struct set_log
{
    uint32_t signature, command, status, used, stage, error;
    uint32_t year, month, day, hour, minute, second, weekday;
    int32_t offset_minutes;
    uint32_t write_bytes, verified, crh_before, crh_after;
    /* Registers are bytes; retain all before/after verification. */
    uint8_t before[16], after[16], expected[7];
};
__attribute__((section("RTC_SURVEY"))) volatile struct set_log wifi_rtc;
static volatile uint32_t rtc_active;
volatile uint32_t rtc_recovery[4]; /* attempts, clocks, success, idle levels */
static uint32_t irq_save(void)
{
    uint32_t state;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(state)::"memory");
    return state;
}
static void irq_restore(uint32_t state)
{
    __asm volatile("msr primask, %0" ::"r"(state) : "memory");
}
static void bus_delay(void)
{
    if (REG32(0x40004418u) & 1u)
        uart_probe_poll_once();
    /* Counter-only transfers need to complete well inside its62ms reload.
     * Calendar accesses keep their existing conservative timing. */
    uint32_t loops = pulse_diag[25] ? 4u : 40u;
    for (volatile uint32_t i = 0; i < loops; ++i)
        __asm volatile("nop");
}
static void bus_low(uint32_t p)
{
    GPIOB_BSRR = p << 16;
    bus_delay();
}
static void bus_release(uint32_t p)
{
    GPIOB_BSRR = p;
    bus_delay();
}
static uint32_t bus_clock(void)
{
    bus_release(RTC_SCL);
    for (uint32_t i = 0; i < 200u; ++i)
    {
        if (RTC_IDR & RTC_SCL)
        {
            bus_delay();
            return 1u;
        }
    }
    wifi_rtc.error = 7u;
    return 0u;
}
static void bus_cleanup(void)
{
    pulse_diag[25] = 0u;
    if (rtc_active)
    {
        GPIOB_BSRR = RTC_BOTH;
        uint32_t irq = irq_save();
        RTC_CRH = (RTC_CRH & ~0xffu) | (wifi_rtc.crh_before & 0xffu);
        irq_restore(irq);
        rtc_active = 0u;
        wifi_rtc.crh_after = RTC_CRH;
    }
}
static uint32_t bus_start(void)
{
    bus_release(RTC_SDA);
    if (!bus_clock())
        return 0u;
    if (!(RTC_IDR & RTC_SDA))
    {
        wifi_rtc.error = 3u;
        return 0u;
    }
    bus_low(RTC_SDA);
    bus_low(RTC_SCL);
    return 1u;
}
static uint32_t bus_send(uint32_t b)
{
    for (uint32_t i = 0; i < 8u; ++i)
    {
        if (b & 0x80u)
            bus_release(RTC_SDA);
        else
            bus_low(RTC_SDA);
        if (!bus_clock())
            return 0u;
        bus_low(RTC_SCL);
        b <<= 1;
    }
    bus_release(RTC_SDA);
    if (!bus_clock())
        return 0u;
    uint32_t ack = !(RTC_IDR & RTC_SDA);
    bus_low(RTC_SCL);
    if (!ack)
        wifi_rtc.error = 4u;
    return ack;
}
static uint32_t bus_receive(uint32_t last)
{
    uint32_t b = 0;
    bus_release(RTC_SDA);
    for (uint32_t i = 0; i < 8u; ++i)
    {
        if (!bus_clock())
            return 0u;
        b = (b << 1) | !!(RTC_IDR & RTC_SDA);
        bus_low(RTC_SCL);
    }
    if (last)
        bus_release(RTC_SDA);
    else
        bus_low(RTC_SDA);
    if (!bus_clock())
        return 0u;
    bus_low(RTC_SCL);
    bus_release(RTC_SDA);
    return b;
}
static void bus_stop(void)
{
    if (wifi_rtc.error == 7u)
        return;
    bus_low(RTC_SCL);
    bus_low(RTC_SDA);
    if (bus_clock())
        bus_release(RTC_SDA);
}
static uint32_t read_range(volatile uint8_t *out, uint32_t address, uint32_t count)
{
    uint32_t ok =
        bus_start() && bus_send(0xa2u) && bus_send(address) && bus_start() && bus_send(0xa3u);
    if (ok)
        for (uint32_t i = 0; i < count; ++i)
        {
            out[i] = bus_receive(i == count - 1u);
            if (wifi_rtc.error)
            {
                ok = 0u;
                break;
            }
        }
    bus_stop();
    return ok && !wifi_rtc.error;
}
static uint32_t read_registers(volatile uint8_t *out)
{
    return read_range(out, 0u, 16u);
}
static uint32_t bus_prepare(void)
{
    /* Only the established PB8/PB9 bus, only open-drain drive. Never force
     * SCL high, reset RTC controls, or repeatedly attempt a calendar write. */
    ++rtc_recovery[0];
    GPIOB_BSRR = RTC_BOTH;
    rtc_active = 1u;
    uint32_t irq = irq_save();
    RTC_CRH = (RTC_CRH & ~0xffu) | 0x66u;
    irq_restore(irq);
    for (uint32_t i = 0u; i < 200u; ++i)
    {
        bus_delay();
        if ((RTC_IDR & RTC_BOTH) == RTC_BOTH)
            break;
    }
    if (!(RTC_IDR & RTC_SCL))
    {
        wifi_rtc.error = 7u;
        return 0u;
    }
    /* SDA high can be a transmitted one, not an idle bus. Complete a full
     * nine clocks with SDA released (NACK), then STOP. Never stop at a one
     * mid-byte: the next falling edge may make the slave drive SDA low. */
    {
        for (uint32_t i = 0u; i < 9u; ++i)
        {
            bus_low(RTC_SCL);
            if (!bus_clock())
                return 0u;
            ++rtc_recovery[1];
        }
        /* Finish the interrupted transaction with STOP before normal access. */
        bus_stop();
    }
    rtc_recovery[3] = RTC_IDR & RTC_BOTH;
    if (rtc_recovery[3] != RTC_BOTH)
    {
        wifi_rtc.error = 3u;
        return 0u;
    }
    ++rtc_recovery[2];
    return 1u;
}
static uint32_t leap(uint32_t y)
{
    return (y % 4u) == 0u;
} /* 2000..2099 only */
static uint32_t month_days(uint32_t y, uint32_t m)
{
    static const uint8_t days[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    return days[m - 1u] + (m == 2u && leap(y));
}
static uint32_t days_since_2000(uint32_t y, uint32_t m, uint32_t d)
{
    uint32_t n = d - 1u;
    for (uint32_t i = 2000u; i < y; ++i)
        n += 365u + leap(i);
    for (uint32_t i = 1u; i < m; ++i)
        n += month_days(y, i);
    return n;
}
static uint32_t bcd(uint32_t x)
{
    return ((x / 10u) << 4) | (x % 10u);
}
static uint32_t unbcd(uint32_t x)
{
    return (x >> 4) * 10u + (x & 15u);
}
static uint32_t valid_bcd(uint32_t x)
{
    return (x & 15u) <= 9u && (x >> 4) <= 9u;
}
static uint32_t verify_time(void)
{
    /* Also require every non-calendar register to remain unchanged. */
    for (uint32_t i = 0; i < 16u; ++i)
        if ((i < 2u || i > 8u) && wifi_rtc.before[i] != wifi_rtc.after[i])
            return 0u;
    volatile uint8_t *p = wifi_rtc.after;
    if ((p[2] & 0x80u) || (p[7] & 0x80u))
        return 0u;
    for (uint32_t i = 2u; i <= 8u; ++i)
        if (!valid_bcd(p[i]))
            return 0u;
    uint32_t s = unbcd(p[2]), mi = unbcd(p[3]), h = unbcd(p[4]);
    uint32_t d = unbcd(p[5]), m = unbcd(p[7]), y = 2000u + unbcd(p[8]);
    if (s > 59u || mi > 59u || h > 23u || m < 1u || m > 12u || d < 1u || d > month_days(y, m))
        return 0u;
    uint32_t days = days_since_2000(y, m, d);
    if (p[6] != (days + 6u) % 7u)
        return 0u;
    uint32_t actual = days * 86400u + h * 3600u + mi * 60u + s;
    uint32_t wanted = days_since_2000(wifi_rtc.year, wifi_rtc.month, wifi_rtc.day) * 86400u +
                      wifi_rtc.hour * 3600u + wifi_rtc.minute * 60u + wifi_rtc.second;
    return actual >= wanted && actual - wanted <= 1u;
}
static void set_rtc(void)
{
    wifi_rtc.stage = 2u;
    wifi_rtc.crh_before = RTC_CRH;
    if ((RTC_CRH & 0xffu) != 0x44u)
    {
        wifi_rtc.error = 8u;
        goto done;
    }
    if (!bus_prepare())
        goto done;
    if (!read_registers(wifi_rtc.before))
        goto done;
    /* Refuse stopped/test-mode counters; preserve all control bits. TESTC
     * startup bit3 is not TEST1 and is deliberately left unchanged. */
    if (wifi_rtc.before[0] & 0xa0u)
    {
        wifi_rtc.error = 9u;
        goto done;
    }
    wifi_rtc.stage = 3u;
    if (bus_start() && bus_send(0xa2u) && bus_send(2u))
    {
        for (uint32_t i = 0; i < 7u; ++i)
        {
            if (!bus_send(wifi_rtc.expected[i]))
                break;
            ++wifi_rtc.write_bytes;
        }
    }
    bus_stop();
    if (wifi_rtc.error || wifi_rtc.write_bytes != 7u)
        goto done;
    wifi_rtc.stage = 4u;
    if (!read_registers(wifi_rtc.after))
        goto done;
    wifi_rtc.verified = verify_time();
done:
    bus_cleanup();
    wifi_rtc.status = wifi_rtc.error ? 7u : (wifi_rtc.verified ? 2u : 8u);
}
uint32_t rtc_motion_set(const Mm32UartEvent *e)
{
    /* Stop the experimental timer before the unchanged full-register
     * calendar write/verification. Calendar, alarms and CLKOUT stay intact. */
    if (!counter_before_calendar())
        return 0u;
    pulse_diag[1] = 0u;
    volatile uint32_t *p = (volatile uint32_t *)&wifi_rtc;
    for (uint32_t i = 0; i < sizeof(wifi_rtc) / 4u; ++i)
        p[i] = 0u;
    wifi_rtc.signature = 0x4d503239u;
    if (e->year < 2000u || e->year > 2099u)
        return 0u;
    wifi_rtc.year = e->year;
    wifi_rtc.month = e->month;
    wifi_rtc.day = e->day;
    wifi_rtc.hour = e->hour;
    wifi_rtc.minute = e->minute;
    wifi_rtc.second = e->second;
    wifi_rtc.weekday = (days_since_2000(e->year, e->month, e->day) + 6u) % 7u;
    wifi_rtc.expected[0] = bcd(e->second);
    wifi_rtc.expected[1] = bcd(e->minute);
    wifi_rtc.expected[2] = bcd(e->hour);
    wifi_rtc.expected[3] = bcd(e->day);
    wifi_rtc.expected[4] = wifi_rtc.weekday;
    wifi_rtc.expected[5] = bcd(e->month);
    wifi_rtc.expected[6] = bcd(e->year - 2000u);
    set_rtc();
    return wifi_rtc.status == 2u;
}
void rtc_motion_release(void)
{
    bus_cleanup();
}
uint32_t rtc_event_stamp(const Mm32UartEvent *e)
{
    if (e->year < 2000u || e->year > 2099u)
        return 0u;
    return days_since_2000(e->year, e->month, e->day) * 86400u + e->hour * 3600u + e->minute * 60u +
           e->second;
}
uint32_t rtc_event_advance(Mm32UartEvent *e, uint32_t seconds)
{
    uint32_t time = e->hour * 3600u + e->minute * 60u + e->second + seconds;
    uint32_t days = time / 86400u;
    time %= 86400u;
    /* Waiting for the next seconds reference must take at most 70 seconds. */
    if (days > 1u)
        return 0u;
    while (days--)
    {
        if (++e->day > month_days(e->year, e->month))
        {
            e->day = 1u;
            if (++e->month > 12u)
            {
                e->month = 1u;
                ++e->year;
            }
        }
    }
    if (e->year > 2099u)
        return 0u;
    e->hour = time / 3600u;
    e->minute = (time / 60u) % 60u;
    e->second = time % 60u;
    return 1u;
}
/* DST changes the offset, not the running seconds phase. Select the nearest
 * whole-minute offset with the requested seconds; never truncate :59 to :00
 * in the same minute. Small negative shifts must borrow the calendar too. */
uint32_t rtc_event_align_seconds(Mm32UartEvent *e, uint32_t second)
{
    if (second > 59u)
        return 0u;
    int32_t shift = (int32_t)second - (int32_t)e->second;
    if (shift > 30)
        shift -= 60;
    if (shift < -30)
        shift += 60;
    if (shift >= 0)
        return rtc_event_advance(e, (uint32_t)shift);
    uint32_t back = (uint32_t)-shift;
    if (e->second >= back)
        e->second -= back;
    else
    {
        e->second = 60u + e->second - back;
        if (e->minute)
            --e->minute;
        else
        {
            e->minute = 59u;
            if (e->hour)
                --e->hour;
            else
            {
                e->hour = 23u;
                if (e->day > 1u)
                    --e->day;
                else
                {
                    if (e->month > 1u)
                        --e->month;
                    else
                    {
                        if (e->year <= 2000u)
                            return 0u;
                        --e->year;
                        e->month = 12u;
                    }
                    e->day = month_days(e->year, e->month);
                }
            }
        }
    }
    return 1u;
}
uint32_t rtc_motion_stamp(void)
{
    volatile uint8_t *p = wifi_rtc.after;
    uint32_t y = 2000u + unbcd(p[8]), m = unbcd(p[7] & 0x1fu), d = unbcd(p[5]);
    if ((p[7] & 0x80u) || !valid_bcd(p[8]) || !valid_bcd(p[7] & 0x1fu) || !valid_bcd(p[5]) ||
        m < 1u || m > 12u || d < 1u || d > month_days(y, m))
        return 0xffffffffu;
    return days_since_2000(y, m, d) * 86400u + unbcd(p[4]) * 3600u + unbcd(p[3]) * 60u +
           unbcd(p[2]);
}
uint32_t rtc_motion_read(uint32_t *h, uint32_t *m, uint32_t *s)
{
    wifi_rtc.error = 0u;
    wifi_rtc.crh_before = RTC_CRH;
    if ((RTC_CRH & 0xffu) != 0x44u || (RTC_IDR & RTC_BOTH) != RTC_BOTH)
    {
        wifi_rtc.error = (RTC_CRH & 0xffu) != 0x44u ? 8u : 3u;
        return 0u;
    }
    GPIOB_BSRR = RTC_BOTH;
    rtc_active = 1u;
    uint32_t irq = irq_save();
    RTC_CRH = (RTC_CRH & ~0xffu) | 0x66u;
    irq_restore(irq);
    /* Keep the runtime calendar transaction inside the countdown's polling
     * budget. Setting/verifying calendar time retains its old timing. */
    pulse_diag[25] = pulse_diag[1] == 1u;
    /* Controls are separate from the single coherent calendar access.
     * NXP section 8.5: pointer 02, repeated START, seven bytes, NACK/STOP.
     * No alarm/timer/CLKOUT registers are read during runtime pacing. */
    uint32_t ok = read_range(wifi_rtc.after, 0u, 2u);
    if (ok && !(wifi_rtc.after[0] & 0xa0u))
        ok = read_range(wifi_rtc.after + 2, 2u, 7u);
    bus_cleanup();
    volatile uint8_t *p = wifi_rtc.after;
    if (!ok)
        return 0u;
    if (p[0] & 0xa0u)
    {
        wifi_rtc.error = 9u;
        return 0u;
    }
    if (p[2] & 0x80u)
    {
        wifi_rtc.error = 10u;
        return 0u;
    }
    if (!valid_bcd(p[2]) || !valid_bcd(p[3]) || !valid_bcd(p[4]))
    {
        wifi_rtc.error = 11u;
        return 0u;
    }
    *s = unbcd(p[2]);
    *m = unbcd(p[3]);
    *h = unbcd(p[4]);
    if (*s < 60u && *m < 60u && *h < 24u)
        return 1u;
    wifi_rtc.error = 12u;
    return 0u;
}
uint32_t rtc_motion_error(void)
{
    return wifi_rtc.error;
}

#include "rtc_counter.h"
