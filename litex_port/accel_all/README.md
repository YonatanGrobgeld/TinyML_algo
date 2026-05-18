# All — DOT8 + LUT + GEMV (v2)

TinyFormer build with **all** accelerators enabled: DOT8 custom instruction, EXP LUT MMIO peripheral, and GEMV v2 (32-bit packed, 4-lane MAC).

- **Macros:** `USE_DOT8_HW`, `USE_EXP_LUT_HW`, `USE_GEMV_HW`, `EXP_LUT_USE_LITEX_CSR`, `GEMV_USE_LITEX_CSR`
- **SoC:** VexRiscv with Dot8Plugin + LiteX `exp_lut` and v2 `gemv` peripherals (32-bit X_IN/W_IN).
- **Banner:** `MODE: DOT8 + LUT + GEMV`

## Final measured performance

On the v2 bitstream (Nexys4DDR @ 100 MHz):

| Mode | CYCLES | Time | Speedup vs Baseline |
|---|---|---|---|
| Baseline (real-math softmax, software matvec) | 75,900,400 | 759.00 ms | 1.00× |
| accel_all v1 (byte-wide GEMV) | 19,067,129 | 190.67 ms | 3.98× |
| **accel_all v2** (this build) | **15,755,300** | **157.55 ms** | **4.82×** |

`ENC_CKSUM` bit-identical across all modes. Per-component breakdown and cycle math in [REPORT_NOTES_IMPLEMENTATION.md §9](../../REPORT_NOTES_IMPLEMENTATION.md).

## Build

```sh
make TARGET=accel_all
```

Defines applied (see top-level `Makefile`): `-DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART -DUSE_DOT8_HW -DUSE_EXP_LUT_HW -DUSE_GEMV_HW -DEXP_LUT_USE_LITEX_CSR -DGEMV_USE_LITEX_CSR`.

Links: `../hw_extensions/dot8/sw/dot8.c`, `../hw_extensions/exp_lut/sw/exp_lut.c`, `../hw_extensions/gemv/sw/gemv.c` (v2 packing driver).

## Run on the board

The measurement script auto-uploads firmware via SFL — no separate litex_term step needed:

```
cd C:\Final_Project\accelerators\accel_all_v2
python run_accel_all_and_measure.py --port COM3 --runs 10 --power_val estimate
```

Look for the `FIRMWARE TIMER Avg` line in the summary — that's the authoritative number.
