# Hardware Extensions for TinyFormer Accelerator

This directory contains **hardware extension designs** intended to accelerate the TinyFormer inference kernel (see `litex_port/`) when running on VexRiscv (LiteX, Nexys4DDR). The extensions are **prepared for integration** but are **not yet wired** into the CPU or SoC.

**Status:** Structure, documentation, and skeleton RTL/plugin code only. No VexRiscv integration, no LiteX CSR wiring, no C intrinsics.

---

## Extensions

| Extension | Purpose | Integration target |
|-----------|---------|---------------------|
| **#1 DOT8** | Packed int8 dot-product → int32 (MAC). Accelerates Q/K/V, attention scores, FFN matvec inner loops. | VexRiscv custom instruction (SpinalHDL plugin) |
| **#2 Exp LUT** | Small LUT for `exp(score - max)` in softmax. Input index (e.g. -15..0) → fixed-point exp value. | LiteX MMIO peripheral (Verilog); optional custom instruction later |
| **#3 GEMV** | Matrix–vector multiply Y = W×X + b (int8 W/X, int32 Y). CSR-fed; LEN/OUT_DIM 32 or 64. | LiteX MMIO peripheral (Verilog + Python wrapper) |

---

## Directory layout

```
hw_extensions/
├── README.md          (this file)
├── dot8/              Extension #1: INT8 dot-product / MAC
│   ├── README.md
│   ├── Dot8Plugin.scala
│   ├── encoding.md
│   └── sw/
│       ├── dot8.h
│       └── dot8.c         (C API + inline asm when USE_DOT8_HW)
├── exp_lut/           Extension #2: Exp LUT (softmax helper)
│   ├── README.md
│   ├── exp_lut.v
│   ├── exp_lut_spec.md
│   ├── litex/
│   │   └── exp_lut_periph.py
│   └── sw/
│       ├── exp_lut.h
│       └── exp_lut.c      (driver + golden table; USE_EXP_LUT_HW)
└── gemv/              Extension #3: GEMV accelerator
    ├── README.md
    ├── gemv_spec.md
    ├── rtl/
    │   └── gemv_core.v
    ├── litex/
    │   └── gemv_periph.py
    └── sw/
        ├── gemv.h
        └── gemv.c
```

---

## On-target self-tests

- **DOT8:** `litex_port/tests_dot8.c` + `hw_extensions/dot8/sw/dot8.c`. Run `test_dot8()`; PASS prints `DOT8 PASS`. Use `-I hw_extensions/dot8/sw`; optional `-DUSE_DOT8_HW` when the custom instruction is present.
- **Exp LUT:** `litex_port/tests_lut.c` + `hw_extensions/exp_lut/sw/exp_lut.c`. Run `test_lut()`; PASS prints `LUT PASS`. Use `-I hw_extensions/exp_lut/sw`; optional `-DUSE_EXP_LUT_HW` and CSR or EXP_LUT_BASE.
- **GEMV:** `litex_port/tests_gemv.c`; see `hw_extensions/gemv/README.md`.

See root **README.md** § "Hardware extension self-tests" for build/run and typical failure causes.

## Next steps (for integration)

1. **DOT8:** Complete execute/writeback in `Dot8Plugin.scala`, add to VexRiscv plugin list; use `dot8.h` / `dot8_4_lanes()` from firmware.
2. **Exp LUT:** Instantiate `exp_lut.v` and `exp_lut_periph.py` in LiteX SoC; use `exp_lut_hw(idx)` from firmware or replace `score_to_exp` in `tinyformer.c` with MMIO read.
3. **GEMV:** Add `gemv_periph.py` and `rtl/gemv_core.v` to the SoC build; link `sw/gemv.c` in firmware; call `gemv_*` from TinyFormer or a test harness when ready.
4. Validate on Nexys4DDR: timing, area, and correctness vs. pure-software TinyFormer run.
