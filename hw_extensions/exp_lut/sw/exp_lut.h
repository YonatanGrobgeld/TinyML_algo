/*
 * Exp LUT — softmax helper (Q10, index 0..15 = exp(0)..exp(-15)).
 * Defining USE_EXP_LUT_HW requires the SoC to include the corresponding HW block; otherwise keep macro off.
 * When USE_EXP_LUT_HW: read from MMIO (write index, read value).
 * Otherwise: return software golden table (matches tinyformer.c exp_lut[]).
 */

#ifndef EXP_LUT_H
#define EXP_LUT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Index 0..15 → exp(0)..exp(-15) in Q10 (value/1024). Returns 16-bit. */
uint16_t exp_lut_hw(unsigned idx);

#ifdef __cplusplus
}
#endif

#endif /* EXP_LUT_H */
