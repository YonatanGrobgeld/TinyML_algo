/*
 * GEMV accelerator on-target self-test.
 *
 * Link with code that provides uart_write_char(char) (e.g. uart_litex.c or main stub).
 * Returns 0 on PASS, nonzero on FAIL.
 */
#ifndef TESTS_GEMV_H
#define TESTS_GEMV_H

#ifdef __cplusplus
extern "C" {
#endif

int test_gemv(void);

#ifdef __cplusplus
}
#endif

#endif /* TESTS_GEMV_H */
