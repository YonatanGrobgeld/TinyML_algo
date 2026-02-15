# GEMV — GEMV accelerator only

TinyFormer build that uses the **GEMV** peripheral for matrix-vector ops only. No DOT8 or Exp LUT.

- **Macros:** `USE_GEMV_HW`
- **SoC:** VexRiscv + LiteX with GEMV peripheral; no Dot8 plugin or Exp LUT required.
- **Banner:** `MODE: GEMV`

Add `-DUSE_GEMV_HW`, `-I hw_extensions/gemv/sw`, and link `hw_extensions/gemv/sw/gemv.c`. Ensure LiteX CSR include path and GEMV base address are set as needed.
