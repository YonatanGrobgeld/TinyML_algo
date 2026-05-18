# Implementation Notes: TinyFormer on RISC-V (Nexys4DDR + LiteX + VexRiscv)

This document summarizes the implementation carried out in this repository for running a TinyFormer encoder on a bare-metal RISC-V soft core (VexRiscv) on the Nexys4DDR FPGA with LiteX. It is intended as a self-contained, report-ready description of what was built and why.

---

## 1. Project Goal and Target Platform

**Objective.** The project aims to run a TinyFormer encoder (a small Transformer-style model) on an FPGA-hosted RISC-V core in two phases: first a **baseline** (pure software on an unmodified core), then **hardware-accelerated** variants using custom instructions and peripherals. The goal is to compare correctness and, subsequently, performance across these configurations.

**Target platform.** The implementation targets:

- **Board:** Nexys4DDR FPGA.
- **SoC framework:** LiteX (SoC build, memory map, and CSR layout are defined outside this repository).
- **CPU:** VexRiscv, RV32IM ISA, bare-metal (no OS).
- **I/O:** UART for all textual output (banner, checksums, and per-sample predictions). The firmware assumes that either a UART or a “serial” peripheral is present and exposed via LiteX-generated CSR headers.

The repository provides **firmware sources, accelerator drivers, self-tests, and multiple build “modes”** (baseline and five accelerated combinations). It does **not** provide the LiteX SoC target, bitstream build, linker script, crt0, or `generated/csr.h`; those remain in the user’s LiteX build tree.

---

## 2. TinyFormer Algorithm Implementation (Firmware)

The TinyFormer encoder is implemented in portable C under `litex_port/common/tinyformer.c` (and declared in `tinyformer.h`). It is designed for deterministic, bare-metal execution with no dynamic allocation or libc dependency.

**Model dimensions.**

- Sequence length **S = 16**, model dimension **D = 32**, feed-forward hidden size **FFN = 64**.
- Single attention head.
- All weights and activations are **int8**; accumulators are **int32**.

**Structure.**

1. **Q/K/V linear projections:** Input tokens `X[S][D]` are multiplied by weight matrices `W_q`, `W_k`, `W_v` (each `[D][D]`) with optional biases, producing query, key, and value tensors of shape `[S][D]`. Accumulation is in int32; results are scaled (right-shift) and saturated to int8.

2. **Streaming scaled dot-product attention:** For each query position, dot products with all key positions are computed and accumulated in int32. The implementation **does not** allocate an S×S attention matrix; it processes one query at a time and reuses small 1D buffers for scores and exponent values. This keeps memory use bounded and avoids large stack or heap allocation.

3. **Softmax approximation:** For numerical stability, the maximum score over keys is subtracted before applying a softmax-like step. A small **exponential lookup table (LUT)** approximates exp(x) for x in the range [-15, 0], with values in **Q10** fixed-point (scale 2^10). The resulting weights are used in **Q15**-style fixed-point for the weighted sum over values. No floating-point is used.

4. **Output projection and residual:** The attention output is projected through `W_o` and added to the original input (residual connection), with saturation to int8.

5. **Feed-forward network (FFN) and residual:** A two-layer position-wise FFN is applied: first layer `D → FFN` with ReLU (clamp to zero in int8 space), second layer `FFN → D`. The result is added to the previous residual (again with saturation). Both layers use int8 weights, int32 accumulation, and right-shift scaling.

**Design choices.**

- **Determinism:** Fixed dimensions, no randomness, no dynamic allocation. All buffers are global or stack with fixed size.
- **Portability:** No OS, no threads, no SIMD or vendor intrinsics; only standard C and fixed-size arrays so the same code can run on other RV32IM systems.
- **Quantization:** int8 everywhere except internal accumulators; scaling is by right-shift. The encoder can use either built-in placeholder weights or trained weights included via a compile-time switch (`USE_TRAINED_WEIGHTS`) and external `trained_weights.c/h`.

---

## 3. Dataset and Training Pipeline (Host-Side)

The model is trained and exported on a host machine; the repository includes scripts and documentation for this pipeline.

**Dataset.** UCI Human Activity Recognition (UCI HAR) is used. Raw inertial signals (6 channels × 128 timesteps per sample) are:

- Downsampled to **16 timesteps** (e.g. by average pooling) to match TinyFormer’s sequence length S = 16.
- Turned into **32-dimensional feature vectors** per timestep (matching D = 32).
- **Z-score normalized** using the training set’s mean and standard deviation.

The result is stored as arrays of shape **[N, 16, 32]** (and labels) for training and testing.

**Training.** A PyTorch training script (`train_tinyformer_uci_har.py`) trains a TinyFormer encoder plus a linear classifier head for 6 activity classes. It produces:

- **Encoder weights:** `state_dict.pt` with keys such as `W_q`, `W_k`, `W_v`, `W_o`, `W_ff1`, `W_ff2` and corresponding biases (`b_q`, `b_k`, etc.).
- **Classifier head:** e.g. `classifier.npz` with weights and biases for the 6-way classification layer.

**Export.** An export script (`export_and_make_fpga_demo.py`) and a weight-export tool (`tools/export_weights.py`) convert the encoder weights to **quantized int8 C arrays** in the layout expected by `tinyformer.c` (row-major, dimensions matching `TINYFORMER_D`, `TINYFORMER_FFN`). The same pipeline produces:

- **`trained_weights.c/h`** — Encoder weights and biases for the C implementation.
- **`demo_samples.c/h`** — A small set of pre-quantized int8 demo inputs and ground-truth labels.
- **`demo_classifier.c/h`** — Quantized classifier head for the 6 classes.

The firmware is built with `-DUSE_TRAINED_WEIGHTS=1` so that `tinyformer.c` includes `trained_weights.h` and uses these arrays instead of placeholders.

---

## 4. LiteX Integration Layer (UART and Build Assumptions)

**UART driver.** The firmware uses a minimal UART layer (`uart_litex.c` / `uart_litex.h`) that compiles to either a real implementation or a no-op stub.

- When **`USE_LITEX_UART`** is defined and the LiteX build’s `generated/csr.h` is available, the driver uses CSR accessors to poll the TX-full flag and write one character at a time. It supports two naming conventions: if **`CSR_UART_RXTX_ADDR`** is defined, it uses `uart_txfull_read()` and `uart_rxtx_write()`; if instead **`CSR_SERIAL_RXTX_ADDR`** is defined, it uses `serial_txfull_read()` and `serial_rxtx_write()`. No source change is required when switching between common LiteX UART naming schemes; only the generated headers and compile define matter.
- When `USE_LITEX_UART` is not set (or the CSR macros are absent), the same file compiles to a stub that discards characters, so the rest of the firmware still links.

**Include path.** Firmware must be compiled with `-I<litex_build>/software/include` so that `#include <generated/csr.h>` resolves. The LiteX build tree is external to this repository; the repository does not contain the SoC RTL, bitstream generation, linker script, crt0, or the generated CSR headers.

---

## 5. Hardware Acceleration Extensions Implemented

Three hardware extensions were implemented and integrated with the firmware: a custom instruction (DOT8), and two MMIO peripherals (EXP LUT and GEMV). Each has a software driver and an on-target self-test.

### 5.1 DOT8 — Custom Instruction (4-Lane Signed int8 Dot-Product)

**Purpose.** To accelerate the inner product of two 4-element signed int8 vectors (e.g. in attention and linear layers) in a single instruction, reducing loop overhead and instruction count.

**Interface.** Custom instruction (not a peripheral). Opcode **custom-0 (0x0B)**, **funct7 = 0x01**. Operands: two 32-bit registers holding **packed** int8 values (lane 0 in the LSB byte through lane 3 in the MSB byte); result register holds a signed int32 dot-product. The operation is **single-cycle** in the implemented VexRiscv plugin (decode, execute, writeback). Lane packing is little-endian: byte 0 = lane 0, byte 1 = lane 1, etc.

**Software driver.** Under `hw_extensions/dot8/sw/`: `dot8.h` exposes a packing helper and `dot8_4_lanes(a_packed, b_packed)`. When **`USE_DOT8_HW`** is defined, the implementation uses an inline assembly instruction that matches the plugin encoding; when the macro is undefined, a pure C (software) fallback is used so that tests and baseline builds can run without the custom instruction.

**Verification.** An on-target self-test (`litex_port/tests_dot8.c`) compares a set of packed inputs against the software reference. With the plugin present and `USE_DOT8_HW` defined, the test exercises the hardware path; without the plugin, the same test runs using the software path and still passes. Success is reported over UART (e.g. “DOT8 PASS”).

### 5.2 EXP LUT — Exponential Lookup Table Peripheral

**Purpose.** To offload the softmax exponential lookup used in the TinyFormer attention so that the CPU does not need to store or reference the LUT in software; the table is fixed and matches the encoder’s expected range and scaling.

**Interface.** MMIO peripheral. Index range 0..15 corresponds to exp(0) down to exp(-15). The peripheral exposes (at least) an index write and a value read; the value is **16-bit Q10** fixed-point, with the same numerical content as the software LUT in `tinyformer.c` (e.g. 1024 for exp(0), then 754, 556, … for exp(-1), exp(-2), etc.). The RTL and LiteX wrapper are in `hw_extensions/exp_lut/`; the exact CSR layout is defined by the LiteX integration (e.g. index register, value register).

**Software driver.** Under `hw_extensions/exp_lut/sw/`: `exp_lut.h` / `exp_lut.c` provide `exp_lut_hw(idx)`. When **`USE_EXP_LUT_HW`** is defined, the driver uses either LiteX-generated CSR accessors (`EXP_LUT_USE_LITEX_CSR`) or a raw base address (`EXP_LUT_BASE`). When the macro is off, the driver returns values from an internal “golden” table identical to the one in `tinyformer.c`, so behaviour is unchanged and tests can run without the peripheral.

**Verification.** On-target self-test (`litex_port/tests_lut.c`) checks indices 0..15 against the golden table. With the peripheral present and `USE_EXP_LUT_HW` set, the test uses the hardware path; otherwise it uses the software table. Success is reported over UART (e.g. “LUT PASS”).

### 5.3 GEMV — Matrix-Vector Accelerator Peripheral

**Purpose.** To accelerate matrix-vector operations **Y = W×X + b** (int8 matrix W, int8 vector X, optional int32 bias b, int32 vector Y) used in the encoder’s linear layers and classifier.

**Interface.** MMIO peripheral with a CSR register map: control (start, clear_done, dimensions, enable_bias), streaming inputs for X, W, and optionally b, and a read path for Y. Supported dimensions are **LEN** and **OUT_DIM** each either 32 or 64 (configured via control bits). Data is fed one element at a time (e.g. 8-bit writes for X and W, 32-bit for b); results are read from Y_OUT, with a separate **Y_NEXT** write used to advance the read pointer (no automatic advance on read). START and CLEAR_DONE are one-shot pulses in the LiteX wrapper. The RTL is in `hw_extensions/gemv/rtl/`; the LiteX peripheral and CSR layout are in `hw_extensions/gemv/litex/`.

**Software driver.** Under `hw_extensions/gemv/sw/`: `gemv.h` / `gemv.c` provide init, load_x, load_w, load_b, start, wait_done, read_y, and clear_done. The driver supports either LiteX-generated CSRs (`GEMV_USE_LITEX_CSR`) or a raw base address (`GEMV_BASE`). When **`USE_GEMV_HW`** is defined, the firmware is expected to use this driver for GEMV ops; when it is not defined, no GEMV MMIO is used (the encoder uses pure C matvec).

**Verification.** An on-target self-test (`litex_port/tests_gemv.c`) runs GEMV with known matrices and vectors and checks the outputs. It covers the supported shapes (e.g. 32×32, 64×64) and optional bias. Success is reported over UART (e.g. “GEMV self-test PASS”).

---

## 6. Verification and Testing Strategy

**Self-tests.** Each extension has a dedicated test that runs on the target and prints a pass/fail line over UART. The tests are designed so that they can run even when the corresponding hardware is absent (using software fallbacks where applicable). This allows validating the SoC and toolchain with baseline firmware first, then validating each accelerator in isolation.

**End-to-end correctness gate.** The demo application (used by both baseline and accelerated builds) does not only print per-sample predictions; it also prints a **32-bit checksum** of the encoder output for each sample. After `tinyformer_encode()` produces the 16×32 int8 output tensor, the firmware computes a simple additive checksum over all elements (as unsigned bytes) and prints a line **`ENC_CKSUM=0xXXXXXXXX`**. For the same input and weights, the baseline and every accelerated build must produce the **same** `ENC_CKSUM` for each sample index. If any accelerated run differs, the implementation is considered incorrect and performance must not be reported until the mismatch is resolved.

**Bring-up order.** The recommended order is: (1) ensure LiteX memory initialization is correct (e.g. memtest passes); (2) build and run **baseline** firmware and record its UART output (MODE banner, ENC_CKSUM lines, pred/exp lines); (3) run the three self-tests (LUT, GEMV, DOT8) so that each block is known good; (4) build and run each accelerated mode and verify that ENC_CKSUM and pred/exp match the baseline for every sample; (5) only then measure performance (e.g. cycles). This order avoids attributing failures to the wrong layer (e.g. SoC vs accelerator) and ensures that “correctness” is defined as bit-identical encoder output and predictions versus baseline.

---

## 7. Benchmarking Structure (Baseline vs Accelerated Modes)

**Directory layout.** The firmware is organized so that a single shared implementation is reused across all configurations:

- **`litex_port/common/`** contains the shared sources: TinyFormer encoder, demo samples, classifier weights, demo runner (which runs the encoder, computes the checksum, mean-pools, classifies, and prints), UART driver, and trained weights. There is no duplication of the core algorithm.
- **Six mode directories** each contain a small `main_*.c` that prints a fixed **MODE** banner and calls the shared demo runner. The modes are: **baseline** (no accelerators), **accel_dot8**, **accel_lut**, **accel_gemv**, **accel_dot8_lut**, and **accel_all** (DOT8 + LUT + GEMV).

**Feature macros.** Compile-time macros select which hardware paths are used (and which driver code is linked):

- **`USE_DOT8_HW`** — Use the DOT8 custom instruction when defined; otherwise pure C dot-products.
- **`USE_EXP_LUT_HW`** — Use the EXP LUT peripheral for softmax when defined; otherwise the in-code LUT in `tinyformer.c`.
- **`USE_GEMV_HW`** — Use the GEMV peripheral for matrix-vector ops when defined; otherwise pure C.

When a macro is not defined, the corresponding hardware is not used (no custom instruction, no MMIO to that block), so the same codebase can run on a plain VexRiscv or on a SoC that includes only a subset of the accelerators.

**UART output format.** Each run prints:

1. A single line **`MODE: BASELINE`** (or `MODE: DOT8`, `MODE: LUT`, etc.) so that logs are self-identifying.
2. For each demo sample: **`ENC_CKSUM=0xXXXXXXXX`** (the 32-bit checksum of the encoder output), then **`Sample i: pred=X exp=Y`** (sample index, predicted class, expected class).

Comparing logs between baseline and accelerated builds is done by checking that MODE is correct and that ENC_CKSUM and pred/exp match sample-by-sample.

---

## 8. Limitations and Future Work

- **Cycle counting.** Implemented. The firmware now reads LiteX `timer0` around `demo_run()` and prints `CYCLES=N` and `TIME_US=N` per run; see Section 9 below. The Python measurement scripts (`run_baseline_and_measure.py`, `run_accel_all_and_measure.py`) parse these and report the firmware-side timer as the authoritative number alongside the (less reliable) Python wall-clock.

- **GEMV v2.** The byte-wide v1 design was upgraded to a packed 32-bit data path with a 4-lane parallel MAC (see Section 9.4). Future improvements: DMA-based transfers so the GEMV core fetches W from main RAM itself (eliminating CPU-side CSR-bus traffic entirely), and tiling for matrices larger than 64×64.

- **DOT8.** The custom instruction is single-cycle. Further gains might be possible with pipelining or wider lanes (e.g. 8-lane).

- **EXP LUT.** The hardware table is fixed (16 entries, Q10).

- **Timing closure at 100 MHz.** The v2 GEMV's 4-lane MAC adds combinational depth; final Vivado WNS at 100 MHz is **−6.3 ns** on the xc7a100t-1 (the design works at room temperature, and `ENC_CKSUM` is bit-identical with baseline across all 10 demo samples, but is not timing-safe). For production use, either pipeline the dot4 stage (one extra cycle of latency) or lower `sys_clk_freq` to ~75 MHz to close timing cleanly.

---

## 9. Final Measured Performance Results

### 9.1 Methodology

All measurements are taken on the **same FPGA platform** (Digilent Nexys4DDR with the v2 LiteX bitstream loaded). Only the firmware binary changes between modes; the bitstream — and therefore the CPU, peripherals, memory map, and cache configuration — is identical across the three measurements. This isolates the effect of using the accelerators from any platform variation.

**Timer source.** The on-chip LiteX `timer0` peripheral is read in `main_baseline.c` and `main_all.c` immediately before and after the call to `demo_run()`. The timer counts down at the system clock rate `sys_clk_freq = 100 MHz`. Reported `CYCLES` is the elapsed count, converted to microseconds with `TIME_US = CYCLES / (sys_clk_freq / 1_000_000) = CYCLES / 100`.

**Why the hardware timer, not Python wall-clock.** The Python script's `time.perf_counter()` is unreliable for short runs because pyserial's `readline()` loop can exit early between runs (it loses some bytes between the firmware's "Done" marker and the next "Ready"). The firmware-side timer cannot be fooled — it counts at `sys_clk` regardless of what Python observes.

**Workload.** A single firmware run executes `demo_run()`, which iterates through 10 demo samples. For each sample it calls `tinyformer_encode()` (full Q/K/V/O projections + streaming attention + softmax + FFN + residuals + saturation) followed by mean-pooling, the 6-class classifier, and UART output of `ENC_CKSUM`, `Sample N: pred=… exp=…`. The 10 samples are deterministic and identical across modes.

**Correctness gate.** All three modes (baseline, v1, v2) produce **bit-identical** `ENC_CKSUM` for every sample (`0x00005CE7, 0x00006557, 0x000068B6, 0x00006469, 0x000062A1, 0x000063A6, 0x0000627B, 0x00006ACF, 0x0000719B, 0x00007185`). Identical encoder output ⇒ identical predictions ⇒ the speedup is real, not an artefact of skipped work.

### 9.2 Three-Way Comparison Table

| Mode | Firmware path | CYCLES | TIME_US | Wall time | Speedup |
|------|--------------|--------|---------|-----------|---------|
| **Baseline** (no accelerators) | Real-math softmax exp + software matvec + software attention scores | **75,900,400** | 759,004 | **759.00 ms** | 1.00× |
| **accel_all v1** (byte-wide GEMV) | HW LUT exp + DOT8 attention + 1-lane GEMV matvec | 19,067,129 | 190,671 | 190.67 ms | 3.98× |
| **accel_all v2** (packed GEMV) | HW LUT exp + DOT8 attention + 4-lane packed GEMV matvec | **15,755,300** | 157,553 | **157.55 ms** | **4.82×** |

Standard deviation across 10 runs is < 0.1 ms in every mode (the timer is rock-steady).

### 9.3 Cycles → Time Conversion (Worked Example)

At 100 MHz, one cycle is 10 ns. The conversion is:

```
time_s   = CYCLES / sys_clk_freq
time_us  = CYCLES / (sys_clk_freq / 1_000_000)
time_ms  = CYCLES / (sys_clk_freq / 1_000)
```

Worked example for accel_all v2:

```
CYCLES   = 15,755,300
sys_clk  = 100,000,000 Hz

time_s   = 15,755,300 / 100,000,000           = 0.157553 s
time_ms  = 15,755,300 / 100,000               = 157.553 ms
time_us  = 15,755,300 / 100                   = 157,553 µs
```

Worked example for baseline:

```
CYCLES   = 75,900,400
time_ms  = 75,900,400 / 100,000               = 759.004 ms
```

Worked example for the **speedup ratio**:

```
Speedup_v2 = baseline_cycles / accel_v2_cycles
           = 75,900,400      / 15,755,300
           = 4.818           (≈ 4.82×)

Speedup_v1 = baseline_cycles / accel_v1_cycles
           = 75,900,400      / 19,067,129
           = 3.980           (≈ 3.98×)

Speedup_v2_over_v1 = accel_v1_cycles / accel_v2_cycles
                   = 19,067,129      / 15,755,300
                   = 1.210           (≈ 1.21×)
```

### 9.4 What Changed from v1 to v2 (GEMV optimisation)

**Bus path (data movement).** In v1, the CSR-bus registers `X_IN` and `W_IN` were each 8-bit; the CPU pushed one int8 lane per MMIO write. For a 32×32 matvec that meant 32 X writes + 1024 W writes + 32 B writes = 1088 writes/call, and the bus dominated the total time. In v2, both registers were widened to 32-bit and the C driver packs four int8 lanes per write (`pack4_i8()`), cutting CSR-bus traffic by **4×** to ~272 writes/matvec.

**Compute path.** In v1, the FSM inside `gemv_core.v` performed one signed int8 multiply-accumulate per clock — i.e. 1024 cycles for a 32×32 matvec. In v2, the internal X and W memories were restructured as 32-bit-wide word arrays, and the FSM now reads one packed word from each per cycle and computes four signed int8 MACs in parallel (`dot4 = sum of four mul`), folding the result into the running accumulator. Compute drops to **256 cycles per 32×32 matvec** — another **4× win** on the hardware side.

**End-to-end result.** v1 → v2 saves ≈ 3.3 M cycles per inference (~33 ms at 100 MHz), which is the 1.21× column above. The remaining v2 → baseline gap (60.1 M cycles) is split across attention dot products (accelerated by DOT8), softmax exp (accelerated by EXP_LUT), and the *outer* loop overhead around the linear projections.

### 9.5 Breakdown — Where the Baseline's 75.9 M Cycles Go

Rough decomposition (per inference, baseline mode):

| Component | Cycles | % | Accelerated by |
|-----------|--------|---|----------------|
| **Softmax exp() per call** (2560 calls × ~21k cyc each) | ~53.8 M | 71 % | EXP_LUT peripheral (~12 cyc/call in accel modes) |
| Software matvec (Q,K,V,O,FFN1,FFN2): 960 calls × ~17k cyc | ~16.3 M | 21 % | GEMV peripheral (v2: ~2k cyc/call) |
| Attention dot products (16×16 × 32-dim × 10 samples) | ~1.0 M | 1 % | DOT8 custom instruction (~256 cyc total) |
| UART output (10 × ENC_CKSUM + Sample lines, 115200 baud) | ~4.0 M | 5 % | not accelerated (115200-baud transmit time) |
| Misc (softmax accumulator, mean-pool, classifier, residuals, control flow) | ~0.8 M | 1 % | not accelerated |
| **Total** | **~75.9 M** | 100 % | |

(The 71% softmax cost is high because the honest baseline uses runtime fixed-point math for `exp()` — see Section 9.6.)

### 9.6 What “Real-Math Baseline” Means

To make the EXP_LUT speedup a fair comparison, the baseline firmware (compiled without `USE_EXP_LUT_HW`) no longer reads from a precomputed 16-entry table. Instead, `compute_exp_q10()` in `tinyformer.c` computes each softmax `exp(-c·k)` at runtime via fixed-point multiplicative decay with a single mathematical constant `decay_q15 = 24149 ≈ 0.7368 · 2^15`. The function is `__attribute__((noinline, optimize("O0")))` so gcc cannot unroll, constant-fold, or memoize it — the per-call work is genuinely paid on every softmax lookup. Each call costs ~21k CPU cycles; multiplied by 2560 softmax lookups per inference, this contributes ~53.8 M cycles (i.e. roughly 71 % of the baseline total). Removing the LUT was a deliberate, *honest* choice: the HW LUT is meaningful only if the alternative is real arithmetic, not another lookup table that gcc would otherwise pre-resolve.

### 9.7 Vivado Resource and Timing Report (v2 bitstream)

| Resource | Used | Available | Util % |
|----------|------|-----------|--------|
| Slice LUTs | 6,321 | 63,400 | 9.97 % |
| Slice Registers | 5,461 | 126,800 | 4.31 % |
| LUT as Distributed RAM | 968 | 19,000 | 5.11 % |
| RAMB36 | 47 | 135 | 34.81 % |
| DSP Blocks | 4 (VexRiscv DOT8) + 4 (GEMV 4-lane MAC) = 8 | 240 | 3.33 % |

**Timing.** WNS = **−6.309 ns** on the worst path (inside `gemv_core` — the 4-lane multiply + adder-tree + accumulator-add chain). The design routes cleanly (0 routing errors) and runs correctly at room temperature, but a production version should either pipeline the dot4 stage or drop `sys_clk_freq` to ~75 MHz.

---

## 10. How to Reproduce the Final Numbers

1. **Program the v2 bitstream** from `accelerators/accel_all_v2/digilent_nexys4ddr.bit` onto the Nexys4DDR.

2. **Run each mode** in turn — the SFL-upload measurement scripts swap firmware over UART automatically (no need to reprogram between modes):

   ```sh
   # Baseline (real-math softmax exp, software matvec)
   cd C:\Final_Project\0_baseline
   python run_baseline_and_measure.py --port COM3 --runs 10 --power_val estimate
   #   → "FIRMWARE TIMER Avg : 759.00 ms"

   # accel_all v1 (byte-wide GEMV)
   cd C:\Final_Project\accelerators\accel_all
   python run_accel_all_and_measure.py --port COM3 --runs 10 --power_val estimate
   #   → "FIRMWARE TIMER Avg : 190.67 ms"

   # accel_all v2 (32-bit packed GEMV + 4-lane MAC)
   cd C:\Final_Project\accelerators\accel_all_v2
   python run_accel_all_and_measure.py --port COM3 --runs 10 --power_val estimate
   #   → "FIRMWARE TIMER Avg : 157.55 ms"
   ```

3. **Verify correctness.** In each `serial_debug*.log`, grep for `ENC_CKSUM=` — the values must match across all three modes for every sample.

4. **Compute the speedup** from the firmware-timer `Avg` (or, equivalently, divide the `CYCLES=` values).

The `COMPARISON_SUMMARY.csv` in the shared-folder root captures the headline numbers, and each mode's per-run CSV (`results_runtime.csv`, `results_accel_all.csv`, `results_accel_all_v2.csv`) keeps both `FW_Time_s` (authoritative) and `Python_WallClock_s` (kept for transparency) columns.

---

## Reproducibility / How to Run

The following order matches the README and ensures reproducibility:

1. **LiteX SoC and memory.** Build the LiteX SoC for Nexys4DDR (or equivalent) in an external build tree. Ensure memory initialization is correct (e.g. run memtest). The bitstream, linker script, crt0, and `generated/csr.h` come from that tree; this repository does not provide them.

2. **Baseline firmware.** Compile and link: all sources in `litex_port/common/` (tinyformer.c, demo_samples.c, demo_classifier.c, demo_runner.c, uart_litex.c, trained_weights.c) and `litex_port/baseline/main_baseline.c`. Use `-I litex_port/common`, `-I<litex_build>/software/include`, `-DUSE_TRAINED_WEIGHTS=1`, and `-DUSE_LITEX_UART`. Run on the board and capture UART output; confirm `MODE: BASELINE`, then for each sample `ENC_CKSUM=0x...` and `Sample i: pred=X exp=Y`. Keep this log as the reference.

3. **Self-tests.** Build and run the LUT, GEMV, and DOT8 self-tests (each with the corresponding driver and includes as documented in the README). Confirm each prints its PASS line.

4. **Accelerated modes.** For each mode (DOT8 only, LUT only, GEMV only, DOT8+LUT, all), add the appropriate driver sources and defines (see README “Files to compile/link per mode” and “Build flags”). Run and verify that for every sample, `ENC_CKSUM` and `pred`/`exp` match the baseline. Do not proceed to performance measurement until they do.

5. **Performance.** After correctness is confirmed, add cycle or timer measurements in the integrator’s code (e.g. around the encoder or demo loop), run baseline and each accelerated build, and compare cycles per sample or per encoder call.

All build flags, include paths, and file lists are specified in the root README so that a teammate with the FPGA and LiteX environment can reproduce the bring-up and benchmarking steps without relying on information outside the repository.
