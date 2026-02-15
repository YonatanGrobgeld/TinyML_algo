# Extension #3: GEMV (Matrix–Vector) Accelerator

## What GEMV is and how it fits TinyFormer

**GEMV** (general matrix–vector multiply) computes **Y = W × X + b**:
- **W**: `OUT_DIM × LEN` matrix (int8)
- **X**: vector of length `LEN` (int8)
- **b**: optional bias vector of length `OUT_DIM` (int32)
- **Y**: output vector of length `OUT_DIM` (int32)

In TinyFormer (`litex_port/tinyformer.c`), almost every layer is a matrix–vector product:
- **Q/K/V/O projections:** (32×32) × (32)
- **FFN layer 1:** (64×32) × (32)
- **FFN layer 2:** (32×64) × (64)

A dedicated GEMV accelerator offloads these inner loops from the CPU: the CPU streams in X and W (and optionally b), starts the core, then reads back Y. Requantization/saturation to int8 is left to software (or a future hardware block).

## v1 design and limitations

- **Memory model:** **CSR-fed** — no DMA, no bus-master. The CPU writes X and W (and optionally b) via MMIO registers, then reads Y via MMIO. All data passes through the CSR bus.
- **Compute:** Sequential: for each output row, accumulate dot-product in int32, then store. No parallelism in v1.
- **Supported sizes:** `LEN` and `OUT_DIM` each 32 or 64 (configurable per run).
- **Control:** Polling only (no interrupts). Software waits for a *done* status bit before reading Y.

These choices keep the RTL and driver simple and integration-safe; performance can be improved in a later version.

## Future v2 ideas (not in scope yet)

- **Preload weights:** Keep W in on-core BRAM and only stream X per inference (reduces CSR traffic for repeated layers).
- **DMA / bus-master:** Let the accelerator read X and W from main memory and write Y back, instead of CSR push/pull.
- **Requantize in hardware:** Add a block that saturates int32 Y to int8 (e.g. shift + clip) so the CPU receives ready-to-use activations.

## Directory layout

```
hw_extensions/gemv/
├── README.md           (this file)
├── gemv_spec.md        Register map, data formats, calling sequence
├── rtl/
│   └── gemv_core.v     RTL core (FSM, internal RAMs, sequential compute)
├── litex/
│   └── gemv_periph.py  LiteX CSR wrapper (pulses for start/clear_done; Y_NEXT for read advance)
└── sw/
    ├── gemv.h          C driver API
    └── gemv.c          C driver implementation (polling; both LiteX CSR and raw MMIO)
```

## CSR summary (see gemv_spec.md for full map)

| Offset | Name    | R/W | Description |
|--------|---------|-----|-------------|
| 0x00   | CTRL    | R/W | start (pulse), clear_done (pulse), len_64, out_dim_64, enable_bias |
| 0x04   | X_IN    | W   | Stream int8 X (LEN writes) |
| 0x08   | W_IN    | W   | Stream int8 W row-major (OUT_DIM×LEN writes) |
| 0x0C   | B_IN    | W   | Stream int32 bias (optional) |
| 0x10   | Y_OUT   | R   | Read current Y[i] (does not advance) |
| 0x14   | STATUS  | R   | busy (bit 0), done (bit 1) |
| 0x18   | Y_NEXT  | W   | Write to advance Y read pointer (pulse) |

**Software sequence:** clear_done pulse → load X → load W → (optional) load B → start pulse (with config) → poll done → for each i: read Y_OUT, write Y_NEXT → clear_done before next run.

## On-target self-test

- **`litex_port/tests_gemv.c`** and **`litex_port/tests_gemv.h`** implement a minimal self-test:
  - Software reference GEMV (int8×int8→int32) with deterministic LCG inputs.
  - Runs HW GEMV for (32×32), (64×32), (32×64), (64×64); compares all Y elements.
  - **`int test_gemv(void);`** returns 0 on PASS, nonzero on FAIL; prints "GEMV self-test PASS" or "FAIL len=... i=... ref=... hw=..." via UART (no printf).
- **How to build:** Compile `tests_gemv.c`, `gemv.c`, and your UART source (e.g. `uart_litex.c`); link with `gemv.h`, `tests_gemv.h`. Define `GEMV_USE_LITEX_CSR` or `GEMV_BASE` as for the driver. From your firmware `main()`, call `gemv_init(base)` (if using MMIO base) then `test_gemv()`; non-zero return = fail.

## Integration status

- **Not yet wired** into any LiteX SoC target. Add `gemv_periph.py` and `rtl/gemv_core.v` to your SoC; link `gemv.c` and optionally `tests_gemv.c` in firmware. Run `test_gemv()` before integrating into TinyFormer.
