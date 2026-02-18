/*
 * Golden minimal UART implementation for LiteX.
 *
 * Compile with -DUSE_LITEX_UART and -I<litex_build>/software/include
 * (or wherever generated/csr.h lives).
 *
 * Selects implementation by CSR address macros (not CSR_*_BASE):
 *   - CSR_UART_RXTX_ADDR   -> uart_txfull_read() / uart_rxtx_write()
 *   - CSR_SERIAL_RXTX_ADDR -> serial_txfull_read() / serial_rxtx_write()
 * If neither is defined, falls back to stub. Blocking poll only; no libc.
 */
#include <stdint.h>

#if defined(USE_LITEX_UART)
#include <generated/csr.h>

#if defined(CSR_UART_RXTX_ADDR)
/* UART exposed as uart_* (e.g. default LiteX UART) */
void uart_write_char(char c) {
  while (uart_txfull_read())
    ;
  uart_rxtx_write((uint8_t)c);
}

void uart_write_string(const char *s) {
  while (*s != '\0') {
    uart_write_char(*s);
    s++;
  }
}

char uart_read_char(void) {
  while (uart_rxempty_read())
    ;
  return (char)uart_rxtx_read();
}

#elif defined(CSR_SERIAL_RXTX_ADDR)
/* UART exposed as serial_* (alternative LiteX naming) */
void uart_write_char(char c) {
  while (serial_txfull_read())
    ;
  serial_rxtx_write((uint8_t)c);
}

char uart_read_char(void) {
  while (serial_rxempty_read())
    ;
  return (char)serial_rxtx_read();
}

void uart_write_string(const char *s) {
  while (*s != '\0') {
    uart_write_char(*s);
    s++;
  }
}

#else
/* No UART/serial CSR present: stub so file still links */
void uart_write_char(char c) { (void)c; }
char uart_read_char(void) { return 0; }
void uart_write_string(const char *s) { (void)s; }

#endif

#else
/* Build without USE_LITEX_UART: stub for non-LiteX builds */
void uart_write_char(char c) { (void)c; }
char uart_read_char(void) { return 0; }
void uart_write_string(const char *s) { (void)s; }

#endif /* USE_LITEX_UART */
