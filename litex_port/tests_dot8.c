/*
 * DOT8 on-target self-test: SW reference vs dot8_4_lanes (HW or SW).
 * Deterministic LCG; ~1000 iterations; UART on fail. No printf/libc.
 */

#include <stdint.h>
#include "tests_dot8.h"
#include "dot8.h"

extern void uart_write_char(char c);

static void uart_write_string(const char *s)
{
    while (*s != '\0') { uart_write_char(*s); s++; }
}

static void uart_print_hex(uint32_t v)
{
    const char hex[] = "0123456789ABCDEF";
    uart_write_char('0'); uart_write_char('x');
    for (int i = 7; i >= 0; i--) {
        uart_write_char(hex[(v >> (i * 4)) & 0xFu]);
    }
}

static uint32_t lcg_state = 1u;
static int8_t lcg_next_int8(void)
{
    lcg_state = lcg_state * 1664525u + 1013904223u;
    return (int8_t)(lcg_state >> 24);
}

#define NITER 1000

int test_dot8(void)
{
    int8_t a[4], b[4];
    uint32_t a_packed, b_packed;
    int32_t sw_dot, hw_dot;
    int i, iter;

    for (iter = 0; iter < NITER; iter++) {
        for (i = 0; i < 4; i++) {
            a[i] = lcg_next_int8();
            b[i] = lcg_next_int8();
        }
        a_packed = dot8_pack(a);
        b_packed = dot8_pack(b);

        sw_dot = (int32_t)(int8_t)(a[0]) * (int32_t)(int8_t)(b[0])
               + (int32_t)(int8_t)(a[1]) * (int32_t)(int8_t)(b[1])
               + (int32_t)(int8_t)(a[2]) * (int32_t)(int8_t)(b[2])
               + (int32_t)(int8_t)(a[3]) * (int32_t)(int8_t)(b[3]);
        hw_dot = dot8_4_lanes(a_packed, b_packed);

        if (hw_dot != sw_dot) {
            uart_write_string("DOT8 FAIL iter=");
            uart_print_hex((uint32_t)iter);
            uart_write_string(" sw=");
            uart_print_hex((uint32_t)sw_dot);
            uart_write_string(" hw=");
            uart_print_hex((uint32_t)hw_dot);
            uart_write_string("\r\n");
            return -1;
        }
    }
    uart_write_string("DOT8 PASS\r\n");
    return 0;
}
