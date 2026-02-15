/*
 * GEMV on-target self-test: software reference GEMV vs hardware, compare Y.
 * Deterministic inputs (LCG). No printf/malloc; uses uart_write_char for output.
 *
 * Link with: gemv.c, and code providing uart_write_char (e.g. uart_litex.c).
 * Define GEMV_USE_LITEX_CSR or GEMV_BASE as for the driver.
 */

#include <stdint.h>
#include "tests_gemv.h"
#include "gemv.h"

extern void uart_write_char(char c);

static void uart_write_string(const char *s)
{
    while (*s != '\0') {
        uart_write_char(*s);
        s++;
    }
}

static void uart_print_hex(uint32_t value)
{
    const char hex[] = "0123456789ABCDEF";
    int i;
    uart_write_char('0');
    uart_write_char('x');
    for (i = 7; i >= 0; i--) {
        uint32_t n = (value >> (i * 4)) & 0xFu;
        uart_write_char(hex[n]);
    }
}

/* Deterministic LCG for int8 (no libc rand) */
static uint32_t lcg = 1u;
static int8_t lcg_next_int8(void)
{
    lcg = lcg * 1664525u + 1013904223u;
    return (int8_t)(lcg >> 24);
}

/* Software reference: Y = W*X (no bias). W row-major [out_dim][len], X [len], Y [out_dim]. */
static void gemv_ref(const int8_t *w, const int8_t *x, int out_dim, int len, int32_t *y)
{
    int i, k;
    for (i = 0; i < out_dim; i++) {
        int32_t acc = 0;
        for (k = 0; k < len; k++)
            acc += (int32_t)w[i * len + k] * (int32_t)x[k];
        y[i] = acc;
    }
}

#define MAX_LEN    64
#define MAX_OUT    64
static int8_t  ref_x[MAX_LEN];
static int8_t  ref_w[MAX_OUT * MAX_LEN];
static int32_t ref_y[MAX_OUT];
static int32_t hw_y[MAX_OUT];

static int run_one(int len, int out_dim)
{
    int i;
    lcg = 1u;
    for (i = 0; i < len; i++)
        ref_x[i] = lcg_next_int8();
    for (i = 0; i < out_dim * len; i++)
        ref_w[i] = lcg_next_int8();

    gemv_ref(ref_w, ref_x, out_dim, len, ref_y);

    gemv_clear_done();
    gemv_load_x(ref_x, len);
    gemv_load_w(ref_w, out_dim, len);
    gemv_start(len, out_dim, 0);
    gemv_wait_done();
    gemv_read_y(hw_y, out_dim);

    for (i = 0; i < out_dim; i++) {
        if (hw_y[i] != ref_y[i]) {
            uart_write_string("FAIL len=");
            uart_print_hex((uint32_t)len);
            uart_write_string(" out_dim=");
            uart_print_hex((uint32_t)out_dim);
            uart_write_string(" i=");
            uart_print_hex((uint32_t)i);
            uart_write_string(" ref=");
            uart_print_hex((uint32_t)ref_y[i]);
            uart_write_string(" hw=");
            uart_print_hex((uint32_t)hw_y[i]);
            uart_write_string("\r\n");
            return -1;
        }
    }
    return 0;
}

int test_gemv(void)
{
    if (run_one(32, 32) != 0) return -1;
    if (run_one(64, 32) != 0) return -1;
    if (run_one(32, 64) != 0) return -1;
    if (run_one(64, 64) != 0) return -1;
    uart_write_string("GEMV self-test PASS\r\n");
    return 0;
}
