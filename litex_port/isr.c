// Interrupt Service Routine (ISR)
// Required by crt0.S

void isr(void);

void isr(void)
{
    // Default ISR: do nothing
    // In a real application, this would handle UART interrupts, timer ticks, etc.
}
