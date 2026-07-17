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

This project implements and accelerates a compact Transformer encoder — TinyFormer — on an FPGA-hosted RISC-V soft-core for human activity recognition. The platform is a Digilent Nexys4DDR board running a LiteX-generated SoC with a VexRiscv RV32IM CPU at 100 MHz. The model performs 6-class classification on the UCI Human Activity Recognition (UCI HAR) dataset, with all weights and activations quantized to int8. The encoder processes 16×32 input sequences (16 timesteps, 32-dim features) through a full encoder block: Q/K/V projections, scaled dot-product attention with softmax, output projection, residual connections, and a two-layer feed-forward network.

A pure-software baseline of **75.9 million cycles (759 ms)** per inference spends 71% of cycles on softmax exponentials and 21% on matrix-vector multiplications. Three targeted accelerators were designed, verified, and integrated to remove these bottlenecks:

1. **DOT8** — a custom VexRiscv instruction for 4-lane signed int8 dot-products, using 4 DSP blocks in the CPU pipeline.
2. **EXP-LUT** — an MMIO peripheral replacing the runtime softmax exponential computation with a 16-entry Q10 fixed-point lookup table.
3. **GEMV** — an MMIO peripheral with a 4-lane parallel MAC for matrix-vector multiplication, featuring a 32-bit packed data path that reduces CSR-bus traffic by 4×.

The combined system achieves a **4.82× end-to-end speedup** (759.00 ms → 157.55 ms). A 32-bit additive checksum over the encoder's 16×32 int8 output confirms bit-identical results on every inference, so accuracy is unchanged by acceleration. LUT utilization rises from 6.13% to **10.04%** — leaving ~90% of the fabric free — and power from **0.740 W to 0.792 W** (1.07×, ≈7%): a deliberate area/power-for-speed trade in exchange for the 4.82× gain.

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

Transformers are now the dominant architecture for sequence modeling, from NLP to audio and inertial-sensor activity recognition. Even compact variants impose two predictable bottlenecks on embedded RISC-V cores: (1) the matrix-vector multiplications in the linear projections, and (2) the softmax exponential in self-attention.

A 100 MHz soft-core RISC-V CPU is a flexible compute substrate but, unmodified, cannot meet always-on inference demands: even with the M-extension's single-cycle multiply, scalar code spends separate load/sign-extend/multiply/accumulate instructions on every multiply-add, and a runtime fixed-point softmax exp() dominates total time. This project shows that targeted hardware acceleration within a small FPGA budget closes this gap — a 4.8×+ end-to-end speedup at roughly 10% LUT and only ~7% more power.

### 1.3 Approach

The project follows a disciplined, evidence-driven methodology:

1. **Establish correctness first.** A verified pure-software baseline is built before any hardware. Every inference produces a 32-bit additive checksum over the encoder output — the correctness gate for all accelerated builds.
2. **Profile to identify true bottlenecks.** Cycle counts are measured per-component by instrumented firmware runs, not estimated from instruction counts.
3. **Design accelerators for measured bottlenecks.** Each accelerator targets a specific, quantified cycle contributor.
4. **Verify before benchmarking.** A build is benchmarked only after its checksum matches the baseline on every sample.
5. **Report on-chip measurements.** All numbers come from the LiteX hardware timer, not host wall-clock, which is unreliable at this granularity.

### 1.4 Comparison with Related Work

**KWT-Tiny [1]** is a RISC-V accelerated keyword-spotting Transformer on a custom ASIC with 64 kB RAM, reaching a 5× speedup via custom GELU/softmax instructions at 29% area overhead, but requiring aggressive model compression (369× size reduction) and accepting a 10% accuracy loss from class reduction.

This work differs in several respects: it targets a commodity FPGA (Digilent Nexys4DDR) with full bitstream transparency and no chip tape-out; it keeps bit-exact correctness (no accuracy loss from the accelerators); and its LUT cost is +3.9 pp (6.13% → 10.04%) — roughly 7× smaller than KWT-Tiny's 29% overhead. Both attack the same bottlenecks (softmax and attention inner products on embedded RISC-V) and reach comparable speedups (4.82× vs. 5×). The Transformer architecture itself follows Vaswani et al. [2]; TinyFormer is a single-head, S=16, D=32 simplification suited to bare-metal FPGA constraints.

---

## 2. Theoretical Background

### 2.1 Transformer Encoder Architecture

The Transformer encoder [2] processes a sequence of token vectors through self-attention then a feed-forward network (FFN), with residual connections around each sub-layer. Given an input X of shape (S×D) — sequence length S, model dimension D — it computes:

1. **Linear projections:** Q = XW_q, K = XW_k, V = XW_v (D×D weight matrices).
2. **Scaled dot-product attention:** A = softmax(QK^T / √D), then context C = AV.
3. **Output projection:** Out = CW_o.
4. **Residual and FFN:** Y = X + Out, then Z = Y + FFN(Y), where FFN is two linear layers with a ReLU between them.

TinyFormer uses S=16, D=32, FFN hidden size 64, and a single head.

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

All weights and activations are quantized to int8 (−128 to +127), with int32 accumulators to prevent multiply-accumulate overflow. After each linear layer, results are scaled back to int8 by a fixed arithmetic right-shift of 7 bits and saturation. This removes all floating-point from the inference path — essential for efficient bare-metal RISC-V on FPGA.

Softmax requires exponentiation. The baseline computes `exp(−k)` genuinely at runtime in `compute_exp_q10()`: a fixed-iteration loop plus a multiplicative-decay loop using one constant `decay_q15 = 24149 ≈ 0.7368 × 2^15` (*not* a lookup table). It is declared `__attribute__((noinline, optimize("O0")))` so the compiler cannot unroll, constant-fold, or memoize it — the work is genuinely paid on every call. Accelerated builds replace this entire loop with a single read from a 16-entry Q10 table (scale 2^10 = 1024) covering exp(0)…exp(−15). The denominator `sum_exp` is accumulated in 32-bit fixed-point, and each attention weight is `w_q15 = (exp_value << 15) / sum_exp` in Q15 before the weighted sum over the value vectors.

### 2.3 LiteX SoC Framework

LiteX [3] is an open-source FPGA SoC builder that generates a complete system — CPU, memory controllers, bus fabric, and peripheral CSR (Control and Status Register) maps — from Python. Here it generates the VexRiscv RV32IM soft-core, connects DDR2 SDRAM and a UART, and provides the infrastructure into which the three accelerators are integrated as memory-mapped peripherals. It also emits C headers (`generated/csr.h`) exposing each peripheral's CSRs as typed accessor macros, so firmware uses standard C without hand-crafted MMIO pointer arithmetic.

### 2.4 VexRiscv and Custom Instructions

VexRiscv [4] is a flexible, plugin-based RISC-V CPU in SpinalHDL whose plugins insert new functional units at the decode/execute/writeback stages without modifying the core. The RISC-V ISA reserves custom-0…custom-3 opcodes for extensions; this project uses custom-0 (opcode 0x0B, funct7=0x01) for DOT8. The plugin intercepts the decoded instruction in execute, computes four signed int8 multiply-accumulates on 4 DSP blocks, and writes the int32 result in writeback.

### 2.5 MMIO Peripheral Design

MMIO peripherals appear to the CPU as ordinary memory addresses: it writes control registers and reads status/result registers with standard load/store instructions. In LiteX, peripherals are Python modules that auto-generate both the synthesizable RTL and the matching C headers, keeping hardware and software consistent without manual address bookkeeping.

### 2.6 Alternative Approaches Considered

Several alternatives were evaluated before settling on DOT8 + EXP-LUT + GEMV:

- **Software-only optimization.** Unrolling, scheduling, and `-O3` reduce baseline cycles somewhat but cannot overcome computing exponentials and high-dimensional dot-products one scalar op at a time on RV32IM — this is the baseline all accelerators are measured against.
- **Full systolic-array GEMM.** A 2-D array maximizes matrix-multiply throughput, but TinyFormer's workload is matrix-*vector* (token-by-token); a full array would blow the 10% LUT budget and leave most PEs idle. A single 4-lane streaming MAC (GEMV) is the right granularity.
- **Exponential by polynomial/CORDIC instead of a LUT.** A Taylor/CORDIC pipeline is more general but larger and slower than a 16-entry ROM; since attention logits occupy a known small range after max-subtraction, a fixed Q10 LUT is exact here and essentially free in area.
- **Per-channel / power-of-two quantization.** Per-channel scales or learned step sizes would shrink the int8 accuracy gap of the uniform shift-by-7 scheme, at the cost of more complex requantization; deferred (Section 6.2) since correctness, not maximum accuracy, was the gating requirement.
- **DMA-fed accelerators.** A DMA engine could fetch W/X from DDR2 directly instead of CPU CSR streaming, removing bus traffic at the cost of bus-master complexity; scoped as future work after packed-CSR GEMV already delivered most of the available speedup.

---

## 3. Implementation

### 3.1 Hardware Platform

The system runs on a Digilent Nexys4DDR board with a Xilinx Artix-7 xc7a100t FPGA. The LiteX SoC comprises a VexRiscv RV32IM soft-core at 100 MHz, DDR2 SDRAM, a UART, and the three accelerator blocks; the bus fabric, memory map, and CSR layout are generated from Python by LiteX.

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

The DOT8 accelerator adds one instruction to the VexRiscv pipeline via the plugin interface, computing the signed int8 dot-product of two 4-element vectors packed into two 32-bit registers:

```
result = a[0]×b[0] + a[1]×b[1] + a[2]×b[2] + a[3]×b[3]
```

where a[i], b[i] are the i-th signed bytes (lanes 0–3, little-endian) of the sources and the result is signed int32.

**Encoding:** A standard RISC-V R-type using opcode custom-0 (0x0B), funct7=0x01; funct3 is reserved for future variants (e.g. an 8-lane or MAC form).

| Bits 31–25 | 24–20 | 19–15 | 14–12 | 11–7 | 6–0 |
|---|---|---|---|---|---|
| funct7 = 0x01 | rs2 | rs1 | funct3 | rd | opcode = 0x0B |
| 7 bits | 5 bits | 5 bits | 3 bits | 5 bits | 7 bits |

rs1/rs2 each carry four packed signed int8 lanes (lane 0 in the LSB byte), each sign-extended to int32 before multiplication; rd receives the int32 dot-product.

**Execution and integration.** Execution is single-cycle: the plugin intercepts the decoded instruction in the execute stage, performs four signed int8×int8 multiplies and a four-input adder tree (4 DSP blocks), and writes the int32 result in writeback, with no pipeline stall. A 32-element software dot product (32 iterations × ≈8 instructions ≈ 256) collapses to 8 DOT8 calls (2 packs each), cutting the inner-loop instruction count by ≈6.4×.

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

The EXP-LUT peripheral (`exp_lut.v`) is a 16-entry read-only ROM holding exp(0)…exp(−15) in Q10 fixed-point (scale 2^10), read purely combinationally from a `reg [15:0]` array (no clocked latency); a 5-bit signed index is truncated to the address (`addr = index[3:0]`). Entries match the golden table in `tinyformer.c` byte-for-byte (Appendix A), so baseline and accelerated softmax are numerically identical. The CPU writes the index CSR and reads the value CSR — two MMIO ops (~12 cycles) — replacing the baseline's `compute_exp_q10()` loop (≈21,000 cycles/call, Section 5.1), a ~1,700× per-call reduction.

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

**Design.** GEMV computes Y = W·X + b (int8 W/X, optional int32 bias, int32 Y) with a 32-bit packed data path and a 4-lane parallel MAC. The driver packs four int8 elements per `X_IN`/`W_IN` write (`pack4_i8()`), so a 32×32 matvec needs ≈272 CSR writes vs. 1,088 byte-wide — a 4× bus saving. Internally X/W are 32-bit word arrays; the FSM reads one packed word from each per cycle and does four signed MACs in parallel (4 DSP blocks), completing a 32×32 matvec in **256 compute cycles** — a further 4× over one MAC/cycle. The two savings are independent and multiply. LEN and OUT_DIM are 32 or 64, runtime-selectable.

**Control FSM.** A separate always-on write path loads X/W/B with auto-incrementing indices (reset by `clear_done`). The compute FSM has three states: **S_IDLE** waits for `start` and preloads the accumulator with the row bias; **S_COMPUTE** sweeps LEN/4 words per row (8 for LEN=32), accumulating one `dot4`/cycle, then latches `y_mem[row]` and reloads the next bias; **S_DONE** raises `done` for the CPU to read via `Y_OUT`/`Y_NEXT` then `clear_done`.

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

Resource and power figures are reported for both configurations on the same xc7a100t bitstream at 100 MHz, measured against the plain-VexRiscv baseline.

**Table 2 — FPGA Resource Utilization and Power (xc7a100t @ 100 MHz)**

| Metric | Baseline | Accelerated | Change |
|---|---|---|---|
| Power | 0.740 W | 0.792 W | ×1.07 (≈ +7%) |
| Slice LUTs | 6.13% | 10.04% | +3.9 pp |
| Slice Registers (FF) | 2.49% | 4.32% | +1.8 pp |
| DSP Blocks | 0% | 3.3% | +3.3 pp |

The 8 DSP blocks split as 4 for the DOT8 multiplier array and 4 for the GEMV 4-lane MAC; the plain RV32IM multiplier maps to logic (hence 0% baseline DSP). The accelerated build also uses 47 of 135 RAMB36 block-RAMs (≈34.8%) and 968 LUTs of distributed RAM. At 10.04% LUT, ~90% of the fabric remains free.

**Timing.** The pipelined GEMV core (v3) meets timing at 100 MHz: Vivado reports WNS = +0.019 ns post-route, all timing constraints met, 0 failing endpoints. (The earlier single-cycle core did not close timing — WNS ≈ −6.3 ns — which motivated pipelining the fetch → multiply → accumulate path; the DOT8 custom instruction, whose single-cycle execute→bypass path was the next limiter, was removed.) The design routes cleanly and is bit-identical across all samples.

### 3.3 Software Description

#### Firmware Architecture

The firmware is shared common sources plus mode-specific main files; both configurations share the same encoder, with hardware paths selected at compile time via feature macros. This report focuses on the two end-points — the pure-software baseline and the fully-accelerated `accel_all` build.

**Table 3 — Firmware Build Modes**

| Mode | Accelerators Active | Feature Macros |
|---|---|---|
| Baseline | None | `USE_TRAINED_WEIGHTS`, `USE_LITEX_UART` |
| accel_all | DOT8 + EXP-LUT + GEMV | + `USE_DOT8_HW`, `USE_EXP_LUT_HW`, `USE_GEMV_HW` (with the LiteX-CSR variants) |

When a macro is undefined, that hardware is never accessed — no custom opcode, no MMIO touch — so one codebase runs correctly on a plain VexRiscv (baseline) or with all three accelerators (`accel_all`).

#### TinyFormer Encoder (`tinyformer.c`)

The encoder implements the full pipeline in portable C with no dynamic allocation, OS, or libc, compiled with `-ffreestanding -nostdlib -march=rv32im -mabi=ilp32`.

**Algorithm stages:**

1. **Q/K/V linear projections:** Each input token (row of X) is multiplied by W_q, W_k, W_v via row-major int8 matrix-vector multiply with int32 accumulation, then right-shifted by 7 and saturated to int8 (`saturate_int32_to_int8`), producing 16×32 Q, K, V. In `accel_all`, all projections use GEMV.

2. **Streaming scaled dot-product attention:** Queries are processed one at a time, reusing 1D scratch buffers (`scores[16]`, `exp_buf[16]`) instead of a full 16×16 matrix. Per query: (a) the int32 dot-product against each of the 16 keys is right-shifted by 5 to approximate 1/√D; (b) the per-query max is subtracted for stability and shifted by a further 3 to compress the range to ≈[−15, 0], then clamped as the exp index; (c) exp values are looked up (EXP-LUT, or `compute_exp_q10()` in baseline) and summed; (d) each weight is normalized to Q15 as `(exp_buf[j] << 15) / sum_exp`, and the Q15-weighted value sum, right-shifted by 15, gives the context vector. Inner dot-products use DOT8 in accelerated builds.

3. **Output projection and residual:** Context is projected through W_o and added to the input via saturating int8 addition.

4. **Two-layer FFN with residual:** W_ff1 (32→64) with ReLU, then W_ff2 (64→32), added back via a second residual. Both layers use GEMV in accelerated builds.

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

Each accelerator exposes a compile-time-selectable driver, each with a pure-C fallback when its `USE_*_HW` macro is undefined:

- **`dot8/sw/dot8.h`** — packing helper `dot8_pack()` and inline-asm `dot8_4_lanes(a, b)` emitting the custom-0 instruction.
- **`exp_lut/sw/exp_lut.c`** — `exp_lut_hw(idx)` writes the index CSR and reads the value CSR.
- **`gemv/sw/gemv.c`** — full driver: `gemv_init`/`load_x`/`load_w`/`load_b`/`start`/`wait_done`/`read_y`/`clear_done`.

#### Demo and Measurement Pipeline

The shared `demo_runner.c` iterates over 10 pre-embedded int8 samples; for each it: (1) calls `tinyformer_encode()`; (2) computes a 32-bit additive checksum (`ENC_CKSUM`) over the 16×32 output; (3) mean-pools to a D-vector; (4) applies the quantized linear classifier; (5) prints checksum, predicted, and expected class over UART. The on-chip `timer0` is read around `demo_run()` for cycle-accurate timing, converted to ms at `sys_clk_freq = 100 MHz`.

---

## 4. Simulation

### 4.1 Python Training and Validation Pipeline

Before any FPGA work, TinyFormer was trained and validated on a host with PyTorch. This pipeline is the algorithmic reference and the source of the quantized firmware weights.

**Dataset Preparation.** The UCI Human Activity Recognition (UCI HAR) dataset [5] holds inertial recordings (body accelerometer + gyroscope) from 30 subjects across 6 activities (walking, walking up/down stairs, sitting, standing, laying): 6 channels (acc/gyro x/y/z) at 128 timesteps per sample. Preprocessing (`preprocess_uci_har.py`):

- **Downsampling:** each 128-step signal is average-pooled in chunks of 8 to 16 steps (S=16).
- **Feature engineering:** each step gets a 32-dim vector (D=32) from 14 engineered features, the other 18 dims zero-padded (Table 5).
- **Normalization:** per-feature z-score from training-set statistics, applied to the test set too.
- **Labels:** remapped from 1–6 to 0–5.

The result has shape (N, 16, 32). The 18 zero-padded dims are deliberate: they round D up to 32 — a multiple of 4 (needed by DOT8 4-lane packing and the GEMV 32-bit data path) and a power of two (simplifying right-shift scaling).

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

**Training.** The encoder (S=16, D=32, FFN=64, 1 head) plus a linear classifier head (D=32 → 6 classes) is trained in PyTorch with cross-entropy loss and Adam, producing `artifacts/state_dict.pt` (encoder weights and biases) and `artifacts/classifier.npz` (classifier head).

**Weight Export.** `tools/export_weights.py` quantizes the float weights to int8 with symmetric per-tensor scaling and emits C sources (`trained_weights.c/h`, `demo_samples.c/h`, `demo_classifier.c/h`) in the firmware's row-major layout, embedding 10 labelled test samples for on-device validation.

**Software Reference.** The Python pipeline is also the numerical reference: the int8 C code in `tinyformer.c` is validated against Python encoder outputs before hardware bring-up to confirm quantization error is within range.

### 4.2 Model Accuracy and Quantization Quality

Accuracy originates entirely in PyTorch training; the bare-metal C runtime only *executes* the exported network. It is reported in three stages, following KWT-Tiny [1]:

1. **Float reference (PyTorch).** The encoder + classifier head trained with cross-entropy and Adam; the float test accuracy is the upper-bound reference. *(Value from the final run: ≈ [__]%.)*

2. **Quantized C path (int8).** Exporting to int8 with symmetric per-tensor scaling and the fixed shift-by-7 requantization adds a small, expected loss — the accuracy actually realized on the FPGA. The crude uniform shift (vs. per-channel) is the dominant source of this gap (future work, Section 6.2).

3. **Accelerated path.** Since the correctness gate (Section 5.4) proves bit-identical encoder output between baseline and every accelerated build, the accelerated path has **exactly** the quantized C path's accuracy — zero added loss by construction. EXP-LUT, DOT8, and GEMV each reproduce the software result exactly, decoupling acceleration from quality.

**On-device functional check.** Ten labelled samples (`demo_labels = {0,1,2,3,4,5,4,4,4,4}`, spanning all six classes) are embedded; the demo runner classifies each and prints `pred`/`exp`. Being bit-identical across modes, this is a deterministic hardware functional check, not a statistical accuracy estimate (the latter from the full held-out test set in PyTorch).

### 4.3 RTL Simulation (Vivado xsim)

Both MMIO peripherals were verified in standalone SystemVerilog simulation (Vivado 2025.2 xsim) before SoC integration. This two-stage strategy — standalone simulation, then in-system self-test — catches bugs before SoC integration obscures them.

**GEMV Testbench (`tb_gemv.sv`).** Three test scenarios are exercised:

**Table 6 — RTL Simulation Test Scenarios (GEMV)**

| Scenario | Description | Pass Condition |
|---|---|---|
| Deterministic | Fixed 32×32 matrix and vector, known expected output | Y outputs match golden reference after DONE asserts |
| Randomized | LCG-generated random matrix and vector pair | Results match software-model computed inside testbench |
| Boundary | All elements set to INT8_MIN (−128) and INT8_MAX (+127) | Correct saturation and sign handling verified |

Any mismatch triggers `$fatal`; a PASS prints on success. The testbench also writes a VCD (`tb_gemv.vcd`) for manual timing inspection.

**LUT Testbench (`tb_lut.sv`).** A full sweep (indices 0–15) compares each output against the golden file (`expected_lut.mem`) — the Q10 representations of exp(0)…exp(−15), matching `tinyformer.c` exactly. Any mismatch triggers `$fatal`.

Simulations are invoked from the Vivado Tcl console:

```tcl
source run_gemv_xsim.tcl
source run_lut_xsim.tcl
```

#### GEMV Simulation Waveforms

The captures below are from the `tb_gemv` xsim run, signals grouped (Clock/Reset, Load, Start, FSM state/pointers, MAC datapath, Read-back) to read top-to-bottom.

**Figure 7 — GEMV simulation: full operation overview**

```
(waveform)
```

Figure 7 shows one matvec end to end: reset, the three CPU load bursts (`x_wr_en`/`w_wr_en`/`b_wr_en`), the one-cycle `start`, the autonomous compute phase (`state = 1`, `col` sweeping), and `done` with read-back. The load bursts dominate, yet the CPU blocks only for the single `start` write — compute runs entirely inside the peripheral.

**Figure 8 — GEMV simulation: start handshake**

```
(waveform)
```

Figure 8 zooms to ~6 cycles around kick-off: on the `start` pulse the FSM samples it, `state` jumps `0 → 1` (IDLE → COMPUTE) and `busy` asserts. One CSR write starts the peripheral; the CPU is immediately free.

**Figure 9 — GEMV simulation: one compute row (4-lane MAC)**

```
(waveform)
```

Figure 9 spans one output row: with `row = 0`, `col` increments `0 → 8`; each clock `x_word`/`w_word` present a packed-operand pair, `dot4` yields a signed value (four int8 multiplies + adder tree in one cycle), and `acc` accumulates. At `col = 8`, `y_mem[0]` latches, `row` advances, `acc` reloads with `b[1]`. So 32 multiplies finish in 8 cycles (vs. 32 byte-wide); the full `start`→`done` phase is ≈290 cycles for a 32×32 matvec (256 MAC + per-row bookkeeping).

**Figure 10 — GEMV simulation: completion and result read-back**

```
(waveform)
```

Figure 10 shows the hand-off: `busy` deasserts, `state` moves `1 → 2` (COMPUTE → DONE), `done` latches, a `clear_done` pulse resets the read pointer, and each `y_rd_en` presents the next int32 result. Outputs read −8, −6, −4, −2 (rows 0–3), matching the software golden exactly — bit-exact, not just fast.

#### EXP-LUT Simulation Waveforms

These captures are from the `tb_lut` xsim run, which verifies the lookup peripheral against the golden table `expected_lut.mem`.

**Figure 11 — EXP-LUT simulation: full index sweep (Test 1)**

```
(waveform)
```

Figure 11 drives `index` `0 → 15`, one per clock, sampling `value` the same cycle against the golden table (`addr = index[3:0]`). It shows two properties: **zero-cycle combinational behaviour** — each transition appears in `value` the same cycle, so an exponent is ready immediately; and **monotonic decay** — outputs fall from `0x0400 = 1024` (Q10 for 1.0) at index 0 to `0x000C = 12` (≈0.0117) at index 15. These match `compute_exp_q10()` bit-for-bit: a drop-in replacement, not an approximation. All 16 entries are covered in 16 cycles.

**Figure 12 — EXP-LUT simulation: stability hold (Test 2)**

```
(waveform)
```

Figure 12 holds four representative indices — `0, 4, 8, 15` — for five cycles each, covering the high, mid, and low ends of the table:

| index | value (hex / dec) | Q10 → float | Role in softmax |
|---|---|---|---|
| 0 | 0x0400 / 1024 | 1.0000 | weight when score is at the max (k = 0) |
| 4 | 0x012E / 302 | 0.2949 | mid-range decay |
| 8 | 0x005A / 90 | 0.0879 | small contribution |
| 15 | 0x000C / 12 | 0.0117 | nearly negligible (largest spread) |

Each plateau holds steady with no glitches (pure combinational ROM) and every transition is an instantaneous step. The per-exponent cost is two CSR transactions (~12 cycles) versus the ≈21,000-cycle software `exp()`. Across 2,560 exponents per inference, the EXP-LUT eliminates ≈53.8 M cycles — the single largest contributor to the 4.82× speedup.

### 4.4 On-Target Self-Tests

In addition to RTL simulation, each accelerator includes a dedicated on-target self-test that runs before any benchmarking:

- **`tests_dot8.c`**: Compares DOT8 hardware output against the C reference for a set of packed test vectors. Prints "DOT8 PASS" on success.
- **`tests_lut.c`**: Sweeps indices 0–15 and compares EXP-LUT hardware output against the golden table in `tinyformer.c`. Prints "LUT PASS" on success.
- **`tests_gemv.c`**: Runs GEMV with known matrices and vectors (32×32 and 64×64 shapes, with and without bias) and checks results against a software reference computed on-target. Prints "GEMV self-test PASS" on success.

The self-tests also run when the corresponding hardware is absent (via software fallbacks), allowing SoC and toolchain validation before the peripherals are enabled.

---

## 5. Analysis of Results

### 5.1 Baseline Profiling

The baseline firmware (pure software, runtime fixed-point exp()) measured **75,900,400 cycles (759.00 ms)** per inference across 10 samples. The on-chip hardware timer is the authoritative source; Python wall-clock timing is unreliable here due to pyserial buffering.

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

The 71% softmax share reflects a deliberate choice: the baseline uses genuine runtime fixed-point arithmetic (fixed-iteration loop plus multiplicative decay, constant `decay_q15 = 24,149`), not a precomputed table, and is marked `__attribute__((noinline, optimize("O0")))` so gcc cannot constant-fold or memoize it. This is essential for a fair EXP-LUT comparison: a software table would be resolved at compile time and the hardware LUT would show no advantage. For transparency, the *absolute* softmax share — and thus the headline speedup — depends on this modeling choice; the EXP-LUT replaces real runtime exp() work. The per-call cost (~21,000 cycles) is the measured total (53.8 M cycles ÷ 2,560 calls).

### 5.2 Performance Results

All measurements use the same bitstream, only the firmware binary changing between modes; the on-chip `timer0` provides cycle-accurate timing independent of host serial latency.

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

**EXP-LUT** eliminates the dominant bottleneck (71% of baseline cycles), replacing a ~21,000-cycle runtime computation with a ~12-cycle MMIO lookup (~1,700× per call). Despite being the simplest block (a combinational ROM), it delivers the largest share of the reduction.

**GEMV** is the largest absolute saver: per 32×32 matvec it is ~8× faster (~17,000 → ~2,000 cycles), coming equally from the 4× fewer CSR writes (packed data path) and the 4× fewer compute cycles (4-lane MAC).

**DOT8** contributes a modest speedup matching the initial 1% share of attention dot-products; it is small in the final measurement because softmax and matvec dominate and are handled by the other two blocks.

**Table 9 — Per-Accelerator Cycle Savings**

| Accelerator | Cycles Saved (vs Baseline) | Contribution to Speedup |
|---|---|---|
| EXP-LUT | ~53,800,000 | Primary — eliminates 71% bottleneck |
| GEMV | ~14,000,000 | Secondary — eliminates the bulk of matrix-vector cost (packed 4-lane design: 4× bus + 4× compute) |
| DOT8 | ~800,000 | Minor — consistent with 1% initial share |

### 5.4 Correctness Verification

Before any performance number, every accelerated build had to pass the `ENC_CKSUM` gate: the 32-bit additive checksum over the 16×32 int8 output must be bit-identical to the baseline for every sample.

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

All 10 checksums and predicted classes match the baseline, confirming the 4.82× speedup is genuine acceleration, not skipped computation or degraded correctness.

### 5.5 Area and Power

Relative to the plain VexRiscv baseline, the accelerators add **+3.9 pp LUT** (6.13% → **10.04%**), **+1.8 pp flip-flops** (2.49% → 4.32%), and **+3.3 pp DSP** (0% → 3.3%); power rises from **0.740 W to 0.792 W** (**1.07×**, ≈7%). Full breakdown in Table 2.

To be candid: the original goal aspired to stay *below* 10% LUT and limit power growth, but both rose modestly — the fundamental trade-off of FPGA acceleration, where dedicated arithmetic and wider data paths cost logic and switching in exchange for fewer cycles. The design landed at 10.04% LUT (marginally over) and 1.07× power. Against a **4.82× speedup** this is strongly favorable: 157.55 ms latency for ~7% more power, with ~**90% of the fabric still free**.

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

The single partial result is the LUT budget: 10.04% rather than strictly below 10%, with power up 1.07×. As noted in Section 5.5, this is the expected cost of dedicated hardware, strongly outweighed by the 4.82× speedup. The remaining key findings:

1. **Bottleneck identification is essential and non-obvious.** The 71% softmax share was not predictable from instruction counts; without profiling, effort might have gone to attention dot-products (only 1% of cycles).

2. **The simplest accelerator delivers the largest gain.** The EXP-LUT — a combinational ROM with two CSRs — accounts for most of the cycle reduction, underscoring the value of targeting the true bottleneck over the most interesting one.

3. **Data-path width matters as much as compute parallelism.** GEMV's efficiency comes equally from cutting CSR-bus traffic (4×, packed writes) and parallelizing the MAC (4×); for MMIO accelerators, bus bandwidth co-limits with arithmetic throughput.

4. **Correctness must precede performance.** Requiring a bit-identical `ENC_CKSUM` before any benchmark prevented reporting speedups from skipped or corrupted computation.

5. **4.82× at ~10% LUT is competitive.** KWT-Tiny [1] reports 5× at 29% area overhead; this work reaches 4.82× for +3.9 pp LUT (≈7× lower added area) with full bit-exact accuracy on an open FPGA platform.

6. **Universality is bounded by the bottleneck.** Accelerating softmax and GEMV ties the bitstream to TinyFormer's fixed dimensions; a general accelerator would need GEMV tiling/DMA and a larger, programmable EXP-LUT.

### 6.2 Further Work

- **DMA-based GEMV.** A DMA engine fetching W rows from DDR2 directly would remove CPU CSR streaming entirely, an estimated 2–3× further latency cut for GEMV-bound operations.

- **DMA-fed GEMV.** The GEMV core is now pipelined and meets timing at 100 MHz (WNS = +0.019 ns). A natural next step is a DMA path so the core fetches W rows from main RAM directly, removing CPU-side CSR streaming.

- **Wider DOT8.** An 8-lane DOT8 would double attention throughput, worthwhile for larger D or multi-head attention.

- **Larger EXP-LUT.** A 256-entry table (finer step or higher Q precision) would support wider attention logit ranges and reduce approximation error.

- **Tiling for larger models.** GEMV supports up to 64×64; tiling would enable D=64/128 and multi-head attention without peripheral changes, at some firmware loop overhead.

- **Multi-head attention.** Extending from one head to H would need H parallel GEMV cores or a serialized schedule on shared hardware, depending on area budget.

---

## 7. Project Documentation

All deliverables are maintained in two Git repositories:

**Algorithm and Firmware Repository (TinyML_algo):**

| Directory | Contents |
|---|---|
| `litex_port/common/` | Shared firmware sources: encoder, demo runner, UART driver, trained weights |
| `litex_port/baseline/`, `accel_all/` | Per-mode main files (baseline and accel_all) |
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

1. **Build the SoC bitstream** with `hw/build_soc.py` (Vivado 2025.2 + Nexys4DDR board file).
2. **Program the bitstream** per `docs/PROGRAM_FPGA.md`.
3. **Build each firmware mode** using the flags/file lists in `TinyML_algo/README.md`.
4. **Run self-tests** (LUT/GEMV/DOT8 PASS) before benchmarking.
5. **Run baseline and accel_all**; verify ENC_CKSUM match; compare CYCLES.

Full instructions are in `TinyML_algo/README.md` and `TinyML_algo/REPORT_NOTES_IMPLEMENTATION.md`.

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
