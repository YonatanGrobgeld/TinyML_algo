# Baseline — no hardware accelerators

Runs TinyFormer on an **unmodified VexRiscv** (no custom instructions or accelerator peripherals). Use this as the reference for correctness and performance comparison.

- **Macros:** none (`USE_DOT8_HW`, `USE_EXP_LUT_HW`, `USE_GEMV_HW` all undefined).
- **SoC:** Plain VexRiscv + LiteX; no DOT8 plugin, no Exp LUT, no GEMV peripheral.
- **Banner:** `MODE: BASELINE`

Build with common sources and this main; no accelerator driver or extra include paths.
