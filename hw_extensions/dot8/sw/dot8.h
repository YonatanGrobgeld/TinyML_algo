/*
 * DOT8 (4-lane signed int8 dot-product) — C API for custom instruction.
 *
 * Defining USE_DOT8_HW requires the SoC to include the corresponding HW block (VexRiscv
 * Dot8Plugin); otherwise keep the macro off and the code uses the software fallback.
 *
 * Packing: lane 0 in LSB (byte 0), lane 1 in byte 1, lane 2 in byte 2, lane 3 in byte 3.
 * All lanes are signed int8; result is signed int32.
 * When USE_DOT8_HW is defined and the VexRiscv DOT8 plugin is present, uses inline asm.
 * Otherwise uses software fallback (so tests can run without hardware).
 */

#ifndef DOT8_H
#define DOT8_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Pack 4 signed int8s into one uint32_t: a[0]=LSB .. a[3]=MSB (little-endian). */
static inline uint32_t dot8_pack(const int8_t a[4])
{
    return (uint32_t)(uint8_t)a[0]
         | ((uint32_t)(uint8_t)a[1] << 8)
         | ((uint32_t)(uint8_t)a[2] << 16)
         | ((uint32_t)(uint8_t)a[3] << 24);
}

/* 4-lane signed int8 dot-product: sum_i (a_i * b_i), result int32.
 * When USE_DOT8_HW: uses custom-0 instruction (opcode 0x0B, funct7=0x01).
 * Otherwise: software reference. */
int32_t dot8_4_lanes(uint32_t a_packed, uint32_t b_packed);

#ifdef __cplusplus
}
#endif

#endif /* DOT8_H */
