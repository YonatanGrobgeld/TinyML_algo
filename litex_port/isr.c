/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  The interrupt handler required by the startup code (crt0.S). It is intentionally EMPTY:
 *  this firmware never uses interrupts - everything is simple polling loops.
 *  BIG PICTURE: Exists only so the firmware links; keeps the design deterministic.
 * ==========================================================================
 */

// Interrupt Service Routine (ISR)
// Required by crt0.S

void isr(void);

void isr(void)
{
    // Default ISR: do nothing
    // In a real application, this would handle UART interrupts, timer ticks, etc.
}
