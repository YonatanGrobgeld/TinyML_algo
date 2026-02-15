/*
 * Minimal UART API for LiteX bare-metal firmware.
 *
 * When building with LiteX, add -DUSE_LITEX_UART and -I<path_to_generated>,
 * compile uart_litex.c (which includes generated/csr.h), and link it.
 * Then include this header in main.c / demo_main.c so uart_write_char()
 * is provided by uart_litex.c.
 *
 * Without USE_LITEX_UART, use the local stubs in main.c / demo_main.c.
 */
#ifndef UART_LITEX_H
#define UART_LITEX_H

#ifdef __cplusplus
extern "C" {
#endif

/* Write a single character to the LiteX UART (blocking until TX not full). */
void uart_write_char(char c);

#ifdef __cplusplus
}
#endif

#endif /* UART_LITEX_H */
