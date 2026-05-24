# TinyFormer: Hardware-Accelerated Transformer Inference on FPGA

**Project Number:** [XX-X-X-XXXX]

**Students:**
- Yehonatan Grobgeld | ID: [ID]
- Ron Weinstein | ID: [ID]

**Supervisor:** Oren Ganon

**Project Carried Out at:** Faculty of Engineering, Tel Aviv University

---

## Abstract

This project implements and accelerates a compact Transformer encoder — TinyFormer — on an FPGA-hosted RISC-V soft-core. The target platform is a Digilent Nexys4DDR board running a LiteX-generated SoC with a VexRiscv RV32IM CPU at 100 MHz. The model performs 6-class human activity recognition using the UCI HAR dataset, with all weights and activations quantized to int8.

A pure-software baseline requires 75.9 million cycles (759 ms) per inference. Profiling reveals that 71% of cycles are consumed by softmax exponentials and 21% by matrix-vector multiplications. Three hardware accelerators were designed and integrated to attack these bottlenecks: (1) a DOT8 custom VexRiscv instruction for 4-lane int8 dot-products, (2) an EXP-LUT MMIO peripheral replacing the softmax exponential, and (3) a GEMV MMIO peripheral with a 4-lane parallel MAC for matrix-vector operations.

The final accelerated system achieves a **4.82× end-to-end speedup** (157.55 ms), measured on the same FPGA bitstream with the same trained model and C source. Encoder outputs are bit-identical across baseline and all accelerated modes, verified by a 32-bit checksum on every inference. Total LUT utilization is 9.97%, leaving approximately 90% of the FPGA fabric available for future extensions. The power cost is modest at 1.07× the baseline.

---

## 1. Introduction

### 1.1 Goals

The goals of this project are:

1. Implement a complete, bare-metal Transformer encoder (TinyFormer) in firmware on a VexRiscv RISC-V soft-core running inside a LiteX SoC on an FPGA.
2. Identify and quantify the computational bottlenecks of the pure-software inference path.
3. Design three hardware accelerators — a custom CPU instruction and two MMIO peripherals — that target the dominant bottlenecks.
4. Measure the end-to-end speedup while maintaining bit-exact correctness with respect to the baseline.
5. Remain within a less than 10% LUT utilization footprint on the target FPGA.

### 1.2 Motivation

Transformer-based models have become the dominant architecture for sequence modeling tasks, including natural language processing, audio classification, and sensor-based activity recognition. However, deploying even small Transformer variants on embedded, battery-powered devices is challenging. The bottlenecks are predictable: matrix-vector multiplications (GEMV) in the linear projection layers, and the softmax exponential function in the attention mechanism.

A soft-core RISC-V CPU running at 100 MHz on an FPGA offers a flexible, reconfigurable compute substrate. However, in its unmodified form it cannot match the throughput demands of always-on inference. This project demonstrates that targeted hardware acceleration — implemented with minimal FPGA area overhead — can close this gap substantially.

### 1.3 Approach

The project follows a systematic methodology: (1) establish a correct, measured baseline; (2) profile to identify true cycle sinks; (3) design accelerators targeting those sinks; (4) verify bit-exact correctness before reporting performance; (5) measure speedup on hardware. This order ensures that reported numbers reflect genuine acceleration rather than artifacts of skipped work or incorrect computation.

### 1.4 Comparison with Related Work

Al-Qawlaq et al. [1] present KWT-Tiny, a RISC-V accelerated keyword spotting Transformer targeting a custom chip with 64 kB RAM. They achieve a 5× speedup through custom instructions for GELU and softmax, with a 29% area overhead. Their approach requires aggressive model compression (369× size reduction) and accepts a 10% accuracy loss due to class reduction. In contrast, this work targets an FPGA platform — offering full bitstream transparency and reproducibility — preserves full bit-exact correctness, and achieves a 4.82× speedup with only a 9.97% LUT footprint, leaving 90% of the fabric free. The two works attack the same fundamental bottlenecks — softmax and attention on embedded RISC-V — and arrive at comparable speedups through different design trade-offs.

---

## 2. Theoretical Background

### 2.1 Transformer Encoder Architecture

The Transformer encoder [2] processes an input sequence of token vectors through a self-attention mechanism followed by a feed-forward network (FFN), with residual connections around each sub-layer.

Given an input matrix X of shape (S × D) — sequence length S, model dimension D — the encoder computes:

1. **Linear projections:** Query, Key, and Value matrices are computed as Q = XW_q, K = XW_k, V = XW_v, where W_q, W_k, W_v are D×D weight matrices.
2. **Scaled dot-product attention:** Attention scores are A = softmax(QK^T / sqrt(D)), then the context is C = AV.
3. **Output projection:** The context is projected back through W_o: Out = CW_o.
4. **Residual and FFN:** The residual Y = X + Out is passed through a two-layer feed-forward network: Z = Y + FFN(Y), where FFN applies two linear layers with a ReLU activation in between.

TinyFormer uses S=16, D=32, FFN hidden size=64, and a single attention head.

### 2.2 Integer Quantization

All weights and activations in TinyFormer are quantized to int8 (8-bit signed integers). Accumulators are promoted to int32 to prevent overflow during multiply-accumulate operations. Results are scaled back to int8 using fixed right-shift operations. This approach eliminates all floating-point operations from the inference path, which is essential for efficient FPGA and RISC-V implementation.

The softmax function requires exponentiation, which is approximated by a 16-entry lookup table covering exp(0) through exp(-15), stored in Q10 fixed-point format (values scaled by 2^10). The softmax denominator is accumulated in 32-bit fixed-point.

### 2.3 LiteX SoC Framework

LiteX [3] is an open-source FPGA SoC builder that generates a complete system — including CPU instantiation, memory controllers, bus fabric, and peripheral CSR (Control and Status Register) maps — from Python descriptions. In this project, LiteX generates the VexRiscv RV32IM soft-core, connects it to DDR2 SDRAM, exposes a UART peripheral, and provides the infrastructure into which the three custom accelerators are integrated as memory-mapped peripherals.

The generated CSR headers (`generated/csr.h`) expose each peripheral's registers as typed C accessors, allowing the firmware to interact with hardware peripherals using standard C without hand-crafted MMIO pointer arithmetic.

### 2.4 VexRiscv and Custom Instructions

VexRiscv [4] is a flexible, plugin-based RISC-V CPU written in SpinalHDL, commonly used as a soft-core inside LiteX SoCs. Its plugin architecture allows new functional units to be added at the decode, execute, and writeback stages without modifying the core pipeline. The RISC-V ISA reserves the custom-0 through custom-3 opcodes for non-standard extensions, allowing user-defined instructions that are decoded and executed within the core. This project uses custom-0 (opcode 0x0B) with funct7=0x01 for the DOT8 instruction.

### 2.5 MMIO Peripheral Design

Memory-mapped I/O (MMIO) peripherals appear to the CPU as ordinary memory addresses. The CPU writes to control registers and reads from status and data registers using standard load and store instructions. In LiteX, peripherals are described as Python modules that generate both the RTL logic and the C header definitions. This project implements two MMIO peripherals: EXP-LUT (a lookup table for the softmax exponential) and GEMV (a matrix-vector accelerator).

---

## 3. Simulation

### 3.1 Python Training and Validation Pipeline

Before any FPGA implementation, the TinyFormer model was trained and validated on a host machine using PyTorch. This serves as the algorithmic reference for the entire project.

**Dataset preparation.** The UCI Human Activity Recognition (UCI HAR) dataset [5] contains inertial sensor recordings (accelerometer and gyroscope) from 30 subjects performing 6 activities: walking, walking upstairs, walking downstairs, sitting, standing, and laying. Raw signals consist of 6 channels at 128 timesteps per sample. The preprocessing pipeline downsamples each signal to 16 timesteps by average pooling (matching TinyFormer's S=16), concatenates channels to form 32-dimensional feature vectors per timestep (matching D=32), and applies z-score normalization using training set statistics. The resulting dataset has shape (N, 16, 32) with integer class labels 0–5.

**Training.** A TinyFormer encoder (S=16, D=32, FFN=64, 1 head) plus a linear classifier head (D=32 to 6 classes) is trained in PyTorch using cross-entropy loss and the Adam optimizer. The training script produces:
- `artifacts/state_dict.pt` — encoder weights (W_q, W_k, W_v, W_o, W_ff1, W_ff2 and corresponding biases).
- `artifacts/classifier.npz` — classifier head weights and biases.

**Weight export.** A dedicated export script (`tools/export_weights.py`) quantizes the floating-point weights to int8 using symmetric per-tensor scaling and generates C source files (`trained_weights.c/h`, `demo_samples.c/h`, `demo_classifier.c/h`) in the format expected by the firmware. A fixed set of 10 test samples with ground-truth labels is embedded for on-device validation.

**Software reference.** The Python pipeline also serves as the numerical reference. The int8 C implementation in `tinyformer.c` is validated against Python-computed encoder outputs to confirm that quantization error is within the expected range before the firmware is run on hardware.

### 3.2 RTL Simulation (Vivado xsim)

Both hardware peripherals were verified in standalone SystemVerilog simulation using Vivado 2025.2's xsim simulator before integration into the LiteX SoC.

**GEMV testbench (`tb_gemv.sv`).** The testbench exercises the `gemv_core.v` module with three test scenarios:

- **Deterministic test:** A fixed 32×32 matrix and vector with known expected output are loaded, the START pulse is issued, and Y output values are compared against a golden reference after the DONE signal asserts.
- **Randomized test:** An LCG-based deterministic random generator produces a different matrix and vector pair at each run; results are cross-checked against a software model computed inside the testbench.
- **Boundary test:** All elements set to INT8_MIN (−128) and INT8_MAX (+127) to verify correct saturation and sign handling in the 32-bit accumulator.

All mismatches trigger `$fatal`; a PASS message is printed on successful completion.

**LUT testbench (`tb_lut.sv`).** The testbench performs a full address sweep (indices 0–15) and compares each output against a golden file (`expected_lut.mem`). The golden values are the Q10 fixed-point representations of exp(0), exp(-1), through exp(-15), matching the software LUT in `tinyformer.c` exactly. Any mismatch triggers `$fatal`.

Simulations are invoked from the Vivado Tcl console:

```tcl
source run_gemv_xsim.tcl
source run_lut_xsim.tcl
```

Both generate VCD waveform files (`tb_gemv.vcd`, `tb_lut.vcd`) for manual inspection.

---

## 4. Implementation

### 4.1 Hardware Description

**Platform.** The system runs on a Digilent Nexys4DDR board hosting a Xilinx Artix-7 xc7a100t FPGA. The LiteX SoC includes a VexRiscv RV32IM soft-core at 100 MHz, DDR2 SDRAM as main memory, a UART peripheral for serial output, and three custom accelerator blocks.

**DOT8 — Custom VexRiscv Instruction.**
The DOT8 accelerator adds a single new instruction to the VexRiscv pipeline via the plugin interface. The instruction computes the signed int8 dot-product of two 4-element vectors packed into two 32-bit registers:

```
result = a[0]*b[0] + a[1]*b[1] + a[2]*b[2] + a[3]*b[3]
```

where a[i] and b[i] are the i-th signed byte (lanes 0–3 in little-endian order) of the source registers, and the result is a signed int32. The instruction is encoded as opcode custom-0 (0x0B), funct7=0x01. Execution is single-cycle: the plugin intercepts the decoded instruction in the execute stage, computes four multiplications and a sum using 4 DSP blocks, and writes the int32 result back in the writeback stage. The software driver in `hw_extensions/dot8/sw/dot8.h` exposes `dot8_4_lanes(a_packed, b_packed)` using inline assembly when `USE_DOT8_HW` is defined, and falls back to a pure C implementation otherwise.

**EXP-LUT — Exponential Lookup Table Peripheral.**
The EXP-LUT peripheral is a read-only lookup table with 16 entries corresponding to exp(0), exp(-1), through exp(-15), stored in Q10 fixed-point (scale 2^10). The table values match the software LUT in `tinyformer.c` exactly, ensuring numerical equivalence between baseline and accelerated softmax. The CPU writes an index (0–15) to the index CSR register and reads the corresponding Q10 value from the output CSR register. The RTL is a purely combinational ROM implemented as a case statement in SystemVerilog. The LiteX wrapper exposes two CSR registers: `exp_lut_index` (write) and `exp_lut_value` (read).

**GEMV — Matrix-Vector Multiplier Peripheral.**
The GEMV peripheral computes Y = W×X + b, where W is an int8 matrix, X is an int8 vector, b is an optional int32 bias vector, and Y is an int32 output vector. The design features:

- **32-bit packed data path:** The `X_IN` and `W_IN` CSR registers are 32 bits wide. The CPU driver packs four int8 lanes into one 32-bit word using `pack4_i8()` before each write, reducing CSR-bus traffic by 4× compared to a byte-wide design.
- **4-lane parallel MAC:** The FSM inside `gemv_core.v` reads one packed 32-bit word from each of the internal X and W memories per clock cycle and computes four signed int8 multiply-accumulate operations in parallel. The four products are summed by an adder tree and folded into a running 32-bit accumulator, using 4 DSP blocks.
- **Output readout:** After the DONE signal asserts, the CPU reads Y values sequentially. Each read of `Y_OUT` returns the current output element; the CPU writes to `Y_NEXT` to advance the read pointer.
- **Supported dimensions:** LEN and OUT_DIM can each be 32 or 64, selected at runtime via control register bits.

For a 32×32 matvec, the design requires approximately 272 CSR writes and 256 compute cycles, delivering approximately 4× improvement in both bus and compute cost compared to a byte-wide implementation.

**Resource Utilization (Vivado report):**

| Resource | Used | Available | Util % |
|---|---|---|---|
| Slice LUTs | 6,321 | 63,400 | 9.97% |
| Slice Registers | 5,461 | 126,800 | 4.31% |
| LUT as Distributed RAM | 968 | 19,000 | 5.11% |
| RAMB36 | 47 | 135 | 34.81% |
| DSP Blocks | 8 | 240 | 3.33% |

### 4.2 Software Description

**Firmware architecture.** The firmware is organized as a set of shared common sources plus six mode-specific main files, supporting one baseline and five accelerated configurations:

| Mode | Accelerators Active |
|---|---|
| Baseline | None |
| accel_dot8 | DOT8 |
| accel_lut | EXP-LUT |
| accel_gemv | GEMV |
| accel_dot8_lut | DOT8 + EXP-LUT |
| accel_all | DOT8 + EXP-LUT + GEMV |

All modes share the same TinyFormer encoder source (`tinyformer.c`) and demo pipeline. Hardware paths are selected at compile time using feature macros (`USE_DOT8_HW`, `USE_EXP_LUT_HW`, `USE_GEMV_HW`). When a macro is not defined, the corresponding hardware is not accessed — no custom instruction, no MMIO — so the same codebase runs on a plain VexRiscv.

**TinyFormer encoder (`tinyformer.c`).** The encoder implements the full pipeline in portable C:

- Q/K/V linear projections via row-major int8 matrix-vector multiplication with int32 accumulation and right-shift scaling back to int8.
- Streaming scaled dot-product attention: one query position processed at a time, reusing 1D scratch buffers to avoid an S×S allocation.
- Softmax with max-subtraction for numerical stability, followed by Q10 exponential lookup and Q15 normalization.
- Output projection and residual (saturating int8 addition).
- Two-layer FFN with ReLU (int8 clamp to zero) and final residual.

All buffers are statically allocated. There is no `malloc`, no OS, and no libc dependency. The code compiles with `-ffreestanding -nostdlib -march=rv32im -mabi=ilp32`.

**Hardware drivers.** Each accelerator has a dedicated software driver:

- `hw_extensions/dot8/sw/dot8.c` — packing helper and inline-assembly DOT8 instruction wrapper.
- `hw_extensions/exp_lut/sw/exp_lut.c` — index and value CSR accessors for the EXP-LUT peripheral.
- `hw_extensions/gemv/sw/gemv.c` — full GEMV driver: init, load_x, load_w, load_b, start, wait_done, read_y, and clear_done.

**Demo and measurement pipeline.** The shared `demo_runner.c` iterates over 10 pre-embedded int8 test samples. For each sample it: (1) calls `tinyformer_encode()`; (2) computes a 32-bit additive checksum (`ENC_CKSUM`) over the 16×32 output; (3) mean-pools the encoder output to a D-dimensional vector; (4) applies the quantized linear classifier; (5) prints checksum, predicted class, and expected class over UART. An on-chip LiteX `timer0` peripheral is read before and after `demo_run()` to measure elapsed cycles, converted to milliseconds at `sys_clk_freq = 100 MHz`.

**On-target self-tests.** Before any benchmarking, each accelerator is validated in isolation:

- `tests_dot8.c`: Compares DOT8 hardware output against the C reference for a set of packed test vectors. Prints "DOT8 PASS" on success.
- `tests_lut.c`: Sweeps indices 0–15 and compares EXP-LUT hardware output against the golden table in `tinyformer.c`. Prints "LUT PASS" on success.
- `tests_gemv.c`: Runs GEMV with known matrices and vectors and checks results for all supported shapes. Prints "GEMV self-test PASS" on success.

---

## 5. Analysis of Results

### 5.1 Baseline Profiling

The baseline firmware (no accelerators, real fixed-point exp() math) was measured at **75,900,400 cycles (759.00 ms)** per inference across 10 samples. Cycle decomposition:

| Component | Cycles | % | Accelerated By |
|---|---|---|---|
| Softmax exp() — 2,560 calls × ~21k cyc each | ~53.8 M | 71% | EXP-LUT |
| Matrix-vector multiplications | ~16.3 M | 21% | GEMV |
| Attention dot products | ~1.0 M | 1% | DOT8 |
| UART output (115200 baud) | ~4.0 M | 5% | — |
| Misc (residuals, pool, classifier, control) | ~0.8 M | 1% | — |
| **Total** | **75.9 M** | **100%** | |

The baseline uses real per-call fixed-point multiplicative decay for each softmax exp() — the function is marked `noinline` and compiled without optimization to prevent the compiler from folding or memoizing the computation — so the EXP-LUT comparison is fair: every exponent is genuinely computed at runtime.

### 5.2 Performance Results

All measurements were taken on the same FPGA bitstream, with only the firmware binary changing between modes. The on-chip LiteX `timer0` peripheral provides cycle-accurate measurement independent of host-side serial latency.

| Mode | Cycles | Latency | Speedup |
|---|---|---|---|
| Baseline | 75,900,400 | 759.00 ms | 1.00× |
| **accel_all (DOT8 + EXP-LUT + GEMV)** | **15,755,300** | **157.55 ms** | **4.82×** |

Speedup = 75,900,400 / 15,755,300 = **4.82×**

### 5.3 Correctness Verification

Before reporting performance numbers, every accelerated build was required to pass the ENC_CKSUM correctness gate: the 32-bit additive checksum over the encoder's 16×32 int8 output must be identical between baseline and accelerated modes for every sample. The verified checksums across all 10 samples are:

```
0x00005CE7   0x00006557   0x000068B6   0x00006469   0x000062A1
0x000063A6   0x0000627B   0x00006ACF   0x0000719B   0x00007185
```

All checksums are identical across baseline and accel_all, confirming that the speedup reflects genuine acceleration and not skipped computation. Predicted classes also match the baseline for all 10 samples.

### 5.4 Per-Accelerator Contribution

The EXP-LUT peripheral eliminates the dominant bottleneck (71% of baseline cycles) by replacing approximately 21,000-cycle per-call runtime computation with a 12-cycle MMIO lookup — approximately 1,700× faster per call. The GEMV peripheral (4-lane MAC) is the single largest design win in absolute cycle savings, reducing matrix-vector multiply time by approximately 8× per call (from ~17,000 cycles to ~2,000 cycles for a 32×32 matvec), driven equally by the 4× reduction in CSR-bus writes and the 4× reduction in compute cycles from the parallel MAC. DOT8 contributes a minor speedup consistent with the small initial cycle share of attention dot products.

### 5.5 Area and Power

The accelerators add **+3.9 percentage points of LUT** and **+1.8 percentage points of flip-flops** relative to a plain VexRiscv baseline. Total LUT utilization is 9.97%, within the less-than-10% design target. Power increases by a factor of 1.07 (approximately 7%). Approximately **90% of the FPGA fabric remains free** for future extensions.

The 4.82× speedup at a 7% power increase represents a strongly favorable trade-off: the system reaches a target latency of 157.55 ms while consuming only marginally more power than the unaccelerated baseline.

---

## 6. Conclusions and Further Work

### 6.1 Conclusions

This project demonstrates that targeted hardware acceleration can provide substantial inference speedup on an embedded RISC-V soft-core with minimal FPGA area overhead. The key findings are:

1. **Bottleneck identification is essential.** The 71% cycle share of softmax exp() was not obvious a priori. Without profiling, design effort might have been misallocated to attention dot-products, which represent only 1% of cycles.

2. **EXP-LUT provides disproportionate gains.** Replacing a ~21,000-cycle per-call computation with a ~12-cycle lookup accounts for the majority of the cycle reduction, despite being the simplest accelerator in terms of RTL complexity.

3. **Data-path width matters as much as compute parallelism.** The 32-bit packed GEMV design with 4-lane parallel MAC delivers equal improvements on both the CSR-bus side and the compute side, confirming that memory and bus bandwidth is a co-bottleneck with raw arithmetic throughput.

4. **Correctness must precede performance measurement.** The ENC_CKSUM gate prevented reporting incorrect speedups and ensured that every measured result corresponds to a bit-identical inference.

5. **4.82× speedup at less than 10% LUT cost** is competitive with published work (KWT-Tiny: 5× at 29% area overhead) while preserving full bit-exact accuracy and using a fully open, reproducible FPGA platform.

### 6.2 Further Work

- **DMA-based GEMV.** The current design requires the CPU to write all W and X elements to CSR registers over the system bus. A DMA engine would allow the GEMV core to fetch rows of W directly from DDR, eliminating CPU involvement in data movement and further reducing inference latency.

- **Wider DOT8.** An 8-lane DOT8 instruction — using two packed 32-bit source words — would double attention throughput and may become worthwhile in models with larger model dimension D.

- **Larger EXP-LUT.** A larger table with more entries or higher Q-format precision would support models with wider attention logit ranges without any firmware changes.

- **Larger models and tiling.** The GEMV peripheral currently supports matrices up to 64×64. Tiling support would enable larger model dimensions (e.g. D=64 or D=128) and multi-head attention without architectural changes to the peripheral.

---

## 7. Project Documentation

All project deliverables are maintained in two Git repositories:

**Algorithm and firmware repository (TinyML_algo):** Contains the TinyFormer C firmware (`litex_port/`), hardware accelerator RTL and drivers (`hw_extensions/`), training and export scripts (`training/`, `tools/`), pre-trained artifacts (`artifacts/`), FPGA-ready C exports (`litex_port/common/`), and SystemVerilog testbenches (`run_gemv_xsim.tcl`, `run_lut_xsim.tcl`).

**LiteX SoC repository (litex-nexys4ddr):** Contains the LiteX SoC build scripts, bitstream generation configuration, accelerator integration paths, and memory initialization documentation.

**Key directories:**

| Directory | Contents |
|---|---|
| `TinyML_algo/litex_port/common/` | Shared firmware sources (encoder, demo runner, UART driver, weights) |
| `TinyML_algo/litex_port/baseline/` and `accel_*/` | Per-mode main files |
| `TinyML_algo/hw_extensions/dot8/`, `exp_lut/`, `gemv/` | RTL, LiteX wrappers, and SW drivers |
| `TinyML_algo/training/` | Dataset download, preprocessing, and training scripts |
| `TinyML_algo/artifacts/` | Trained encoder and classifier weight files |

Reproduction steps are fully documented in `TinyML_algo/TinyML_algo/README.md` and `REPORT_NOTES_IMPLEMENTATION.md`, covering: LiteX SoC build, firmware compilation per mode, self-test execution, correctness verification, and performance measurement.

---

## 8. References

[1] A. Al-Qawlaq, A. Kumar M, D. John, "KWT-Tiny: RISC-V Accelerated, Embedded Keyword Spotting Transformer," arXiv:2407.16026, 2024.

[2] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, L. Kaiser, I. Polosukhin, "Attention Is All You Need," Advances in Neural Information Processing Systems (NeurIPS), 2017.

[3] LiteX SoC Builder. Available: https://github.com/enjoy-digital/litex

[4] VexRiscv RISC-V CPU. Available: https://github.com/SpinalHDL/VexRiscv

[5] D. Anguita, A. Ghio, L. Oneto, X. Parra, J. L. Reyes-Ortiz, "A Public Domain Dataset for Human Activity Recognition Using Smartphones," ESANN 2013.
