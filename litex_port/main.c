// Bare‑metal entry point for TinyFormer on LiteX / VexRiscv.
//
// This file avoids any libc features (no malloc, no printf) and uses only
// fixed‑size arrays. UART functions are provided as stubs so that the code
// can be compiled on a bare‑metal RV32IM target and later wired up to the
// actual LiteX UART peripheral.

#include <stdint.h>
#include "tinyformer.h"

// --- UART stubs -----------------------------------------------------------
// Replace these with real LiteX UART MMIO accessors in your SoC.

static void uart_write_char(char c)
{
    (void)c;
    // Implement: wait for TX ready, then store c into UART TX register.
}

static void uart_write_string(const char *s)
{
    while (*s != '\0') {
        uart_write_char(*s);
        s++;
    }
}

// Simple hex printing without libc.
static void uart_write_hex32(uint32_t value)
{
    int i;
    for (i = 7; i >= 0; --i) {
        uint32_t nibble = (value >> (i * 4)) & 0xFu;
        char c = (nibble < 10u) ? (char)('0' + nibble)
                                : (char)('A' + (nibble - 10u));
        uart_write_char(c);
    }
}

// --- Simple pseudo‑random initializer -------------------------------------
// Tiny LCG to generate deterministic int8_t input data without libc.

static uint32_t lcg_state = 1u;

static uint8_t lcg_next_u8(void)
{
    lcg_state = lcg_state * 1664525u + 1013904223u;
    return (uint8_t)(lcg_state >> 24);
}

// --- Main application -----------------------------------------------------

int main(void)
{
    static int8_t input[TINYFORMER_S][TINYFORMER_D];
    static int8_t output[TINYFORMER_S][TINYFORMER_D];

    // Initialize input with deterministic pseudo‑random data.
    int32_t s, d;
    for (s = 0; s < TINYFORMER_S; ++s) {
        for (d = 0; d < TINYFORMER_D; ++d) {
            // Map 0..255 -> -128..127
            uint8_t r = lcg_next_u8();
            input[s][d] = (int8_t)(r - 128u);
        }
    }

    // Run TinyFormer encoder block.
    tinyformer_encode(input, output);

    // Compute a simple checksum over the output tensor.
    int32_t checksum = 0;
    for (s = 0; s < TINYFORMER_S; ++s) {
        for (d = 0; d < TINYFORMER_D; ++d) {
            checksum += (int32_t)output[s][d];
        }
    }

    // "Print" checksum using UART stubs (can be wired to LiteX UART).
    uart_write_string("TinyFormer checksum: 0x");
    uart_write_hex32((uint32_t)checksum);
    uart_write_string("\r\n");

    // End in an infinite loop (bare‑metal firmware style).
    while (1) {
        // Optionally enter low‑power mode or wait for interrupts.
    }

    // We never return.
    return 0;
}

