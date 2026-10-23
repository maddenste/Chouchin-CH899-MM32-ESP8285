#ifndef MM32_TIMER_ERRATA_H
#define MM32_TIMER_ERRATA_H
/* MM32SPIN05 errata Rev1.1, section 3.3.2 (q3/q4/q5/q6): SMS=000
 * with TS=000 can still reset CNT. A standalone timer MUST use TS=111.
 * SMS remains disabled; ECE remains clear. This is NOT external clocking.
 * https://www.mindmotion.com.cn/download/products/ES_MM32SPIN05_SC.pdf
 * Do not apply this to TIM1 while it intentionally counts TIM3 via ITR2.
 * TIM14 has no SMCR; offset 0x08 there is reserved, not a slave register.
 */
#define MM32_TIMER_STANDALONE_SMCR 0x70u
#define MM32_PULSE_COUNTER_SMCR 0x27u
#endif
