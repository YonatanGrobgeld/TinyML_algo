# DOT8 + LUT — dot-product and Exp LUT hardware

TinyFormer build with **DOT8** and **Exp LUT** accelerators; no GEMV.

- **Macros:** `USE_DOT8_HW`, `USE_EXP_LUT_HW`
- **SoC:** VexRiscv with Dot8Plugin + LiteX exp_lut peripheral.
- **Banner:** `MODE: DOT8 + LUT`

Add both macro defines and include/link paths for dot8 and exp_lut sw.
