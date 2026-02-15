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
