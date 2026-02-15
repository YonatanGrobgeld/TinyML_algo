/*
 * DOT8 — 4-lane signed int8 dot-product.
 * Defining USE_DOT8_HW requires the SoC to include the corresponding HW block; otherwise keep macro off.
 * Opcode custom-0 (0x0B), funct7=0x01. rs1/rs2 = packed int8, rd = int32.
 * Packing: byte0=LSB (lane 0) .. byte3=MSB (lane 3). Signed lanes.
 */

#include "dot8.h"

/* Software reference: signed int8 lanes, int32 result. */
static int32_t dot8_sw(uint32_t a_packed, uint32_t b_packed)
{
    int32_t a0 = (int32_t)(int8_t)(a_packed >> 0);
    int32_t a1 = (int32_t)(int8_t)(a_packed >> 8);
    int32_t a2 = (int32_t)(int8_t)(a_packed >> 16);
    int32_t a3 = (int32_t)(int8_t)(a_packed >> 24);
    int32_t b0 = (int32_t)(int8_t)(b_packed >> 0);
    int32_t b1 = (int32_t)(int8_t)(b_packed >> 8);
    int32_t b2 = (int32_t)(int8_t)(b_packed >> 16);
    int32_t b3 = (int32_t)(int8_t)(b_packed >> 24);
    return a0 * b0 + a1 * b1 + a2 * b2 + a3 * b3;
}

int32_t dot8_4_lanes(uint32_t a_packed, uint32_t b_packed)
{
#if defined(USE_DOT8_HW)
    int32_t result;
    /* custom-0 opcode 0x0B, funct7=0x01; rd = dot-product of rs1/rs2 (4x signed int8). */
    __asm__ volatile (
        "custom0 1, %0, %1, %2"
        : "=r"(result)
        : "r"(a_packed), "r"(b_packed)
        /* no clobbers: instruction uses only reg operands */
    );
    return result;
#else
    return dot8_sw(a_packed, b_packed);
#endif
}
