#ifndef MM32_UART_TRANSPORT_IMPLEMENTATION_H
#define MM32_UART_TRANSPORT_IMPLEMENTATION_H

#include "movement_api.h"

/* Controller-private implementation: included once by parallel_home_main.c.
 * Buffered UART2 transport and factory-compatible protocol parser. */
#define REG32(address) (*(volatile uint32_t *)(address))
#define RCC_AHBENR REG32(0x40021014u)
#define GPIOB_CRL REG32(0x48000400u)
#define GPIOB_AFRL REG32(0x48000420u)
#define GPIOB_BSRR REG32(0x48000410u)
#define GPIOB_BRR REG32(0x48000414u)
#define esp_sleep_requested minute_log[157]
/* Latest deferred TIME, packed into four previously unused words. Settings
 * are applied separately at receipt. No static RAM or event ABI expansion. */
#define pending_time_date minute_log[153]
#define pending_time_clock minute_log[154]
#define pending_time_meta minute_log[155]
#define pending_time_tick minute_log[156]
#define PENDING_TIME_VALID 0x80000000u
/* Whole-second origin of the published and immutable in-flight TIME.
 * Separate from the newest deferred mailbox; no protocol fields added. */
static uint32_t published_time_tick, correction_time_tick;
static volatile uint32_t rx_time_end_tick;
static void legacy_esp_wake(void)
{
    RCC_AHBENR |= 1u << 18;
    GPIOB_BSRR = 1u << 4; /* preload high before output mode */
    GPIOB_AFRL &= ~(15u << 16);
    GPIOB_CRL = (GPIOB_CRL & ~(15u << 16)) | (2u << 16);
}
#define UART1_RDR REG32(UART_BASE + 0x04u)
#define UART1_CSR REG32(UART_BASE + 0x08u)
#define UART1_ISR REG32(UART_BASE + 0x0Cu)
#define UART1_ICR REG32(UART_BASE + 0x14u)
#define UART1_GCR REG32(UART_BASE + 0x18u)
#define UART1_CCR REG32(UART_BASE + 0x1Cu)
#define UART1_BRR REG32(UART_BASE + 0x20u)
#define UART1_FRA REG32(UART_BASE + 0x24u)

#define LINE_CAPACITY 96u

volatile uint32_t uart_probe_bytes;
volatile uint32_t uart_probe_lines;
volatile uint32_t uart_probe_good_time;
volatile uint32_t uart_probe_good_tick;
volatile uint32_t uart_probe_rejected;
volatile uint32_t uart_probe_overflow;
volatile uint32_t uart_probe_uart_errors;

static uint8_t line[LINE_CAPACITY];
static uint16_t line_length;
static uint8_t line_overflowed;
/* Main-context echo borrows line[] until transmission ends. Interrupts stay
 * enabled; the bounded TX routine returns before another line is consumed. */
static volatile uint32_t uart_echo_active;
static void uart_time_echo(void);
Mm32UartEvent uart_probe_time_event;
static volatile uint8_t rx_ring[32];
static volatile uint32_t rx_head, rx_tail, rx_fault;
/* Reserved, previously unused words: no additional static RAM or ABI shift.
 * Error counters count observations, not necessarily distinct lost bytes. */
#define uart_frame_errors minute_log[140]
#define uart_overrun_errors minute_log[141]
#define uart_parity_errors minute_log[142]
#define uart_last_error_flags minute_log[143]
#define uart_last_activity_tick minute_log[144]
#define uart_bad_events minute_log[145]
#define uart_recoveries minute_log[146]
#define uart_last_recovery_tick minute_log[147]
#define uart_power_wake_tick minute_log[148]
#define uart_startup_error_observations minute_log[149]
void uart_probe_rx_reset(void)
{
    rx_head = rx_tail = rx_fault = 0u;
    line_length = 0u;
    line_overflowed = 0u;
}
/* Caller masks IRQs. This resets only the UART and software RX assembly;
 * never ESP power, RCC clocks, motor timers or the RTC. */
static __attribute__((noinline)) void uart_link_configure(void)
{
    REG32(UART_BASE + 0x10u) = 0u;
    UART1_GCR = 0u;
    UART1_CCR = 0x30u; /* Eight bits, no parity, one stop bit. */
    UART1_BRR = 13u;
    /* 212 cycles/bit: live ESP RX sweep rejected 208/209 but passed
     * 210..212 and 214 on the test board. Keep margin on the slower side.
     * ESP remains 38400 8N1; this is not a change to any motor clock. */
    UART1_FRA = 4u;
    REG32(UART_BASE + 0x30u) = 0u; /* Full duplex, no smart-card mode. */
    uart_probe_rx_reset();
    UART1_ICR = 0x7au; /* RX, overrun, parity, framing and break flags. */
    REG32(0xe000e280u) = 1u << 28;
    REG32(0xe000e100u) = 1u << 28;
    uart_bad_events = 0u;
    uart_last_activity_tick = parallel_log[4];
    REG32(UART_BASE + 0x10u) = 0x3au;
    UART1_GCR = 0x19u;
}

static __attribute__((noinline)) void uart_recovery_poll(void)
{
    if (uart_bad_events < 8u || !minute_log[211] || uart_echo_active ||
        minute_log[190] || minute_log[229] || minute_log[230] ||
        parallel_log[2] == 6u || parallel_log[2] == 14u)
        return;
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    uint32_t tick = parallel_log[4];
    /* Require ~31ms without UART activity, TX completely idle, RX empty and
     * the physical RX line high. Recheck while masked to close IRQ races.
     * Rate-limit recovery to once per second, even under persistent noise. */
    if (!mask && minute_log[211] && !minute_log[190] &&
        !minute_log[229] && !minute_log[230] && !uart_echo_active &&
        parallel_log[2] != 6u && parallel_log[2] != 14u &&
        (UART1_GCR & 1u) && uart_bad_events >= 8u &&
        tick - uart_last_activity_tick >= 4u &&
        tick - uart_last_recovery_tick >= 128u &&
        (UART1_CSR & 3u) == 1u && (REG32(0x48000008u) & (1u << 3)))
    {
        uart_link_configure();
        uart_last_recovery_tick = tick;
        ++uart_recoveries;
    }
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
}
/* Vendor SVD: UART2 IRQ28, RX interrupt bit1, errors bits3..5. */
void UART2_Handler(void)
{
    SLEEP_IRQ_NOTE();
    uint32_t errors = UART1_ISR & 0x38u;
    if (errors)
    {
        ++uart_probe_uart_errors;
        if (errors & 0x20u) ++uart_frame_errors;
        if (errors & 0x08u) ++uart_overrun_errors;
        if (errors & 0x10u) ++uart_parity_errors;
        uart_last_error_flags = errors;
        uart_last_activity_tick = parallel_log[4];
        /* ROM startup chatter has a different baud rate. Still count errors
         * and reject damaged data, but do not arm recovery in the first
         * second of a physical ESP wake. Recovery never restarts this window. */
        if (parallel_log[4] - uart_power_wake_tick < 128u)
            ++uart_startup_error_observations;
        else if (uart_bad_events < 8u)
            ++uart_bad_events;
        rx_fault = 1u;
        UART1_ICR = errors;
    }
    if (UART1_CSR & 2u)
    {
        uint8_t b = (uint8_t)UART1_RDR;
        if (b == (uint8_t)'\n')
            rx_time_end_tick = parallel_log[4];
        uart_last_activity_tick = parallel_log[4];
        UART1_ICR = 2u;
        uint32_t next = (rx_head + 1u) & 31u;
        if (next == rx_tail)
        {
            ++uart_probe_overflow;
            rx_fault = 1u;
        }
        else
        {
            rx_ring[rx_head] = b;
            rx_head = next;
        }
    }
}

void uart_probe_consume(uint8_t byte)
{
    Mm32UartEvent event;
    ++uart_probe_bytes;
    if (line_overflowed != 0u)
    {
        if (byte == (uint8_t)'\n')
        {
            line_overflowed = 0u;
            line_length = 0u;
        }
        return;
    }
    if (line_length == LINE_CAPACITY)
    {
        ++uart_probe_overflow;
        line_overflowed = 1u;
        line_length = 0u;
        return;
    }
    line[line_length++] = byte;
    if (byte != (uint8_t)'\n')
    {
        return;
    }
    ++uart_probe_lines;
    if (mm32_uart_parse_esp_line(line, line_length, &event))
    {
        if (event.kind == MM32_UART_SLEEP)
        {
            esp_sleep_requested = 1u;
            ++minute_log[158];
        }
        if (minute_log[211] &&
            (event.kind == MM32_UART_TICK ||
             (event.kind == MM32_UART_TIME && event.year >= 2000u && event.year <= 2099u)))
        {
            minute_log[210] = parallel_log[4];
            if (event.kind == MM32_UART_TIME && !minute_log[230])
                minute_log[212] = 1u;
        }
        if (event.kind == MM32_UART_CLEAN_ACK)
        {
            ++minute_log[236]; /* ACK latch survives following TICK/TIME lines. */
        }
        if (event.kind == MM32_UART_TIME)
        {
            /* A 50..57 byte 38400-baud record takes about 13..15 ms.
             * R12 starts it at .000; subtract two 128 Hz ticks. Capture
             * at RX, not after a possibly lengthy echo/calendar access. */
            uint32_t end = parallel_log[4] - rx_time_end_tick <= 4u ?
                           rx_time_end_tick : parallel_log[4];
            uint32_t origin = end - 2u;
            uart_bad_events = 0u; /* A validated record ends the bad run. */
            uint32_t acknowledge = event.year >= 2000u && event.year <= 2099u &&
                                   !minute_log[229] && !minute_log[230] &&
                                   parallel_log[2] != 6u && parallel_log[2] != 14u;
            /* Set before publishing changed settings: a SysTick restart
             * cannot cut ESP/UART power halfway through its confirmation. */
            uart_echo_active = acknowledge;
            if (event.year >= 2000u && event.year <= 2099u)
                parallel_uart_settings(&event);
            if (acknowledge && !minute_log[190])
            {
                if ((pending_time_meta & PENDING_TIME_VALID) || daily_log[0] == 7u || minute_log[204] ||
                    (parallel_log[6] && (parallel_log[2] != 7u || daily_log[13])))
                {
                    /* Retain BEFORE echo: ESP may sleep after confirmation.
                     * Newest complete valid update supersedes the mailbox,
                     * never the immutable correction already in progress. */
                    pending_time_date = event.year | ((uint32_t)(uint16_t)event.utc_offset_minutes << 16);
                    pending_time_clock = event.month | ((uint32_t)event.day << 8) |
                        ((uint32_t)event.hour << 16) | ((uint32_t)event.minute << 24);
                    pending_time_tick = origin;
                    pending_time_meta = PENDING_TIME_VALID | event.second |
                        ((uint32_t)event.dst_pending << 8) |
                        ((uint32_t)event.scheduled_hour << 16) |
                        ((uint32_t)event.scheduled_minute << 24);
                }
                else
                {
                    published_time_tick = origin;
                    uart_probe_time_event = event;
                    ++uart_probe_good_time;
                }
            }
            else if (parallel_log[2] == 6u && parallel_log[3] == 6u &&
                     ap_recovery[0] == 2u && !minute_log[229] && !minute_log[230])
            {
                /* Error-6 setup recovery needs evidence of a NEW valid TIME
                 * after CLEAN_OK. Motors remain latched off until its reset.
                 * All other fault/REC paths still reject publication/echo. */
                published_time_tick = origin;
                uart_probe_time_event = event;
                ++uart_probe_good_time;
            }
            if (acknowledge)
                uart_time_echo();
            uart_echo_active = 0u;
            if (minute_log[190]) /* Style change: motor tick owns safe restart. */
            {
                line_length = 0u;
                return;
            }
        }
        else if (event.kind == MM32_UART_TICK)
        {
            ++uart_probe_good_tick;
        }
    }
    else
    {
        ++uart_probe_rejected;
    }
    line_length = 0u;
}

__attribute__((noinline)) void uart_probe_poll_once(void)
{
    /* Also capture once here, under a short mask, for deterministic polling
     * and software tests. The IRQ independently captures during parsing/I2C. */
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    UART2_Handler();
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
    if (rx_fault)
    {
        __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
        rx_tail = rx_head;
        rx_fault = 0u;
        __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
        line_length = 0u;
        line_overflowed = 1u;
    }
    while (rx_tail != rx_head)
    {
        uint8_t byte = rx_ring[rx_tail];
        rx_tail = (rx_tail + 1u) & 31u;
        uart_probe_consume(byte);
        if (rx_fault)
            break;
    }
    uart_recovery_poll();
}

#endif
