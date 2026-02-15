# LUT — Exp LUT hardware only

TinyFormer build that uses the **Exp LUT** peripheral for softmax only. No DOT8 or GEMV.

- **Macros:** `USE_EXP_LUT_HW`
- **SoC:** VexRiscv + LiteX with exp_lut peripheral; no Dot8 plugin or GEMV required.
- **Banner:** `MODE: LUT`

Add `-DUSE_EXP_LUT_HW`, `-I hw_extensions/exp_lut/sw`, and link the exp_lut driver when the encoder uses the LUT path.
