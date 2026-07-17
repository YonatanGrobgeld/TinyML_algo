/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Driver for the exp lookup with the golden table built in. With USE_EXP_LUT_HW it does
 *  2 bus operations (write index, read value, ~12 cycles); without it, it returns the same
 *  value from the identical software table - so tests can run with no hardware present.
 *  BIG PICTURE: Same answers either way; only the speed changes.
 * ==========================================================================
 */

/*
 * Exp LUT driver. Golden table matches litex_port/tinyformer.c exp_lut[16] (Q10).
 * Defining USE_EXP_LUT_HW requires the SoC to include the corresponding HW block; otherwise keep macro off.
 * USE_EXP_LUT_HW: use MMIO. EXP_LUT_USE_LITEX_CSR + generated/csr.h, or EXP_LUT_BASE for raw MMIO.
 */

#include "exp_lut.h"
#if defined(USE_EXP_LUT_HW) && defined(EXP_LUT_USE_LITEX_CSR)
#  include <generated/csr.h>
#endif

/* Golden table: same as tinyformer.c exp_lut[] — do not change. */
static const uint16_t exp_lut_golden[16] = {
    1024, 754, 556, 410, 302, 223, 165, 122, 90, 67, 50, 37, 28, 21, 16, 12
};

uint16_t exp_lut_hw(unsigned idx)
{
#if defined(USE_EXP_LUT_HW)
    if (idx > 15u) return exp_lut_golden[15];
#  if defined(EXP_LUT_USE_LITEX_CSR)
    /* SIMPLE WORDS: write the question (index), read the answer (value) -
     * 2 bus operations, ~12 cycles, vs ~21,000 cycles for the software exp(). */
    exp_lut_index_write((uint32_t)idx);
    return (uint16_t)exp_lut_value_read();
#  else
    /* Raw MMIO: define EXP_LUT_BASE; INDEX at 0x00, VALUE at 0x04 */
    *(volatile uint32_t *)(EXP_LUT_BASE + 0x00) = (uint32_t)idx;
    return (uint16_t)(*(volatile uint32_t *)(EXP_LUT_BASE + 0x04) & 0xFFFFu);
#  endif
#else
    if (idx > 15u) return exp_lut_golden[15];
    return exp_lut_golden[idx];
#endif
}
