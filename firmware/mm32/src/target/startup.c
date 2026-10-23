#include <stdint.h>

/* MM32SPIN05PF: 32 KiB flash at 08000000, 4 KiB SRAM at 20000000.
 * Cortex-M0 vectors from the vendor's MM32SPIN05x_q SVD. No peripherals
 * are enabled by this startup file. */
extern uint8_t Image$$RW_IRAM1$$Base[];
extern uint8_t Image$$RW_IRAM1$$Limit[];
extern uint8_t Load$$RW_IRAM1$$Base[];
extern uint8_t Image$$RW_IRAM1$$ZI$$Base[];
extern uint8_t Image$$RW_IRAM1$$ZI$$Limit[];
extern uint8_t Image$$DIAG_RAM$$Base[];
extern uint8_t Image$$DIAG_RAM$$Limit[];

int main(void);

void Default_Handler(void) __attribute__((weak));
void Default_Handler(void)
{
    for (;;)
    {
        __asm volatile("wfi");
    }
}

void SysTick_Handler(void) __attribute__((weak, alias("Default_Handler")));
void PendSV_Handler(void) __attribute__((weak, alias("Default_Handler")));
void UART2_Handler(void) __attribute__((weak, alias("Default_Handler")));
void TIM3_Handler(void) __attribute__((weak, alias("Default_Handler")));
void TIM14_Handler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel2_3_Handler(void) __attribute__((weak, alias("Default_Handler")));

void Reset_Handler(void)
{
    uint8_t *dst;
    const uint8_t *src = Load$$RW_IRAM1$$Base;
    for (dst = Image$$RW_IRAM1$$Base; dst < Image$$RW_IRAM1$$Limit; ++dst)
    {
        *dst = *src++;
    }
    for (dst = Image$$RW_IRAM1$$ZI$$Base; dst < Image$$RW_IRAM1$$ZI$$Limit; ++dst)
    {
        *dst = 0;
    }
    /* This separately located block is outside RW_IRAM1. Flash programming
     * can leave arbitrary SRAM here; never interpret that as valid telemetry. */
    for (dst = Image$$DIAG_RAM$$Base; dst < Image$$DIAG_RAM$$Limit; ++dst)
    {
        *dst = 0;
    }
    (void)main();
    Default_Handler();
}

/* 16 architectural entries plus 29 external entries, IRQ 0..28.
 * All unimplemented interrupts trap safely; no guessed IRQ wiring. */
__attribute__((section("RESET"), used)) const uintptr_t mm32_vectors[45] = {
    [0] = 0x20001000u,
    [1] = (uintptr_t)Reset_Handler,
    [2] = (uintptr_t)Default_Handler,  /* NMI */
    [3] = (uintptr_t)Default_Handler,  /* HardFault */
    [11] = (uintptr_t)Default_Handler, /* SVCall */
    [14] = (uintptr_t)PendSV_Handler,  /* Deferred clock tick, same priority. */
    [15] = (uintptr_t)SysTick_Handler, /* SysTick */
    [16 ... 25] = (uintptr_t)Default_Handler,
    [26] = (uintptr_t)DMA1_Channel2_3_Handler, /* DMA channel 2 transfer error. */
    [27 ... 31] = (uintptr_t)Default_Handler,
    [32] = (uintptr_t)TIM3_Handler, /* Vendor TIM3 IRQ16. */
    [33 ... 34] = (uintptr_t)Default_Handler,
    [35] = (uintptr_t)TIM14_Handler, /* Vendor TIM14 IRQ19. */
    [36 ... 43] = (uintptr_t)Default_Handler,
    [44] = (uintptr_t)UART2_Handler /* Vendor SVD: IRQ28 */
};
