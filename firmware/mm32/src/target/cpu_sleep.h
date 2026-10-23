/* Ordinary Sleep, all peripheral clocks retained. No profiling counters.
 * IRQ generation prevents sleeping after an ISR queues work during polling.
 * Keep the ESP session fully awake. PRIMASK is restored on every path.
 */
__attribute__((noinline)) void cpu_sleep_idle(uint32_t epoch)
{
    uint32_t mask;
    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
    if (mask || seconds_log[213] != epoch || minute_log[211] ||
        (REG32(0xe000ed04u) & ((1u << 26) | (1u << 28))) || REG32(0xe000e200u))
    {
        __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
        return;
    }
    __asm volatile("dsb\n wfi\n isb" ::: "memory");
    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
}
