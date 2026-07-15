# Comparison Points: TinyFormer Project vs KWT-Tiny Paper

This document lists practical axes you can use in a report or presentation to compare our project against the paper:

- Paper: **KWT-Tiny: RISC-V Accelerated, Embedded Keyword Spotting Transformer** (arXiv:2407.16026)
- Our project: **TinyFormer encoder for UCI HAR on LiteX/VexRiscv**

Use these sections as a checklist. If a value is not yet measured in our project, mark it as "TBD" and keep the comparison transparent.

---

## 1) Problem Definition and Task Scope

Compare:
- Application domain (keyword spotting vs activity recognition)
- Number of output classes
- Input modality and shape
- Real deployment target (wake-word detector vs HAR classifier)

Why this matters:
- Direct metric comparisons are only fair if task difficulty and output space are comparable.

Suggested report sentence:
- "The two systems target different tasks and output spaces; therefore, cycle and model-size results are compared as engineering efficiency indicators rather than direct task-quality equivalence."

---

## 2) Model Architecture and Complexity

Compare:
- Transformer style (encoder-only, number of blocks/layers)
- Attention heads
- Hidden dimensions
- FFN size
- Parameter count

Why this matters:
- Compute and memory scale strongly with model dimensions and depth.

Checklist:
- [ ] Report model dimensions side-by-side
- [ ] Report parameter count side-by-side
- [ ] State whether each design is single-head or multi-head

---

## 3) Quantization and Numeric Format

Compare:
- Data types for weights/activations (INT8, FLOAT32, mixed)
- Accumulator precision (INT16/INT32)
- Operations left in floating point (if any)
- Quantization method (post-training static, per-tensor/per-layer scaling)

Why this matters:
- Numeric choices directly affect memory footprint, latency, and accuracy retention.

Checklist:
- [ ] Mention whether softmax/layernorm/GELU remain float or are approximated/fixed-point
- [ ] Mention scaling strategy (power-of-two shifts, LUTs, etc.)

---

## 4) Hardware Platform and Constraints

Compare:
- CPU core and ISA (Ibex vs VexRiscv)
- FPGA board
- Clock frequency
- RAM and ROM/BRAM constraints
- Presence/absence of FPU

Why this matters:
- Performance claims are hardware-dependent; constraints define what is feasible.

Checklist:
- [ ] Quote memory budget available at runtime
- [ ] Quote clock used for benchmarks

---

## 5) Acceleration Strategy

Compare:
- What is accelerated (GELU/Softmax vs dot product/GEMV/LUT)
- Mechanism (custom instruction, MMIO peripheral, plugin)
- Granularity (operator-level vs kernel-level)
- Reusability for other Transformer variants

Why this matters:
- Highlights architectural design choices and portability.

Checklist:
- [ ] Map each accelerator to the exact bottleneck it addresses
- [ ] State if acceleration preserves bit-exactness vs baseline

---

## 6) Memory Management Approach

Compare:
- Buffering strategy (streaming/tiled attention, full matrices, scratch banks)
- Dynamic allocation vs static buffers
- Peak intermediate tensor footprint

Why this matters:
- On tiny systems, memory planning can be as important as arithmetic speed.

Checklist:
- [ ] Document intermediate buffers and reuse policy
- [ ] Report peak RAM estimate if available

---

## 7) Accuracy and Trade-Offs

Compare:
- Baseline accuracy
- Accuracy after model downsizing
- Accuracy after quantization
- Accuracy after hardware approximation

Why this matters:
- The main research question is usually the quality/performance trade-off.

Checklist:
- [ ] Keep each degradation step separate (shrink vs quantize vs accelerate)
- [ ] Explain whether class reduction changes fairness of comparison

---

## 8) Performance Metrics and Methodology

Compare:
- Inference cycles
- Latency at given clock
- Speedup vs software baseline
- Measurement method (mcycle/timer, sample count, averaging)

Why this matters:
- Reproducible methodology makes comparisons credible.

Checklist:
- [ ] Use the same measurement protocol across modes
- [ ] Include baseline and accelerated values with speedup ratios

---

## 9) Area/Resource Cost

Compare:
- FPGA resource overhead from accelerators (LUT, FF, DSP, BRAM)
- Extra ROM/BRAM usage for lookup tables

Why this matters:
- Speedup is only meaningful with corresponding area/power cost.

Checklist:
- [ ] Report resource overhead percentage
- [ ] Link each overhead to its corresponding speed benefit

---

## 10) Reproducibility and Engineering Maturity

Compare:
- Availability of code/scripts
- Self-tests and correctness gates
- Build modes and compile-time switches
- Validation procedure (bit-identical checksums, prediction matching)

Why this matters:
- Strong validation and reproducibility improve academic credibility.

Checklist:
- [ ] Mention on-target self-tests
- [ ] Mention end-to-end correctness criteria before benchmarking

---

## Recommended Comparison Template (for your report)

Use this paragraph structure:

1. Task and constraints are different (state explicitly).
2. Our architecture and quantization choices (briefly).
3. Paper's architecture and acceleration choices (briefly).
4. Side-by-side metrics (size, cycles, speedup, accuracy).
5. Trade-off interpretation (what we gain, what we sacrifice).
6. Future work to narrow gaps (e.g., stronger quantization calibration, better softmax approximation, DMA/streaming improvements).

