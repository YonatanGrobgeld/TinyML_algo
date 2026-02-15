/*
 * DOT8 on-target self-test.
 * Link with code that provides uart_write_char (e.g. uart_litex.c).
 * Returns 0 on PASS, nonzero on FAIL.
 */
#ifndef TESTS_DOT8_H
#define TESTS_DOT8_H

#ifdef __cplusplus
extern "C" {
#endif

int test_dot8(void);

#ifdef __cplusplus
}
#endif

#endif /* TESTS_DOT8_H */
