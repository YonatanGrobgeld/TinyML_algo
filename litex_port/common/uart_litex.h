/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Header for the UART driver: declares uart_write_char / uart_write_string /
 *  uart_read_char used by all printing code.
 *  BIG PICTURE: The printing interface for the whole firmware.
 * ==========================================================================
 */

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

/* Read a single character from the LiteX UART (blocking until RX not empty). */
char uart_read_char(void);

/* Write a null-terminated string to the LiteX UART. */
void uart_write_string(const char *s);

#ifdef __cplusplus
}
#endif

#endif /* UART_LITEX_H */
