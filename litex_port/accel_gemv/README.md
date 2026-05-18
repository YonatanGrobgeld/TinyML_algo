# GEMV — GEMV accelerator only (uses v2 packed peripheral)

TinyFormer build that uses the **GEMV** peripheral for matrix-vector ops only. No DOT8 or Exp LUT.

- **Macros:** `USE_GEMV_HW`, `GEMV_USE_LITEX_CSR`
- **SoC:** VexRiscv + LiteX with v2 GEMV peripheral (32-bit packed `X_IN`/`W_IN`, 4-lane parallel MAC); no Dot8 plugin or Exp LUT required.
- **Banner:** `MODE: GEMV`

The shared driver (`../hw_extensions/gemv/sw/gemv.c`) packs four signed int8 lanes per CSR write via `pack4_i8()` and matches the v2 hardware. The non-`USE_EXP_LUT_HW` path of `tinyformer.c` falls back to the honest software exp() (no LUT), so this build's softmax cost is the full ~21 K cycles/call — only matvec is hardware-accelerated; attention DOT products and softmax exp() stay in software. Use `accel_all` for the full speedup.

Build: `-DUSE_GEMV_HW -DGEMV_USE_LITEX_CSR`, `-I hw_extensions/gemv/sw`, link `hw_extensions/gemv/sw/gemv.c`.
