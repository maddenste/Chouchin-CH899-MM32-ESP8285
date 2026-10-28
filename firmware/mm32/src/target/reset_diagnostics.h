#ifndef MM32_RESET_DIAGNOSTICS_H
#define MM32_RESET_DIAGNOSTICS_H
#include <stdint.h>

/* RC6BF bench diagnostics. Words80..87 were unused in RC6BE. They do not
 * move any existing object or consume the reserved interrupt stack. */
extern volatile uint32_t seconds_log[256];
enum {
    MM32_RESET_DIAG_FIRST = 80u,
    MM32_RESET_DIAG_WORDS = 8u,
    MM32_RESET_DIAG_MAGIC = 0x52424631u,
    MM32_RESET_COOKIE_XOR = 0xa95c73e1u,
    MM32_RESET_SETTINGS = 1u,
    MM32_RESET_CLEAN = 2u,
    MM32_SCHEDULED_WAKE_DELAY = 3u
};
#define reset_diag (seconds_log + MM32_RESET_DIAG_FIRST)
#define MM32_RESET_CSR (*(volatile uint32_t *)0x40021024u)
_Static_assert(MM32_RESET_DIAG_FIRST > 79u &&
               MM32_RESET_DIAG_FIRST + MM32_RESET_DIAG_WORDS <= 213u,
               "reset diagnostics overlap operational seconds state");

static inline void reset_note_request(uint32_t reason)
{
    reset_diag[6] = reason;
    reset_diag[7] = reason ^ MM32_RESET_COOKIE_XOR;
}

/* Read before zero-initialization. A retained cookie is only relevant to a
 * software reset, never a power reset or an unqualified SRAM remnant. */
static inline uint32_t reset_previous_request(uint32_t flags)
{
    if ((flags & ((1u << 28) | (1u << 27))) == (1u << 28) &&
        reset_diag[0] == MM32_RESET_DIAG_MAGIC &&
        (reset_diag[6] == MM32_RESET_SETTINGS || reset_diag[6] == MM32_RESET_CLEAN) &&
        reset_diag[7] == (reset_diag[6] ^ MM32_RESET_COOKIE_XOR))
        return reset_diag[6];
    return 0u;
}

/* Called after normal C initialization, before main/SysTick. Current boot
 * keeps the original flags, then clears historical hardware flags once.
 * Words4/5 later retain scheduled due/activation seconds, not motor timing. */
static inline void reset_record_boot(uint32_t flags, uint32_t reason)
{
    reset_diag[0] = MM32_RESET_DIAG_MAGIC;
    reset_diag[1] = flags;
    reset_diag[3] = reason;
    MM32_RESET_CSR = flags | (1u << 24); /* Exact SPIN05 RCC_CSR RMVF. */
    reset_diag[2] = MM32_RESET_CSR;
}
#endif
