/*
 * Exp LUT on-target self-test: golden table vs exp_lut_hw; score_to_exp mapping.
 * Golden matches tinyformer.c exp_lut[16]. No printf/libc.
 */

#include <stdint.h>
#include "tests_lut.h"
#include "exp_lut.h"

extern void uart_write_char(char c);

static void uart_write_string(const char *s)
{
    while (*s != '\0') { uart_write_char(*s); s++; }
}

static void uart_print_hex(uint32_t v)
{
    const char hex[] = "0123456789ABCDEF";
    uart_write_char('0'); uart_write_char('x');
    for (int i = 7; i >= 0; i--) uart_write_char(hex[(v >> (i * 4)) & 0xFu]);
}

/* Same as tinyformer.c: clamp x to [-15,0], return exp_lut[-x]. */
static uint16_t score_to_exp(int16_t x)
{
    if (x > 0) x = 0;
    else if (x < -15) x = -15;
    return exp_lut_hw((unsigned)(-x));
}

/* Golden table: must match tinyformer.c exp_lut[16] and exp_lut.v */
static const uint16_t golden[16] = {
    1024, 754, 556, 410, 302, 223, 165, 122, 90, 67, 50, 37, 28, 21, 16, 12
};

int test_lut(void)
{
    int i;
    uint16_t v;

    for (i = 0; i < 16; i++) {
        v = exp_lut_hw((unsigned)i);
        if (v != golden[i]) {
            uart_write_string("LUT FAIL idx=");
            uart_print_hex((uint32_t)i);
            uart_write_string(" golden=");
            uart_print_hex((uint32_t)golden[i]);
            uart_write_string(" hw=");
            uart_print_hex((uint32_t)v);
            uart_write_string("\r\n");
            return -1;
        }
    }

    for (i = 0; i >= -15; i--) {
        uint16_t expected = golden[-i];
        v = score_to_exp((int16_t)i);
        if (v != expected) {
            uart_write_string("LUT FAIL score_to_exp x=");
            uart_print_hex((uint32_t)(int16_t)i);
            uart_write_string(" expected=");
            uart_print_hex((uint32_t)expected);
            uart_write_string(" got=");
            uart_print_hex((uint32_t)v);
            uart_write_string("\r\n");
            return -1;
        }
    }

    uart_write_string("LUT PASS\r\n");
    return 0;
}
