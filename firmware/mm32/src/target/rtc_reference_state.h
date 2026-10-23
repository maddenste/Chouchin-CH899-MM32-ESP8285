/* Active RTC-reference state and health evidence, not a motor pulse trace.
 * RC6S retains the symbol/section but moves this block to 0x20000AE0.
 * Decode new dumps by symbol; old C40 write commands are NOT compatible. */
__attribute__((section("PULSE_DIAG"))) volatile uint32_t pulse_diag[40];
