/*
 * Exp LUT on-target self-test.
 * Link with code that provides uart_write_char. Returns 0 on PASS, nonzero on FAIL.
 */
#ifndef TESTS_LUT_H
#define TESTS_LUT_H

#ifdef __cplusplus
extern "C" {
#endif

int test_lut(void);

#ifdef __cplusplus
}
#endif

#endif /* TESTS_LUT_H */
