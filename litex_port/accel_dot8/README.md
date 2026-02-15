# DOT8 — 8‑lane int8 dot-product accelerator only

TinyFormer build that uses the **DOT8** custom instruction (VexRiscv plugin) only. No Exp LUT or GEMV.

- **Macros:** `USE_DOT8_HW`
- **SoC:** VexRiscv with Dot8Plugin; no Exp LUT or GEMV peripheral required.
- **Banner:** `MODE: DOT8`

Add `-DUSE_DOT8_HW`, `-I hw_extensions/dot8/sw`, and link `hw_extensions/dot8/sw/dot8.c` when the encoder uses the DOT8 path.
