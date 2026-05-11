# TinyFormer Project vs KWT-Tiny Paper

This document compares our project to:
**KWT-Tiny: RISC-V Accelerated, Embedded Keyword Spotting Transformer** (arXiv:2407.16026).

The goal is to provide report-ready comparison points with clear fairness notes.

---

## 1) High-Level Summary

- Both works target **Transformer inference on constrained embedded RISC-V systems**.
- Both use **quantized integer pipelines** and **hardware-aware optimization**.
- The paper focuses on **binary keyword spotting**; our project focuses on **6-class human activity recognition (UCI HAR)**.
- Therefore, this is a **design-method comparison** first, and a strict task-performance comparison second.

---

## 2) Side-by-Side Comparison

| Category | Our Project (TinyFormer + UCI HAR) | KWT-Tiny Paper (arXiv:2407.16026) |
|---|---|---|
| Task | Human Activity Recognition | Keyword Spotting |
| Output classes | 6 classes | Reduced from 35 to 2 classes |
| Input representation | Preprocessed int8 tensor `[16, 32]` from inertial signals | MFCC spectrogram (downsized to `[16, 26]`) |
| Core model style | Single-block TinyFormer encoder + linear classifier | Downsized KWT Transformer (encoder-style) |
| Data type | int8 weights/activations, int32 accumulators | Float baseline, then INT8 quantized model |
| Quantization style | Exported int8 C weights + fixed-point runtime | Post-training static quantization (power-of-two scaling) |
| Softmax strategy | Integer LUT + fixed-point normalization | Softmax accelerated using LUT-based exp/invert custom ops |
| Activation strategy | ReLU in FFN | GELU (accelerated/approximated in hardware) |
| CPU/platform | VexRiscv RV32IM on LiteX (Nexys4DDR) | lowRISC Ibex RV32IMC on FPGA (Arty A7-35T) |
| RAM constraint focus | Embedded bare-metal with fixed buffers and streaming attention | 64 KB RAM explicitly reported, no FPU |
| Acceleration mechanisms | DOT8 custom instruction, EXP LUT peripheral, GEMV peripheral | Custom RISC-V instructions and ALU blocks for GELU/Softmax |
| Correctness flow | Self-tests + checksum gate before benchmarking | End-to-end profiling and model-level evaluation reported |

---

## 3) Quantitative Numbers You Can Cite

### From the KWT-Tiny paper

- KWT-1 parameters: `607k`
- KWT-Tiny parameters: `1,646` (about `369x` reduction)
- Model memory: `2.42 MB` -> `6.58 kB` (tiny float) -> `1.646 kB` (quantized)
- Accuracy: `96.9%` -> `87.2%` (tiny) -> `82.5%` (quantized) -> about `80%` with hardware acceleration
- Inference cycles: `26e6` -> `13e6` -> `5.5e6` with hardware acceleration (about `5x` vs tiny baseline)
- Area/resource overhead: about `29%` (as reported by the paper)

### From our current project docs

- TinyFormer compute per sample: about `147,456` multiplications
- Baseline estimate: about `930k` instructions/sample (realistic `1.2M-1.4M` cycles depending on multiply latency)
- Projected speedups:
  - DOT8 only: about `5x-6x`
  - GEMV only: about `2.5x-3x`
  - DOT8 + LUT + GEMV: about `6.5x-7x`

Fairness note:
- Our performance values are currently documented as estimates/projections in project docs; paper values are reported experimental values in the publication.

---

## 4) Strong Comparison Narratives for Your Report

### Narrative A: "Different task, similar embedded methodology"

Use when emphasizing engineering contribution:
- Both projects demonstrate that Transformer-style blocks can run on low-resource RISC-V by combining quantization and custom hardware support.
- The paper accelerates GELU/Softmax primitives, while our design accelerates matvec/dot-product heavy kernels and softmax lookup paths.

### Narrative B: "Bottleneck-targeting strategy"

Use when discussing architecture decisions:
- The paper targets expensive transcendental/normalization operations (GELU + Softmax).
- Our project targets dominant arithmetic kernels and dataflow (DOT8 + GEMV + streaming attention).
- Both are valid and complementary bottleneck-reduction strategies.

### Narrative C: "Accuracy-performance trade-off transparency"

Use when discussing quality impact:
- Paper quantifies accuracy drops across downsizing/quantization/acceleration.
- Our project should mirror this staged reporting for strongest academic alignment (float/int baseline, int8 baseline, accelerated).

---

## 5) What We Can Claim Confidently Today

- We align with the paper's embedded AI philosophy: **small model, fixed-point arithmetic, hardware-aware acceleration**.
- Our system is likely to be competitive in **cycle reduction strategy** due to aggressive matvec/dot-product acceleration and streaming memory usage.
- Direct accuracy comparison is not apples-to-apples due to dataset and class-count differences.

---

## 6) Gaps to Fill for a Strong Final Comparison

To make this section publication-quality, add:

1. **Measured (not estimated) cycle counts** on FPGA for each mode:
   - baseline, DOT8, LUT, GEMV, combined
2. **Measured model accuracy** in each deployment stage:
   - software reference, quantized C path, accelerated path
3. **FPGA resource overhead table** for our accelerators:
   - LUT/FF/DSP/BRAM deltas
4. **Power or energy estimate** (optional but valuable):
   - even rough energy per inference using board-level current measurement

---

## 7) Ready-to-Use Report Paragraph

"Compared to KWT-Tiny, our TinyFormer implementation follows the same core principle of enabling Transformer-style inference on constrained RISC-V hardware through quantization and selective hardware acceleration. While KWT-Tiny emphasizes custom acceleration of GELU and Softmax, our design focuses on matvec and dot-product bottlenecks (DOT8 and GEMV) together with LUT-based softmax support and streaming attention memory reuse. Because the two systems target different tasks (binary keyword spotting versus 6-class HAR), we present the comparison primarily as an embedded-systems design trade-off analysis rather than direct task-quality equivalence."

