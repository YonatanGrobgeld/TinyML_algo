# All — DOT8 + LUT + GEMV

TinyFormer build with **all** accelerators enabled: DOT8, Exp LUT, and GEMV.

- **Macros:** `USE_DOT8_HW`, `USE_EXP_LUT_HW`, `USE_GEMV_HW`
- **SoC:** VexRiscv with Dot8Plugin + LiteX exp_lut and GEMV peripherals.
- **Banner:** `MODE: DOT8 + LUT + GEMV`

Add all three macro defines and include/link paths for dot8, exp_lut, and gemv sw.
