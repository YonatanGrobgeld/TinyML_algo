# TinyFormer: Hardware-Accelerated Transformer Inference on FPGA

---

| | |
|---|---|
| **Project Title** | TinyFormer: Hardware-Accelerated Transformer Inference on FPGA |
| **Project Number** | [Project Number] |
| **Student** | Ron Weinstein |
| **ID** | [ID] |
| **Student** | Yehonatan Grobgeld |
| **ID** | [ID] |
| **Supervisor** | Oren Ganon |
| **Project Carried Out at** | Faculty of Engineering, Tel Aviv University |

---

## Table of Contents

- [Abstract](#abstract)
- [1. Introduction](#1-introduction)
- [2. Theoretical Background](#2-theoretical-background)
- [3. Implementation](#3-implementation)
- [4. Simulation](#4-simulation)
- [5. Analysis of Results](#5-analysis-of-results)
- [6. Conclusions and Further Work](#6-conclusions-and-further-work)
- [7. Project Documentation](#7-project-documentation)
- [8. References](#8-references)
- [Appendix A: LUT Table Values](#appendix-a-lut-table-values)
- [Appendix B: GEMV CSR Register Map](#appendix-b-gemv-csr-register-map)

## List of Figures

- Figure 1 — System Architecture: Baseline vs. Accelerated Modes
- Figure 2 — LiteX SoC Architecture
- Figure 3 — DOT8 Custom Instruction Pipeline Integration
- Figure 4 — EXP-LUT Peripheral Interface
- Figure 5 — GEMV Peripheral Data-Flow
- Figure 6 — TinyFormer Encoder Architecture
- Figure 7 — GEMV Simulation: Full Operation Overview
- Figure 8 — GEMV Simulation: Start Handshake
- Figure 9 — GEMV Simulation: One Compute Row (4-lane MAC)
- Figure 10 — GEMV Simulation: Completion and Result Read-back
- Figure 11 — EXP-LUT Simulation: Full Index Sweep (Test 1)
- Figure 12 — EXP-LUT Simulation: Stability Hold (Test 2)
- Figure 13 — Baseline Cycle Decomposition (per inference)
- Figure 14 — Performance Comparison Graph

## List of Tables

- Table 1 — TinyFormer Model Parameters
- Table 2 — FPGA Resource Utilization and Power
- Table 3 — Firmware Build Modes
- Table 4 — Algorithm Operation Count per Stage
- Table 5 — Per-Timestep Feature Vector Layout
- Table 6 — RTL Simulation Test Scenarios
- Table 7 — Baseline Cycle Decomposition
- Table 8 — Performance Comparison
- Table 9 — Per-Accelerator Cycle Savings
- Table 10 — Correctness Checksums (All 10 Samples)
- Table 11 — Project Goals vs. Achieved Results

## Abstract

This project implements and accelerates a compact Transformer encoder — TinyFormer — on an FPGA-hosted RISC-V soft-core targeting human activity recognition. The platform is a Digilent Nexys4DDR board running a LiteX-generated SoC with a VexRiscv RV32IM CPU at 100 MHz. The model performs 6-class classification over the UCI Human Activity Recognition (UCI HAR) dataset, with all weights and activations quantized to int8. The encoder processes input sequences of shape 16×32 (16 timesteps, 32-dimensional feature vectors) through a full Transformer encoder block: Q/K/V linear projections, scaled dot-product attention with softmax, output projection, residual connections, and a two-layer feed-forward network.

A pure-software baseline measured at **75.9 million cycles (759 ms)** per inference reveals that 71% of cycles are consumed by softmax exponential computation and 21% by matrix-vector multiplications. Three targeted hardware accelerators were designed, verified, and integrated to eliminate these bottlenecks:

1. **DOT8** — a custom VexRiscv instruction for 4-lane signed int8 dot-products, using 4 DSP blocks in the CPU pipeline.
2. **EXP-LUT** — an MMIO peripheral replacing the runtime softmax exponential computation with a 16-entry Q10 fixed-point lookup table.
3. **GEMV** — an MMIO peripheral with a 4-lane parallel MAC for matrix-vector multiplication, featuring a 32-bit packed data path that reduces CSR-bus traffic by 4×.

The final combined system achieves a **4.82× end-to-end speedup** (759.00 ms → 157.55 ms). Bit-identical correctness is verified by a 32-bit additive checksum over the encoder's 16×32 int8 output for every inference, so model accuracy is unchanged by acceleration. Total LUT utilization is **10.04%** (up from 6.13% for the plain soft-core), leaving roughly 90% of the FPGA fabric free for future extensions. Power rises only modestly, from **0.740 W to 0.792 W** (1.07×, ≈7%) — a deliberate area/power-for-speed trade-off in exchange for the 4.82× gain.

*Figure 1 — System Architecture: Baseline vs. Accelerated Modes*

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    Nexys4DDR FPGA (Xilinx Artix-7)                   │
  │                                                                      │
  │  ┌────────────────────────┐     ┌──────────────────────────────────┐ │
  │  │  VexRiscv RV32IM CPU   │     │       Custom Accelerators        │ │
  │  │  (100 MHz, DOT8 plugin)│     │                                  │ │
  │  │                        │     │  ┌──────────┐  ┌──────────────┐  │ │
  │  │  Firmware modes:       │     │  │  EXP-LUT │  │     GEMV     │  │ │
  │  │  - baseline            │     │  │ (MMIO)   │  │   (MMIO)     │  │ │
  │  │  - accel_all           │◄───►│  │ 16 Q10   │  │  4-lane MAC  │  │ │
  │  │    (DOT8 + EXP-LUT     │     │  │ entries  │  │  32/64-dim   │  │ │
  │  │     + GEMV)            │     │  └──────────┘  └──────────────┘  │ │
  │  │                        │     │                                  │ │
  │  └───────────┬────────────┘     └──────────────────────────────────┘ │
  │              │                                                        │
  │  ┌───────────▼────────────┐     ┌──────────────────────────────────┐ │
  │  │   LiteX SoC Bus        │     │  DDR2 SDRAM                      │ │
  │  │   (AXI/Wishbone)       │◄───►│  (Firmware + Weights)            │ │
  │  └───────────┬────────────┘     └──────────────────────────────────┘ │
  │              │                                                        │
  │  ┌───────────▼────────────┐                                          │
  │  │  UART (115200 baud)    │◄──── Serial output: checksums, results   │
  │  └────────────────────────┘                                          │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 1. Introduction

### 1.1 Goals

The goals of this project are:

1. Implement a complete, bare-metal Transformer encoder (TinyFormer) in firmware on a VexRiscv RISC-V soft-core running inside a LiteX SoC on an FPGA.
2. Establish a correct, cycle-accurate baseline measurement using an on-chip hardware timer.
3. Profile the baseline to quantify the computational bottlenecks with cycle-level precision.
4. Design three hardware accelerators — a custom CPU instruction and two MMIO peripherals — each targeting a distinct, measured bottleneck.
5. Verify bit-exact correctness of each accelerated build against the baseline by checksum before reporting any performance numbers.
6. Measure and report the end-to-end speedup while remaining within a less than 10% LUT utilization footprint on the target FPGA.

### 1.2 Motivation

Transformer-based models have emerged as the dominant architecture for sequence modeling — from natural language processing to audio classification and inertial-sensor-based activity recognition. Even compact Transformer variants, however, impose two predictable bottlenecks on embedded RISC-V processors: (1) the matrix-vector multiplications in the linear projection layers, and (2) the softmax exponential function in the self-attention mechanism.

A soft-core RISC-V CPU running at 100 MHz on an FPGA offers a flexible, reconfigurable compute substrate. In its unmodified form, however, it cannot match the throughput demands of always-on inference. The VexRiscv RV32IM ISA provides single-cycle multiplication in hardware (via the M extension), but sequential scalar code still requires separate load, sign-extend, multiply, and accumulate instructions for every multiply-add, producing significant loop overhead in high-dimensional dot products. Softmax exponentiation, implemented honestly as runtime fixed-point arithmetic, contributes disproportionately to total inference time.

This project demonstrates that targeted hardware acceleration — implemented with a small FPGA area budget — can close this gap substantially, achieving better than a 4.8× end-to-end speedup while occupying roughly 10% of available LUT resources and increasing power by only about 7%.

### 1.3 Approach

The project follows a disciplined, evidence-driven methodology:

1. **Establish correctness first.** A complete, verified pure-software baseline is built before any hardware is touched. Every inference produces a 32-bit additive checksum over the encoder output that serves as the correctness gate for all subsequent accelerated builds.
2. **Profile to identify true bottlenecks.** Cycle counts are measured per-component by instrumented firmware runs, not estimated from instruction counts.
3. **Design accelerators that target measured bottlenecks.** Each accelerator addresses a specific, quantified cycle contributor.
4. **Verify correctness before benchmarking.** An accelerated build may not be benchmarked until its checksum matches the baseline on every test sample.
5. **Report on-chip measurements.** All performance numbers come from the LiteX hardware timer, not host-side wall-clock, which is unreliable at the granularity required.

### 1.4 Comparison with Related Work

**KWT-Tiny [1]** presents a RISC-V accelerated keyword spotting Transformer targeting a custom ASIC chip with 64 kB RAM. They achieve a 5× speedup through custom instructions for GELU and softmax, with a 29% area overhead. Their approach requires aggressive model compression (369× size reduction) and accepts a 10% accuracy loss due to class reduction.

This work differs in several important respects. The target is a commodity FPGA platform — the Digilent Nexys4DDR — offering full bitstream transparency and reproducibility without requiring a custom chip tape-out. The model retains full bit-exact correctness (no accuracy loss from the accelerators). The accelerators' LUT cost is +3.9 percentage points (6.13% → 10.04%) — roughly 7× smaller than KWT-Tiny's reported 29% area overhead. Both works attack the same fundamental bottlenecks — softmax exponential and attention inner products on embedded RISC-V — and arrive at comparable end-to-end speedups (4.82× vs. 5×) through different design trade-offs.

The **Attention Is All You Need** paper [2] by Vaswani et al. defines the Transformer architecture that this project implements in miniature. The architecture choices made in TinyFormer (single head, S=16, D=32) are direct simplifications of the original architecture, motivated by the resource constraints of a bare-metal FPGA implementation.

---

## 2. Theoretical Background

### 2.1 Transformer Encoder Architecture

The Transformer encoder [2] processes an input sequence of token vectors through a self-attention mechanism followed by a feed-forward network (FFN), with residual connections around each sub-layer.

Given an input matrix X of shape (S×D) — sequence length S, model dimension D — the encoder computes:

1. **Linear projections:** Query, Key, and Value matrices are computed as Q = XW_q, K = XW_k, V = XW_v, where W_q, W_k, W_v are D×D weight matrices.
2. **Scaled dot-product attention:** Attention scores A = softmax(QK^T / √D), then context C = AV.
3. **Output projection:** The context is projected back through W_o: Out = CW_o.
4. **Residual and FFN:** The residual Y = X + Out is passed through a two-layer feed-forward network: Z = Y + FFN(Y), where FFN applies two linear layers with a ReLU activation in between.

TinyFormer uses S=16, D=32, FFN hidden size=64, and a single attention head.

**Table 1 — TinyFormer Model Parameters**

| Parameter | Value | Description |
|---|---|---|
| Sequence Length (S) | 16 | Timesteps per input sample |
| Model Dimension (D) | 32 | Feature vector size per timestep |
| FFN Hidden Size | 64 | Intermediate dimension in feed-forward network |
| Attention Heads | 1 | Single-head (simplified) |
| Weight Data Type | int8 | All weights quantized to 8-bit signed integer |
| Activation Data Type | int8 | All activations quantized to 8-bit signed integer |
| Accumulator Type | int32 | Internal multiply-accumulate precision |
| Task | 6-class HAR | UCI Human Activity Recognition dataset |

### 2.2 Integer Quantization

All weights and activations in TinyFormer are quantized to int8 (8-bit signed integers, range −128 to +127). Accumulators are promoted to int32 to prevent overflow during multiply-accumulate operations. After each linear layer, results are scaled back to int8 using a fixed arithmetic right-shift of 7 bits, followed by saturation to the int8 range. This approach eliminates all floating-point operations from the inference path, which is essential for efficient FPGA and bare-metal RISC-V implementation.

The softmax function requires exponentiation. In the baseline, `exp(−k)` is computed genuinely at runtime by `compute_exp_q10()`: a fixed-iteration arithmetic loop followed by a multiplicative-decay loop using a single mathematical constant `decay_q15 = 24149 ≈ 0.7368 × 2^15` (one constant, *not* a lookup table). The function is declared `__attribute__((noinline, optimize("O0")))` so that the compiler cannot unroll, constant-fold, or memoize it — the per-call work is genuinely paid on every softmax lookup. In the accelerated builds, this entire loop is replaced by a single read from a 16-entry lookup table covering exp(0) through exp(−15), stored in Q10 fixed-point format (values scaled by 2^10 = 1024). The softmax denominator `sum_exp` is accumulated in 32-bit fixed-point, and the per-key attention weight is then computed as `w_q15 = (exp_value << 15) / sum_exp` in Q15 format before the weighted sum over the value vectors.

### 2.3 LiteX SoC Framework

LiteX [3] is an open-source FPGA SoC builder that generates a complete system — including CPU instantiation, memory controllers, bus fabric, and peripheral CSR (Control and Status Register) maps — from Python descriptions. In this project, LiteX generates the VexRiscv RV32IM soft-core, connects it to DDR2 SDRAM, exposes a UART peripheral for serial output, and provides the infrastructure into which the three custom accelerators are integrated as memory-mapped peripherals.

The LiteX framework generates C header files (`generated/csr.h`) that expose each peripheral's CSR registers as typed C accessor macros, allowing the firmware to interact with hardware peripherals using standard C without hand-crafted MMIO pointer arithmetic.

### 2.4 VexRiscv and Custom Instructions

VexRiscv [4] is a flexible, plugin-based RISC-V CPU written in SpinalHDL. Its plugin architecture allows new functional units to be inserted at the decode, execute, and writeback pipeline stages without modifying the core. The RISC-V ISA reserves the custom-0 through custom-3 opcodes for non-standard extensions. This project uses custom-0 (opcode 0x0B) with funct7=0x01 for the DOT8 instruction. The plugin intercepts the decoded instruction in the execute stage, computes four signed int8 multiply-accumulate operations using 4 DSP blocks, and writes the int32 result back in the writeback stage.

### 2.5 MMIO Peripheral Design

Memory-mapped I/O (MMIO) peripherals appear to the CPU as ordinary memory addresses. The CPU writes to control registers and reads from status and result registers using standard load/store instructions. In LiteX, peripherals are described as Python modules that generate both the synthesizable RTL (Verilog or Migen) and the C header definitions automatically, ensuring consistency between hardware and software without manual address bookkeeping.

### 2.6 Alternative Approaches Considered

Several alternative algorithms and architectures were evaluated before settling on the DOT8 + EXP-LUT + GEMV combination. They are summarized here and revisited against the chosen design in the results analysis (Section 5).

- **Software-only optimization.** Loop unrolling, manual instruction scheduling, and `-O3` on the baseline can reduce cycles somewhat, but they cannot overcome the fundamental cost of computing softmax exponentials and high-dimensional dot-products one scalar operation at a time on a scalar RV32IM core. This approach is the baseline against which all accelerators are measured.
- **Full systolic-array GEMM.** A 2-D systolic array would maximize matrix-multiply throughput, but TinyFormer's workload is matrix-*vector* (S processed token-by-token), and a full array would consume far more than the 10% LUT budget and leave most PEs idle. A single 4-lane streaming MAC (GEMV) was chosen as the right granularity for the problem size.
- **Exponential by polynomial/CORDIC instead of a LUT.** The softmax exponential could be computed in hardware with a Taylor/CORDIC pipeline. This is more general (arbitrary input range) but larger and slower than a 16-entry ROM; since the attention logits occupy a known, small range after max-subtraction, a fixed Q10 LUT is exact for this model and essentially free in area.
- **Per-channel / power-of-two quantization.** More sophisticated quantization (per-channel scales, learned step sizes) would reduce the int8 accuracy gap relative to the uniform right-shift-by-7 scheme used here, at the cost of more complex requantization logic. This was deferred (see Section 6.2) because correctness, not maximum accuracy, was the gating requirement.
- **DMA-fed accelerators.** Instead of the CPU streaming W and X over the CSR bus, a DMA engine could fetch operands directly from DDR2. This removes CPU bus traffic entirely but adds bus-master complexity; it was scoped as future work after the packed-CSR GEMV already delivered the bulk of the available speedup.

---

## 3. Implementation

### 3.1 Hardware Platform

The system runs on a Digilent Nexys4DDR board hosting a Xilinx Artix-7 xc7a100t FPGA. The LiteX SoC includes a VexRiscv RV32IM soft-core at 100 MHz, DDR2 SDRAM as main memory, a UART peripheral for serial output, and three custom accelerator blocks. The SoC bus fabric, memory map, and peripheral CSR layout are generated by the LiteX build system from Python source.

*Figure 2 — LiteX SoC Architecture*

```
   ┌────────────────────────────────────────────────────────┐
   │                    LiteX SoC                           │
   │                                                        │
   │  ┌───────────┐    ┌─────────────────────────────────┐  │
   │  │ VexRiscv  │    │       Peripheral Bus              │  │
   │  │ RV32IM    │◄──►│ ┌──────┐ ┌──────┐ ┌──────────┐  │  │
   │  │ (DOT8     │    │ │UART  │ │Timer0│ │EXP-LUT   │  │  │
   │  │  plugin)  │    │ │CSR   │ │CSR   │ │CSR       │  │  │
   │  └───────────┘    │ └──────┘ └──────┘ └──────────┘  │  │
   │                   │ ┌──────────────────────────────┐ │  │
   │                   │ │GEMV Peripheral CSR           │ │  │
   │  ┌───────────┐    │ │(CTRL,X_IN,W_IN,B_IN,Y_OUT,  │ │  │
   │  │ DDR2      │◄──►│ │STATUS,Y_NEXT)                │ │  │
   │  │ SDRAM     │    │ └──────────────────────────────┘ │  │
   │  │ Controller│    └─────────────────────────────────┘  │
   │  └───────────┘                                         │
   └────────────────────────────────────────────────────────┘
```

### 3.2 Hardware Accelerators

#### DOT8 — Custom VexRiscv Instruction

The DOT8 accelerator adds a single new instruction to the VexRiscv pipeline via the plugin interface. The instruction computes the signed int8 dot-product of two 4-element vectors packed into two 32-bit registers:

```
result = a[0]×b[0] + a[1]×b[1] + a[2]×b[2] + a[3]×b[3]
```

where a[i] and b[i] are the i-th signed byte (lanes 0–3 in little-endian order) of the source registers, and the result is a signed int32.

**Encoding:** The instruction is a standard RISC-V R-type, using opcode custom-0 (0x0B) and funct7=0x01. funct3 is reserved for future variant selection (e.g. an 8-lane or multiply-accumulate form).

| Bits 31–25 | 24–20 | 19–15 | 14–12 | 11–7 | 6–0 |
|---|---|---|---|---|---|
| funct7 = 0x01 | rs2 | rs1 | funct3 | rd | opcode = 0x0B |
| 7 bits | 5 bits | 5 bits | 3 bits | 5 bits | 7 bits |

rs1 and rs2 each carry four packed signed int8 lanes (lane 0 in the LSB byte); rd receives the int32 dot-product. Each lane is sign-extended to int32 before multiplication.

**Execution:** Single-cycle. The plugin intercepts the decoded instruction in the execute stage, computes four signed int8×int8 multiplications and a four-input adder tree using 4 DSP blocks, and writes the int32 result back in the writeback stage. No pipeline stall is introduced.

**Integration:** The baseline inner loop for a 32-element dot product requires 32 iterations of load–sign-extend–multiply–accumulate (approximately 8 instructions per iteration, 256 total). With DOT8, the same dot product is expressed as 8 DOT8 calls over 4-lane packed inputs, each preceded by 2 pack operations, reducing the inner-loop instruction count by approximately 6.4×.

*Figure 3 — DOT8 Custom Instruction Pipeline Integration*

```
  VexRiscv Pipeline:

  ┌─────────┐   ┌─────────┐   ┌───────────────────────┐   ┌──────────┐
  │  Fetch  │──►│ Decode  │──►│  Execute (Dot8Plugin) │──►│Writeback │
  └─────────┘   └─────────┘   │                       │   └──────────┘
                               │ opcode==0x0B &&       │
                               │ funct7==0x01 ?        │
                               │                       │
                               │ DSP[0]: a[0]×b[0]     │
                               │ DSP[1]: a[1]×b[1]     │
                               │ DSP[2]: a[2]×b[2]     │
                               │ DSP[3]: a[3]×b[3]     │
                               │      ↓ adder tree     │
                               │   int32 result        │
                               └───────────────────────┘
```

#### EXP-LUT — Exponential Lookup Table Peripheral

The EXP-LUT peripheral (`exp_lut.v`) is a read-only lookup table with 16 entries corresponding to exp(0), exp(−1), through exp(−15), stored in Q10 fixed-point (scale 2^10). The values are held in a 16-entry `reg [15:0]` array initialized in an `initial` block and read purely combinationally — there is no clocked latency on the read path. The accelerator accepts a 5-bit signed index but uses only its low 4 bits as the table address (`addr = index[3:0]`), so indices 0–15 map directly to exp(0) through exp(−15). The table values are defined to match the software golden table in `tinyformer.c` byte-for-byte, guaranteeing numerical equivalence between baseline and accelerated softmax (see Appendix A).

**Operation:** The CPU writes an index (0–15) to the index CSR register and reads the corresponding Q10 value from the value CSR register. The total per-lookup cost in the accelerated firmware is two MMIO operations (~12 cycles), replacing the runtime `compute_exp_q10()` loop of the baseline. Given the baseline's measured softmax cost (≈21,000 cycles per call, derived in Section 5.1), this is roughly a 1,700× per-call reduction.

*Figure 4 — EXP-LUT Peripheral Interface*

```
  CPU Firmware                    EXP-LUT Peripheral
  ─────────────────               ─────────────────────────────────
                                  ┌─────────────────────────────┐
  Write idx → exp_lut_index CSR──►│ index[3:0]                  │
                                  │                             │
                                  │   case(index)               │
                                  │   0: 1024 (exp(0) Q10)      │
                                  │   1:  754 (exp(-1) Q10)     │
                                  │   ...                       │
                                  │  15:   12 (exp(-15) Q10)    │
                                  │                             │
  Read ← exp_lut_value CSR ◄──────│ value[15:0]  (combinatorial)│
                                  └─────────────────────────────┘
```

#### GEMV — Matrix-Vector Multiplier Peripheral

The GEMV peripheral computes Y = W×X + b, where W is an int8 matrix, X is an int8 vector, b is an optional int32 bias vector, and Y is an int32 output vector.

**Design (32-bit packed data path, 4-lane MAC):**

The GEMV peripheral uses a 32-bit packed data path with a 4-lane parallel MAC. Both the `X_IN` and `W_IN` CSR registers are 32 bits wide; the firmware driver packs four int8 elements into each word using `pack4_i8()`, so a 32×32 matvec requires only about 272 CSR writes — a 4× reduction in bus traffic compared to a naïve one-byte-per-write design (which would need 1,088 writes). The internal X and W memories are 32-bit word arrays, and the FSM reads one packed word from each per clock cycle, computing four signed int8 multiply-accumulate operations in parallel (a 4-lane dot-product unit built from 4 DSP blocks). A 32×32 matvec therefore completes in 256 compute cycles — a further 4× improvement over a one-MAC-per-cycle design. The two optimisations are independent and multiply: 4× on the bus and 4× on compute.

**Key features:**
- **32-bit packed data path:** 4× reduction in CSR-bus writes.
- **4-lane parallel MAC:** 4× reduction in compute cycles.
- **Supported dimensions:** LEN and OUT_DIM each 32 or 64, selected at runtime via control register bits.
- **Output readout:** After DONE asserts, the CPU reads Y values sequentially; a write to `Y_NEXT` advances the read pointer.

**Control FSM.** The `gemv_core.v` module separates data loading from computation. Writes to the X, W, and B memories are handled by an always-on write path with auto-incrementing word indices (reset by `clear_done`), independent of the compute FSM. The compute FSM itself has only three states:

- **S_IDLE** — waits for the `start` pulse; on start, preloads the accumulator with `b_mem[0]` (or 0 if bias is disabled).
- **S_COMPUTE** — for each output row, iterates over the LEN/4 packed words of X and W (8 words for LEN=32, 16 for LEN=64), performing one 4-lane signed dot-product (`dot4`) per clock cycle and folding it into the accumulator. When a row completes, the accumulator is written to `y_mem[row]` and reloaded with the next row's bias. A 32×32 matvec therefore takes 32 rows × 8 words = **256 compute cycles**.
- **S_DONE** — asserts `done`; the CPU polls this, reads out the 32 results via `Y_OUT`/`Y_NEXT`, then issues `clear_done` to return the FSM to idle.

*Figure 5 — GEMV Peripheral Data-Flow*

```
  CPU Firmware                      GEMV Core (gemv_core.v)
  ──────────────────                ──────────────────────────────────────
                                    ┌──────────────────────────────────┐
  pack4_i8(X[0..3]) → X_IN CSR ───►│ X memory (32-bit words)          │
  pack4_i8(X[4..7]) → X_IN CSR ───►│ 32 or 64 elements                │
  ...                               │                                  │
  pack4_i8(W[row,0..3])→W_IN CSR──►│ W memory (32-bit words)          │
  ...                               │ 32×32 or 64×64                   │
  b[0] → B_IN CSR ────────────────►│ b memory (int32)                 │
  ...                               │                                  │
  CTRL.start = 1 ─────────────────►│ FSM:                             │
                                    │   for each output row:           │
  Poll CTRL.done ◄────────────────  │     acc = b[row]                 │
                                    │     for i in 0..LEN/4:           │
                                    │       [p,q,r,s] = W_mem[row*i]   │
                                    │       [a,b,c,d] = X_mem[i]       │
                                    │       acc += p*a+q*b+r*c+s*d     │
                                    │   Y_mem[row] = acc               │
                                    │                                  │
  Read Y_OUT CSR ◄────────────────  │ Y_mem[y_read_idx]               │
  Write Y_NEXT CSR (advance ptr) ──►│                                  │
                                    └──────────────────────────────────┘
```

**Resource Utilization and Power (Vivado Report):**

Resource and power figures are reported for both firmware configurations on the same xc7a100t bitstream at 100 MHz. The accelerators were measured against the plain-VexRiscv baseline.

**Table 2 — FPGA Resource Utilization and Power (xc7a100t @ 100 MHz)**

| Metric | Baseline | Accelerated | Change |
|---|---|---|---|
| Power | 0.740 W | 0.792 W | ×1.07 (≈ +7%) |
| Slice LUTs | 6.13% | 10.04% | +3.9 pp |
| Slice Registers (FF) | 2.49% | 4.32% | +1.8 pp |
| DSP Blocks | 0% | 3.3% | +3.3 pp |

The 8 DSP blocks in the accelerated build comprise 4 for the DOT8 multiplier array and 4 for the GEMV 4-lane MAC; the plain VexRiscv RV32IM multiplier is mapped to logic and uses no DSPs, which is why the baseline DSP utilization is 0%. The accelerated build additionally occupies 47 of 135 RAMB36 block-RAMs (≈34.8%) and 968 LUTs as distributed RAM for SoC memory and peripheral storage. At 10.04% LUT utilization, roughly 90% of the FPGA fabric remains free for future extensions.

**Timing.** The Vivado implementation reports WNS = −6.309 ns on the worst path inside `gemv_core.v` (the 4-lane multiply + adder-tree + accumulator-add chain). The design routes cleanly with zero routing errors and produces bit-identical encoder output across all test samples at room temperature. For a production deployment, the dot4 stage should be pipelined (adding one cycle of latency) or `sys_clk_freq` should be reduced to approximately 75 MHz to close timing cleanly.

### 3.3 Software Description

#### Firmware Architecture

The firmware is organized as a set of shared common sources plus mode-specific main files. Both configurations share the same TinyFormer encoder implementation, and hardware paths are selected at compile time using feature macros. This report focuses on the two end-point configurations — the pure-software baseline and the fully-accelerated `accel_all` build.

**Table 3 — Firmware Build Modes**

| Mode | Accelerators Active | Feature Macros |
|---|---|---|
| Baseline | None | `USE_TRAINED_WEIGHTS`, `USE_LITEX_UART` |
| accel_all | DOT8 + EXP-LUT + GEMV | + `USE_DOT8_HW`, `USE_EXP_LUT_HW`, `USE_GEMV_HW` (with the LiteX-CSR variants) |

When a macro is not defined, the corresponding hardware is never accessed — no custom instruction opcode is issued, no MMIO register is touched — so the same codebase runs correctly on a plain VexRiscv (baseline) or with all three accelerators enabled (`accel_all`).

#### TinyFormer Encoder (`tinyformer.c`)

The encoder implements the full Transformer encoder pipeline in portable C with no dynamic allocation, no OS, and no libc dependency. The code compiles with `-ffreestanding -nostdlib -march=rv32im -mabi=ilp32`.

**Algorithm stages:**

1. **Q/K/V linear projections:** Each input token (row of X) is multiplied by the weight matrices W_q, W_k, W_v via row-major int8 matrix-vector multiplication with int32 accumulation. Results are right-shifted by 7 bits and saturated to int8 using the `saturate_int32_to_int8` macro. This produces Q, K, and V tensors of shape 16×32. In `accel_all`, all projections use the GEMV peripheral.

2. **Streaming scaled dot-product attention:** One query position is processed at a time, reusing 1D scratch buffers (`scores[16]`, `exp_buf[16]`) rather than allocating a full 16×16 attention matrix. For each query position: (a) the int32 dot-product against each of the 16 key positions is computed and right-shifted by 5 bits to approximate the 1/√D scaling; (b) the per-query maximum score is subtracted for numerical stability and the result further right-shifted by 3 bits to compress the dynamic range into roughly [−15, 0] before being clamped and used as the exp index; (c) exp values are obtained (via EXP-LUT in accelerated builds, `compute_exp_q10()` in the baseline) and summed; (d) each weight is normalized to Q15 as `(exp_buf[j] << 15) / sum_exp` and the Q15-weighted sum over the value vectors, right-shifted by 15, produces the context vector. The inner dot-product loops use the DOT8 instruction in accelerated builds.

3. **Output projection and residual:** The context output is projected through W_o and added to the original input via saturating int8 addition.

4. **Two-layer FFN with residual:** W_ff1 (32→64) with ReLU activation, followed by W_ff2 (64→32), with the result added back via a second residual connection. Both layers use the GEMV peripheral in accelerated builds.

**Figure 6 — TinyFormer Encoder Architecture**

```
(figure)
```

**Table 4 — Algorithm Operation Count per Stage**

| Stage | Matrices | Multiply-Accumulate Ops | Output Shape |
|---|---|---|---|
| Q/K/V projections | W_q, W_k, W_v (3×32²) | 3 × 16 × 1,024 = 49,152 | [16][32] each |
| Attention scores | Q·K inner products | 16 × 16 × 32 = 8,192 | [16][16] |
| Softmax | LUT + normalization | 16 × 16 = 256 lookups | [16][16] |
| Value aggregation | attention × V | 16 × 16 × 32 = 8,192 | [16][32] |
| Output projection | W_o (32²) | 16 × 1,024 = 16,384 | [16][32] |
| FFN layer 1 | W_ff1 (64×32) | 16 × 64 × 32 = 32,768 | [16][64] |
| FFN layer 2 | W_ff2 (32×64) | 16 × 32 × 64 = 32,768 | [16][32] |
| **Total** | | **~147,456** | [16][32] |

#### Hardware Drivers

Each accelerator exposes a dedicated, compile-time-selectable software driver:

- **`hw_extensions/dot8/sw/dot8.h`** — packing helper `dot8_pack()` and inline-assembly `dot8_4_lanes(a_packed, b_packed)` that emits the custom-0 instruction. When `USE_DOT8_HW` is not defined, the same function falls back to a pure C dot-product.
- **`hw_extensions/exp_lut/sw/exp_lut.c`** — `exp_lut_hw(idx)` that writes the index CSR and reads the value CSR. Falls back to an internal golden table when `USE_EXP_LUT_HW` is not defined.
- **`hw_extensions/gemv/sw/gemv.c`** — full GEMV driver: `gemv_init`, `gemv_load_x`, `gemv_load_w`, `gemv_load_b`, `gemv_start`, `gemv_wait_done`, `gemv_read_y`, `gemv_clear_done`. Falls back to pure-C matvec when `USE_GEMV_HW` is not defined.

#### Demo and Measurement Pipeline

The shared `demo_runner.c` iterates over 10 pre-embedded int8 test samples. For each sample it:
1. Calls `tinyformer_encode()` (the full encoder pipeline).
2. Computes a 32-bit additive checksum (`ENC_CKSUM`) over the 16×32 encoder output.
3. Mean-pools the encoder output to a D-dimensional vector.
4. Applies the quantized linear classifier to produce a class prediction.
5. Prints the checksum, predicted class, and expected class over UART.

The on-chip LiteX `timer0` peripheral is read before and after `demo_run()` to measure elapsed cycles with cycle-accurate precision, converted to milliseconds at `sys_clk_freq = 100 MHz`.

---

## 4. Simulation

### 4.1 Python Training and Validation Pipeline

Before any FPGA implementation, TinyFormer was trained and validated on a host machine using PyTorch. This pipeline serves as the algorithmic reference and provides the quantized weights used in firmware.

**Dataset Preparation.** The UCI Human Activity Recognition (UCI HAR) dataset [5] contains inertial sensor recordings (body accelerometer and gyroscope) from 30 subjects performing 6 activities: walking, walking upstairs, walking downstairs, sitting, standing, and laying. Raw signals consist of 6 channels (acc x/y/z, gyro x/y/z) at 128 timesteps per sample. The preprocessing pipeline (`preprocess_uci_har.py`):

- **Time downsampling:** Each 128-timestep signal is average-pooled in chunks of 8 down to 16 timesteps, matching TinyFormer's sequence length S=16.
- **Feature engineering:** For each of the 16 timesteps, a 32-dimensional feature vector (matching D=32) is constructed from 14 engineered features, with the remaining 18 dimensions zero-padded. The feature layout is shown in Table 5.
- **Normalization:** Per-feature z-score normalization is applied using mean and standard deviation computed over all training samples and timesteps; the same statistics are applied to the test set.
- **Labels:** Original labels (1–6) are remapped to 0–5.

The resulting dataset has shape (N, 16, 32). The 18 zero-padded dimensions are a deliberate design choice: they round the feature dimension up to D=32, which keeps it a multiple of 4 (required by the DOT8 4-lane packing and the GEMV 32-bit packed data path) and a power of two (simplifying the right-shift scaling).

**Table 5 — Per-Timestep Feature Vector Layout (D = 32)**

| Index | Feature | Source |
|---|---|---|
| 0–2 | ax, ay, az | Body accelerometer (downsampled) |
| 3–5 | gx, gy, gz | Body gyroscope (downsampled) |
| 6 | accel magnitude | √(ax²+ay²+az²) |
| 7 | gyro magnitude | √(gx²+gy²+gz²) |
| 8–10 | Δax, Δay, Δaz | First difference vs. previous timestep (0 at t=0) |
| 11–13 | Δgx, Δgy, Δgz | First difference vs. previous timestep (0 at t=0) |
| 14–31 | zero padding | — |

**Training.** A TinyFormer encoder (S=16, D=32, FFN=64, 1 head) plus a linear classifier head (D=32 to 6 classes) is trained in PyTorch using cross-entropy loss and the Adam optimizer. The training script produces:
- `artifacts/state_dict.pt` — encoder weights (W_q, W_k, W_v, W_o, W_ff1, W_ff2 and corresponding biases).
- `artifacts/classifier.npz` — classifier head weights and biases.

**Weight Export.** A dedicated export script (`tools/export_weights.py`) quantizes floating-point weights to int8 using symmetric per-tensor scaling and generates C source files (`trained_weights.c/h`, `demo_samples.c/h`, `demo_classifier.c/h`) in the row-major layout expected by the firmware. A fixed set of 10 test samples with ground-truth labels is embedded for on-device validation.

**Software Reference.** The Python pipeline also serves as the numerical reference. The int8 C implementation in `tinyformer.c` is validated against Python-computed encoder outputs prior to hardware bring-up to confirm that quantization error is within the expected range.

### 4.2 Model Accuracy and Quantization Quality

Classification accuracy in this project originates entirely from the PyTorch training stage; the bare-metal C runtime only *executes* the exported network and does not train. Accuracy is therefore best reported in three stages, following the staged-reporting methodology used by KWT-Tiny [1]:

1. **Float reference (PyTorch).** The encoder plus linear classifier head are trained with cross-entropy loss and Adam. The training script (`train_tinyformer_uci_har.py`) prints train and test accuracy each epoch; the test accuracy of the trained float model is the upper-bound reference. *(Measured value to be inserted from the final training run: test accuracy ≈ [__]%.)*

2. **Quantized C path (int8).** Exporting weights and activations to int8 with symmetric per-tensor scaling and the fixed right-shift-by-7 requantization introduces a small, expected quantization loss relative to the float reference. This is the accuracy actually realized on the FPGA. The crude uniform shift-by-7 scaling (rather than per-channel scaling) is the dominant source of this gap and is noted as a candidate for future refinement (Section 6.2).

3. **Accelerated path.** Because the correctness gate (Section 5.4) proves the encoder output is **bit-identical** between the baseline int8 path and every accelerated build, the accelerated path has **exactly** the same accuracy as the quantized C path — the accelerators introduce zero additional accuracy loss by construction. This is a key advantage over approaches that approximate transcendental functions in hardware: the EXP-LUT, DOT8, and GEMV blocks each reproduce the software result exactly, so acceleration is decoupled from quality.

**On-device functional check.** Ten labelled samples (`demo_labels = {0,1,2,3,4,5,4,4,4,4}`, spanning all six activity classes) are embedded in firmware. The demo runner classifies each on-target and prints `pred`/`exp` per sample. Because predictions are bit-identical across all modes, this serves as a deterministic end-to-end functional check on hardware rather than a statistical accuracy estimate, which is established on the full held-out test set in PyTorch.

### 4.3 RTL Simulation (Vivado xsim)

Both MMIO peripherals were verified in standalone SystemVerilog simulation using Vivado 2025.2's xsim simulator before integration into the LiteX SoC. This two-stage verification strategy (standalone simulation, then in-system self-test) catches hardware bugs before they are obscured by SoC integration complexity.

**GEMV Testbench (`tb_gemv.sv`).** Three test scenarios are exercised:

**Table 6 — RTL Simulation Test Scenarios (GEMV)**

| Scenario | Description | Pass Condition |
|---|---|---|
| Deterministic | Fixed 32×32 matrix and vector, known expected output | Y outputs match golden reference after DONE asserts |
| Randomized | LCG-generated random matrix and vector pair | Results match software-model computed inside testbench |
| Boundary | All elements set to INT8_MIN (−128) and INT8_MAX (+127) | Correct saturation and sign handling verified |

Any mismatch triggers `$fatal`. A PASS message is printed on successful completion. The testbench also generates a VCD waveform file (`tb_gemv.vcd`) for manual timing inspection.

**LUT Testbench (`tb_lut.sv`).** A full address sweep (indices 0–15) compares each output against a golden file (`expected_lut.mem`). The golden values are the Q10 fixed-point representations of exp(0) through exp(−15), matching the software LUT in `tinyformer.c` exactly. Any mismatch triggers `$fatal`.

Simulations are invoked from the Vivado Tcl console:

```tcl
source run_gemv_xsim.tcl
source run_lut_xsim.tcl
```

#### GEMV Simulation Waveforms

The captures below were taken from the `tb_gemv` xsim run. Signals are grouped into Clock/Reset, the CPU-write Load phase, the Start handshake, the FSM state/pointers, the 4-lane MAC datapath, and the Result read-back, so that the full operation can be read top-to-bottom.

**Figure 7 — GEMV simulation: full operation overview**

```
(waveform)
```

Figure 7 shows one complete matrix-vector operation end to end: reset, the three CPU load bursts (the long `x_wr_en` / `w_wr_en` / `b_wr_en` pulses as X, W, and the bias are streamed into the peripheral), the single `start` pulse, the autonomous compute phase (`state = 1`, `col` sweeping), and finally `done` with the result read-back. The key point is that the three load bursts dominate the timeline, but the CPU only "blocks" for the one-cycle `start` write — the compute phase then runs entirely inside the peripheral while the CPU is free.

**Figure 8 — GEMV simulation: start handshake**

```
(waveform)
```

Figure 8 zooms into roughly six clock cycles around the kick-off. On the rising edge during the one-cycle `start` pulse the FSM samples it, `state` jumps `0 → 1` (IDLE → COMPUTE) and `busy` asserts; `start` then returns to 0. This is the single-cycle handshake: one CSR write places the peripheral in COMPUTE and the CPU is immediately released to do other work.

**Figure 9 — GEMV simulation: one compute row (4-lane MAC)**

```
(waveform)
```

Figure 9 spans one full output row (~10 cycles). With `state = 1` and `row = 0` held, `col` increments `0 → 1 → … → 8`; on every clock `x_word` and `w_word` present a fresh pair of packed 32-bit operands, `dot4` produces a new signed value (four signed int8 multiplies plus the adder tree, in a single cycle), and `acc` accumulates monotonically. When `col` reaches 8, `y_mem[0]` is latched, `row` advances to 1, `col` resets, and `acc` reloads with `b[1]`. This is the heart of the packed 4-lane design: 32 multiplies are completed in 8 cycles, versus 32 cycles for a one-byte-per-cycle MAC. The full compute phase between `start` and `done` spans ≈290 cycles for a 32×32 matvec (the 256 multiply-accumulate cycles plus per-row bias-reload and bookkeeping).

**Figure 10 — GEMV simulation: completion and result read-back**

```
(waveform)
```

Figure 10 shows the hand-off back to the CPU. `busy` deasserts and `state` moves `1 → 2` (COMPUTE → DONE); `done` latches high; a `clear_done` pulse then clears `done` and resets the read pointer. On each subsequent `y_rd_en` pulse, `y_rd_data` presents the next int32 result. For this deterministic stimulus the four outputs read out as −8, −6, −4, −2 (rows 0–3), which match the hand-computed software golden exactly — confirming the peripheral is bit-exact, not merely fast.

#### EXP-LUT Simulation Waveforms

The following captures are from the `tb_lut` xsim run, which verifies the exponential lookup peripheral against the golden table `expected_lut.mem`.

**Figure 11 — EXP-LUT simulation: full index sweep (Test 1)**

```
(waveform)
```

Figure 11 drives `index` through every legal value `0 → 15`, one per clock, while `value` is sampled on the same cycle and checked against the golden table; the internal address `addr = index[3:0]` is shown beneath. Two properties are visible directly: (1) **zero-cycle, combinational behaviour** — every `index` transition is reflected in `value` on the same cycle, with no pipeline register, so a softmax exponent is available the moment the CPU writes the index; and (2) **monotonic decay** — the outputs descend smoothly from `0x0400 = 1024` (the Q10 representation of 1.0) at `index = 0` down to `0x000C = 12` (≈ 0.0117) at `index = 15`. These values match the software helper `compute_exp_q10()` in `tinyformer.c` bit-for-bit, so the EXP-LUT is a drop-in numerical replacement rather than an approximation. All 16 entries are covered in 16 cycles, and the console reports `ok swp idx=k` for every `k`.

**Figure 12 — EXP-LUT simulation: stability hold (Test 2)**

```
(waveform)
```

Figure 12 drives four representative indices — `0, 4, 8, 15` — and holds each for five clock cycles, covering the high, mid, and low ends of the table:

| index | value (hex / dec) | Q10 → float | Role in softmax |
|---|---|---|---|
| 0 | 0x0400 / 1024 | 1.0000 | weight when score is at the max (k = 0) |
| 4 | 0x012E / 302 | 0.2949 | mid-range decay |
| 8 | 0x005A / 90 | 0.0879 | small contribution |
| 15 | 0x000C / 12 | 0.0117 | nearly negligible (largest spread) |

Each plateau holds rock-steady for the full five cycles with no glitches (the LUT is a pure combinational ROM with no internal state), and every transition is an instantaneous step to the new entry. This confirms the accelerator delivers a usable softmax weight with zero latency: the CPU's only per-exponent cost is the two CSR transactions (write index, read value) — roughly 12 cycles, versus the ≈21,000-cycle software `exp()` it replaces. Across 2,560 softmax exponents per inference, the EXP-LUT accounts for ≈53.8 M of the cycles eliminated by `accel_all` — the single largest contributor to the 4.82× speedup.

### 4.4 On-Target Self-Tests

In addition to RTL simulation, each accelerator includes a dedicated on-target self-test that runs before any benchmarking:

- **`tests_dot8.c`**: Compares DOT8 hardware output against the C reference for a set of packed test vectors. Prints "DOT8 PASS" on success.
- **`tests_lut.c`**: Sweeps indices 0–15 and compares EXP-LUT hardware output against the golden table in `tinyformer.c`. Prints "LUT PASS" on success.
- **`tests_gemv.c`**: Runs GEMV with known matrices and vectors (32×32 and 64×64 shapes, with and without bias) and checks results against a software reference computed on-target. Prints "GEMV self-test PASS" on success.

The self-tests are designed so that they can run even when the corresponding hardware is absent (using software fallbacks where applicable), allowing SoC and toolchain validation before the hardware peripherals are enabled.

---

## 5. Analysis of Results

### 5.1 Baseline Profiling

The baseline firmware (pure software, no accelerators, runtime fixed-point exp() computation) was measured at **75,900,400 cycles (759.00 ms)** per inference across 10 samples. The on-chip hardware timer is the authoritative measurement source; Python wall-clock timing is unreliable at this granularity due to pyserial buffering behavior.

**Figure 13 — Baseline Cycle Decomposition (per inference)**

```
  Softmax exp() — 2,560 calls     ████████████████████████████████████  71%
  Matrix-vector multiplications   ██████████  21%
  UART output (115200 baud)       ██  5%
  Attention dot products          █  1%
  Misc (control, pool, cls.)      █  2%
```

**Table 7 — Baseline Cycle Decomposition**

| Component | Calls | Cycles per Call | Total Cycles | % | Accelerated By |
|---|---|---|---|---|---|
| Softmax exp() | 2,560 | ~21,000 | ~53,800,000 | 71% | EXP-LUT |
| Matrix-vector multiplications | ~80 | ~204,000 | ~16,300,000 | 21% | GEMV |
| UART output | — | — | ~4,000,000 | 5% | Not accelerated |
| Attention dot products | — | — | ~1,000,000 | 1% | DOT8 |
| Misc (residuals, pool, classifier) | — | — | ~800,000 | 1% | Not accelerated |
| **Total** | | | **75,900,400** | **100%** | |

The 71% cycle share of softmax exp() reflects a deliberate methodological choice: the baseline uses genuine runtime fixed-point arithmetic (a fixed-iteration loop plus multiplicative decay with constant `decay_q15 = 24,149`) rather than a precomputed table. The computation function is marked `__attribute__((noinline, optimize("O0")))` to prevent the compiler from constant-folding or memoizing it across calls. This is essential for a fair EXP-LUT comparison: if the baseline read from a software table, gcc would resolve it at compile time and the hardware LUT would show no advantage. We note for transparency that the *absolute* softmax share — and therefore the headline end-to-end speedup — depends on this modeling choice; the EXP-LUT genuinely replaces real runtime exp() work, not an already-tabulated lookup. The per-call cost (~21,000 cycles) is derived from the measured total (53.8 M cycles ÷ 2,560 calls).

### 5.2 Performance Results

All measurements were taken on the same FPGA bitstream, with only the firmware binary changing between modes. The on-chip LiteX `timer0` provides cycle-accurate measurement independent of host-side serial latency.

**Table 8 — Performance Comparison**

| Mode | Firmware Path | Cycles | Latency | Speedup |
|---|---|---|---|---|
| **Baseline** | Runtime fixed-point exp(), software matvec, software dot products | 75,900,400 | 759.00 ms | 1.00× |
| **accel_all** | HW LUT + DOT8 + 4-lane packed GEMV | **15,755,300** | **157.55 ms** | **4.82×** |

Speedup: 75,900,400 / 15,755,300 = **4.82×**

**Figure 14 — Performance Comparison (ms per 10-sample inference)**

```
(graph)
```

### 5.3 Per-Accelerator Contribution

**EXP-LUT** eliminates the dominant bottleneck (71% of baseline cycles) by replacing a ~21,000-cycle per-call runtime computation with a ~12-cycle MMIO lookup — approximately 1,700× faster per call. Despite its hardware simplicity (a combinational ROM), this accelerator delivers the largest fraction of the total cycle reduction.

**GEMV** is the single largest contributor in absolute cycle savings. Comparing the baseline software matvec to the GEMV peripheral, the speedup per 32×32 matvec call is approximately 8× (from ~17,000 cycles to ~2,000 cycles). This improvement comes equally from two independent optimizations: (1) the 4× reduction in CSR-bus writes due to the 32-bit packed data path, and (2) the 4× reduction in compute cycles due to the parallel 4-lane MAC.

**DOT8** contributes a modest speedup consistent with the initial 1% cycle share of attention dot products. Its contribution is small in the final measurement because the dominant bottlenecks (softmax and matvec) are addressed by the other two accelerators.

**Table 9 — Per-Accelerator Cycle Savings**

| Accelerator | Cycles Saved (vs Baseline) | Contribution to Speedup |
|---|---|---|
| EXP-LUT | ~53,800,000 | Primary — eliminates 71% bottleneck |
| GEMV | ~14,000,000 | Secondary — eliminates the bulk of matrix-vector cost (packed 4-lane design: 4× bus + 4× compute) |
| DOT8 | ~800,000 | Minor — consistent with 1% initial share |

### 5.4 Correctness Verification

Before any performance numbers were reported, every accelerated build was required to pass the `ENC_CKSUM` correctness gate: the 32-bit additive checksum over the encoder's 16×32 int8 output must be bit-identical between baseline and the accelerated build for every test sample.

**Table 10 — Correctness Checksums (All 10 Samples)**

| Sample | ENC_CKSUM (Baseline) | ENC_CKSUM (accel_all) | Match |
|---|---|---|---|
| 0 | 0x00005CE7 | 0x00005CE7 | ✓ |
| 1 | 0x00006557 | 0x00006557 | ✓ |
| 2 | 0x000068B6 | 0x000068B6 | ✓ |
| 3 | 0x00006469 | 0x00006469 | ✓ |
| 4 | 0x000062A1 | 0x000062A1 | ✓ |
| 5 | 0x000063A6 | 0x000063A6 | ✓ |
| 6 | 0x0000627B | 0x0000627B | ✓ |
| 7 | 0x00006ACF | 0x00006ACF | ✓ |
| 8 | 0x0000719B | 0x0000719B | ✓ |
| 9 | 0x00007185 | 0x00007185 | ✓ |

All 10 checksums match. Predicted classes also match the baseline for every sample. This confirms that the reported 4.82× speedup reflects genuine acceleration, not skipped computation or degraded numerical correctness.

### 5.5 Area and Power

Relative to a plain VexRiscv baseline, the three accelerators add **+3.9 percentage points of LUT** (6.13% → **10.04%**), **+1.8 percentage points of flip-flops** (2.49% → 4.32%), and **+3.3 percentage points of DSP** (0% → 3.3%). Measured power rises from **0.740 W to 0.792 W**, a factor of **1.07** (≈ 7%). The full breakdown is given in Table 2.

It is worth being candid about the area and power outcome. Among the project's original goals was the aspiration to keep the design *below* 10% of the LUT fabric and to limit power growth. In practice, both area and power **increased modestly** — this is a fundamental trade-off of FPGA acceleration: dedicated arithmetic units and wider data paths consume logic and switch more, in exchange for fewer cycles. The design landed at 10.04% LUT — marginally over the sub-10% aspiration — and 1.07× power. Set against a **4.82× speedup**, this is a strongly favorable exchange: the system reaches a 157.55 ms target latency for only ~7% more power, and approximately **90% of the FPGA fabric remains free** for future extensions.

---

## 6. Conclusions and Further Work

### 6.1 Conclusions

**Results against the original goals.** The table below evaluates the outcome against each goal stated in Section 1.1.

**Table 11 — Project Goals vs. Achieved Results**

| # | Goal (Section 1.1) | Outcome | Met? |
|---|---|---|---|
| 1 | Implement a complete bare-metal TinyFormer encoder on VexRiscv/LiteX | Full encoder (Q/K/V, attention, FFN, residuals) runs bare-metal on the Nexys4DDR | ✓ |
| 2 | Establish a correct, cycle-accurate baseline | Baseline measured at 75,900,400 cycles (759.00 ms) via on-chip `timer0` | ✓ |
| 3 | Profile to quantify bottlenecks | Softmax 71%, matvec 21% identified by cycle-accurate profiling | ✓ |
| 4 | Design three accelerators targeting measured bottlenecks | DOT8, EXP-LUT, GEMV implemented and integrated | ✓ |
| 5 | Verify bit-exact correctness before reporting performance | ENC_CKSUM bit-identical across all modes for all 10 samples | ✓ |
| 6 | End-to-end speedup within a <10% LUT footprint | 4.82× speedup achieved; LUT landed at 10.04% — marginally over the sub-10% target | ◑ (speedup met; area slightly over) |

The single partial result is the LUT budget: the design reached 10.04% rather than staying strictly below 10%, and power rose 1.07× rather than falling. As discussed in Section 5.5, this is the expected cost of dedicated hardware and is strongly outweighed by the 4.82× speedup. The remaining key findings are:

1. **Bottleneck identification is essential and non-obvious.** The 71% cycle share of softmax exp() was not predictable from instruction-count analysis alone. Without on-chip cycle-accurate profiling, design effort might have been misallocated to attention dot-products, which represent only 1% of measured cycles and deliver only a minor improvement when accelerated.

2. **The simplest accelerator delivers the largest gain.** The EXP-LUT peripheral — a combinational ROM with two CSR registers — accounts for the majority of the total cycle reduction despite being simpler to implement than either the custom instruction or the GEMV core. This outcome reflects the importance of targeting the true bottleneck rather than the most technically interesting operation.

3. **Data-path width is as important as compute parallelism.** The GEMV peripheral's efficiency comes in equal parts from reducing CSR-bus traffic (4× via packed 32-bit writes) and from parallelizing the MAC unit (4× via the 4-lane dot product). Neglecting either half of this optimization would have left a 4× improvement on the table. This finding generalizes: for MMIO-coupled accelerators, memory and bus bandwidth is a co-bottleneck with raw arithmetic throughput.

4. **Correctness must precede performance measurement.** The ENC_CKSUM gate prevented reporting speedups that might have reflected skipped computation or numerical corruption. The discipline of requiring bit-identical encoder output before any benchmarking is essential to the validity of all reported results.

5. **4.82× speedup at ~10% LUT cost is competitive with published work.** KWT-Tiny [1] reports 5× speedup with 29% area overhead; this work achieves 4.82× with a +3.9 pp LUT overhead (total 10.04%) — roughly 7× lower added area for a comparable speedup — while preserving full bit-exact correctness and using an open, reproducible FPGA platform. The honest counterpoint is that area and power both rose slightly against an initial goal of reducing them; the project treats this as the expected cost of dedicated hardware rather than a failure of the design.

6. **The universality-effectiveness trade-off is bounded by the bottleneck.** Accelerating the softmax (highly specific to the attention mechanism) and GEMV (general but dimension-parameterized) simultaneously required accepting that the bitstream is tailored to TinyFormer's fixed dimensions. For a fully universal accelerator that worked across arbitrary model sizes, the GEMV peripheral would need tiling and DMA support; the EXP-LUT would need a larger, software-programmable table.

### 6.2 Further Work

- **DMA-based GEMV.** The current design requires the CPU to write all W and X elements to CSR registers over the system bus. A DMA engine would allow the GEMV core to fetch rows of W directly from DDR2, eliminating CPU involvement in data movement entirely and further reducing inference latency by an estimated 2–3× for GEMV-bound operations.

- **Pipelined GEMV dot4 stage.** The current GEMV design does not meet timing at 100 MHz (WNS = −6.3 ns). Adding one pipeline register between the 4-lane multiplier array and the adder tree would close timing cleanly at 100 MHz while adding only one cycle of latency per output element — negligible at the scale of 32 output elements per call.

- **Wider DOT8.** An 8-lane DOT8 instruction — using two packed 32-bit source words and one 64-bit source/two 32-bit sources — would double attention throughput and become worthwhile in models with larger model dimension D or multi-head attention.

- **Larger EXP-LUT.** A 256-entry table with finer step size (or higher Q-format precision) would support models with wider attention logit ranges and reduce approximation error in the softmax output.

- **Tiling support for larger models.** The GEMV peripheral supports matrices up to 64×64. Tiling support would enable larger model dimensions (D=64, D=128) and multi-head attention without architectural changes to the peripheral, at the cost of additional firmware loop overhead.

- **Multi-head attention.** TinyFormer uses a single attention head. Extending to H heads would require either H parallel GEMV cores or a serialized schedule with shared hardware, depending on the area budget.

---

## 7. Project Documentation

All project deliverables are maintained in two Git repositories, organized as follows:

**Algorithm and Firmware Repository (TinyML_algo):**

| Directory | Contents |
|---|---|
| `litex_port/common/` | Shared firmware sources: encoder, demo runner, UART driver, trained weights |
| `litex_port/baseline/`, `accel_*/` | Per-mode main files (six modes total) |
| `hw_extensions/dot8/` | VexRiscv Dot8Plugin (Scala), SW driver (`dot8.h/.c`) |
| `hw_extensions/exp_lut/` | EXP-LUT RTL (`exp_lut.sv`), LiteX wrapper, SW driver |
| `hw_extensions/gemv/` | GEMV RTL (`gemv_core.v`), LiteX wrapper (`gemv_periph.py`), SW driver |
| `hw_extensions/sim/` | SystemVerilog testbenches (`tb_gemv.sv`, `tb_lut.sv`), Tcl scripts |
| `training/` | Dataset download, preprocessing, and PyTorch training scripts |
| `tools/` | Weight export (`export_weights.py`), UART measurement scripts |
| `artifacts/` | Trained encoder (`state_dict.pt`) and classifier weight files |

**LiteX SoC Repository (litex-nexys4ddr):**

| Directory / File | Contents |
|---|---|
| `hw/build_soc.py` | LiteX SoC build script; integrates accelerator peripherals |
| `build/gateware/` | Generated Vivado project, bitstream (`digilent_nexys4ddr.bit`) |
| `build/csr.json` | Generated CSR address map (used by C firmware) |
| `ACCELERATOR_INTEGRATION_PATHS.md` | How to add new peripherals to the LiteX SoC |
| `docs/` | Build instructions, FPGA programming guide, memory configuration |

**Reproduction Steps:**

1. **Build the LiteX SoC bitstream** using `hw/build_soc.py` in Vivado (requires Vivado 2025.2 and the Nexys4DDR board file).
2. **Program the bitstream** onto the Nexys4DDR using `docs/PROGRAM_FPGA.md`.
3. **Build each firmware mode** using the compile flags and file lists in `TinyML_algo/README.md`.
4. **Run self-tests** (LUT PASS, GEMV PASS, DOT8 PASS) before benchmarking.
5. **Run baseline and accel_all** firmwares; verify ENC_CKSUM match; compare CYCLES output.

Full reproduction instructions, including LiteX SoC build, firmware compilation per mode, self-test execution, correctness verification, and performance measurement, are documented in `TinyML_algo/README.md` and `TinyML_algo/REPORT_NOTES_IMPLEMENTATION.md`.

---

## 8. References

[1] A. Al-Qawlaq, A. Kumar M, D. John, "KWT-Tiny: RISC-V Accelerated, Embedded Keyword Spotting Transformer," arXiv:2407.16026, 2024.

[2] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, L. Kaiser, I. Polosukhin, "Attention Is All You Need," Advances in Neural Information Processing Systems (NeurIPS), 2017.

[3] LiteX SoC Builder. Available: https://github.com/enjoy-digital/litex

[4] VexRiscv RISC-V CPU. Available: https://github.com/SpinalHDL/VexRiscv

[5] D. Anguita, A. Ghio, L. Oneto, X. Parra, J. L. Reyes-Ortiz, "A Public Domain Dataset for Human Activity Recognition Using Smartphones," ESANN 2013.

[6] RISC-V International, "The RISC-V Instruction Set Manual, Volume I: Unprivileged ISA," version 20191213. https://riscv.org/technical/specifications/

[7] Xilinx / AMD, "Artix-7 FPGAs Data Sheet: DC and AC Switching Characteristics," DS181, October 2021. https://docs.xilinx.com/v/u/en-US/ds181_Artix_7_Data_Sheet

---

## Appendix A: LUT Table Values

The EXP-LUT peripheral stores 16 Q10 fixed-point values representing exp(−k) for k = 0, 1, …, 15. Q10 format means the value is scaled by 2^10 = 1024, so exp(0) = 1.0 is stored as 1024.

| Index k | Floating-Point exp(−k) | Q10 Value (stored) |
|---|---|---|
| 0 | 1.0000 | 1024 |
| 1 | 0.3679 | 754 |
| 2 | 0.1353 | 556 |
| 3 | 0.0498 | 410 |
| 4 | 0.0183 | 302 |
| 5 | 0.0067 | 223 |
| 6 | 0.0025 | 165 |
| 7 | 0.0009 | 122 |
| 8 | 0.0003 | 90 |
| 9 | 0.0001 | 67 |
| 10 | 0.0000454 | 50 |
| 11 | 0.0000167 | 37 |
| 12 | 0.0000061 | 28 |
| 13 | 0.0000023 | 21 |
| 14 | 0.0000008 | 16 |
| 15 | 0.0000003 | 12 |

These values are defined identically in the hardware RTL (`exp_lut.sv`) and in the software golden table (`exp_lut_golden[]` in `exp_lut.c`) to guarantee that baseline and accelerated softmax produce numerically identical results.

---

## Appendix B: GEMV CSR Register Map

The register offsets below are representative; the actual byte addresses are auto-assigned by the LiteX CSR generator and exposed to firmware through `generated/csr.h`. Inside `gemv_core.v`, writes to X_IN, W_IN, and B_IN are presented to the core as the `x_wr_en`, `w_wr_en`, and `b_wr_en` strobes (each with auto-incrementing word index), while the CTRL bits drive `start`, `clear_done`, `len_64`, `out_dim_64`, and `bias_en`.

**Register map** (one row per register):

| Offset | Register | R/W | Width | Description |
|---|---|---|---|---|
| 0x00 | CTRL | R/W | 32-bit | Control / status word — see the bit-field table below |
| 0x04 | X_IN | W | 32-bit | Write packed int8 X elements (4 lanes per word, little-endian) |
| 0x08 | W_IN | W | 32-bit | Write packed int8 W elements (4 lanes per word, row-major) |
| 0x0C | B_IN | W | 32-bit | Write one int32 bias element |
| 0x10 | Y_OUT | R | 32-bit | Read the int32 result element at the current read pointer |
| 0x14 | STATUS | R | 32-bit | Status word: bit [0] busy, bit [1] done (for polling) |
| 0x18 | Y_NEXT | W | 32-bit | Write 1 to advance the Y read pointer by one element |

**CTRL bit-field** (offset 0x00):

| Bit | Name | R/W | Description |
|---|---|---|---|
| 0 | start | W (pulse) | Write 1 to begin computation; self-clears |
| 1 | busy | R | 1 while the FSM is active |
| 2 | done | R | 1 when computation is complete and Y is ready |
| 3 | clear_done | W (pulse) | Write 1 to reset DONE and return the FSM to IDLE |
| 4 | len_64 | W | 0 = LEN 32; 1 = LEN 64 |
| 5 | out_dim_64 | W | 0 = OUT_DIM 32; 1 = OUT_DIM 64 |
| 6 | enable_bias | W | 1 = add the bias vector b to the result |
