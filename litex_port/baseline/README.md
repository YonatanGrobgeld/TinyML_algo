# Baseline — no hardware accelerators (honest software reference)

Runs TinyFormer entirely on the CPU (no custom instructions, no accelerator peripherals). This is the **reference point for both correctness and performance** in the three-way comparison.

- **Macros:** none of `USE_DOT8_HW`, `USE_EXP_LUT_HW`, `USE_GEMV_HW` are defined.
- **SoC:** Plain VexRiscv + LiteX timer/UART; the bitstream **may** still include the accelerator peripherals (e.g. the v2 SoC), but this firmware never touches them.
- **Banner:** `MODE: BASELINE`

## "No LUT" baseline (important for the EXP comparison)

The softmax `exp()` in `tinyformer.c` no longer reads from a precomputed 16-entry table when `USE_EXP_LUT_HW` is undefined. Instead, `compute_exp_q10()` computes each value at runtime via fixed-point multiplicative decay against a single mathematical constant `decay_q15 ≈ 0.7368 · 2^15`. The function is `__attribute__((noinline, optimize("O0")))` so gcc cannot unroll or constant-fold the loop. This is what makes the EXP_LUT peripheral a fair comparison: the baseline alternative is **real arithmetic**, not a software LUT that gcc would otherwise pre-resolve.

Each `compute_exp_q10` call costs ~21 K CPU cycles; multiplied by 2 560 softmax lookups per inference, this contributes ~53.8 M cycles to baseline runtime (about 71 % of the total).

## Final measured baseline

On the v2 bitstream (Nexys4DDR @ 100 MHz, 10 runs averaged):

- **CYCLES = 75,900,400**
- **TIME_US = 759,004**
- **wall = 759.00 ms** (firmware-side timer, authoritative)
- `ENC_CKSUM` per sample is bit-identical with the accelerated builds.

Reference for the speedup ratios: accel_all v2 finishes the same workload in 15,755,300 cycles (157.55 ms) → **4.82×** faster. See [REPORT_NOTES_IMPLEMENTATION.md §9](../../REPORT_NOTES_IMPLEMENTATION.md) for cycle math and per-component breakdown.

## Build

```sh
make TARGET=baseline
```

Defines applied: `-DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART` only (no accelerator macros, no extra includes).

## Run on the board

```
cd C:\Final_Project\0_baseline
python run_baseline_and_measure.py --port COM3 --runs 10 --power_val estimate
```

The script auto-uploads `firmware.bin` to the FPGA via SFL — no separate `litex_term` step. It then sends `s` ten times and prints the firmware-side `CYCLES`-based summary. Use the `FIRMWARE TIMER Avg` line as the authoritative measurement (the Python wall-clock column loses bytes between runs and underestimates).
