#!/usr/bin/env python3
# ==========================================================================
#  WHAT THIS FILE DOES (in simple words):
#  One-off helper used while reorganizing the report text.
#  BIG PICTURE: Report tooling.
# ==========================================================================

"""One-shot restructure of Project_Report.md:
- Move Implementation chapter before Simulation (swap §3 and §4).
- Renumber section headers, figures, and tables to document order.
- Rebuild Table of Contents, List of Figures, List of Tables.
- Fix the GEMV CSR register map (Appendix B) into clean tables.
- Update Figure 1 / Figure 6 captions.
"""
import re

P = "/home/ronweinstein/workspace/university/Final_Project/TinyFormer_algo/Docs/Project_Report.md"
t = open(P, encoding="utf-8").read()

# ---- 1. Reorder chapters: Implementation before Simulation ----
i3 = t.index("## 3. Simulation")
i4 = t.index("## 4. Implementation")
i5 = t.index("## 5. Analysis of Results")
pre, sim, impl, post = t[:i3], t[i3:i4], t[i4:i5], t[i5:]

impl = impl.replace("## 4. Implementation", "## 3. Implementation").replace("### 4.", "### 3.")
sim = sim.replace("## 3. Simulation", "## 4. Simulation").replace("### 3.", "### 4.")
t = pre + impl + sim + post

# ---- 2. Renumber figures (document order after reorder) via markers ----
fig_map = {7: 13, 8: 14, 9: 7, 10: 8, 11: 9, 12: 10, 13: 11, 14: 12}
for old, new in fig_map.items():
    t = t.replace(f"Figure {old}", f"Figure \x00{new}\x00")
t = t.replace("\x00", "")

# ---- 3. Renumber tables (document order after reorder) via markers ----
tab_map = {2: 5, 3: 6, 4: 2, 5: 3, 6: 4}
for old, new in tab_map.items():
    t = t.replace(f"Table {old}", f"Table \x00{new}\x00")
t = t.replace("\x00", "")

# ---- 4. Rebuild front-matter blocks (overwrite, so renumber above can't corrupt them) ----
toc = """## Table of Contents

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

"""
lof = """## List of Figures

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

"""
lot = """## List of Tables

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

"""
t = re.sub(r"## Table of Contents\n.*?\n## List of Figures\n",
           toc + "## List of Figures\n", t, count=1, flags=re.S)
t = re.sub(r"## List of Figures\n.*?\n## List of Tables\n",
           lof + "## List of Tables\n", t, count=1, flags=re.S)
t = re.sub(r"## List of Tables\n.*?\n## Abstract\n",
           lot + "## Abstract\n", t, count=1, flags=re.S)

# ---- 5. Captions: Figure 1 and Figure 6 ----
t = t.replace("*Figure 1 — TinyFormer System Block Diagram*",
              "*Figure 1 — System Architecture: Baseline vs. Accelerated Modes*")
t = t.replace("**Figure 6 — TinyFormer Algorithm Pipeline**",
              "**Figure 6 — TinyFormer Encoder Architecture**")

# ---- 6. CSR register map (Appendix B): split into two clean tables ----
old_csr = """| Offset | Register | R/W | Bits | Description |
|---|---|---|---|---|
| 0x00 | CTRL | R/W | [0] start (pulse) | Write 1 to begin computation; self-clears |
| | | | [1] busy (read-only) | 1 while FSM is active |
| | | | [2] done (read-only) | 1 when computation is complete and Y is ready |
| | | | [3] clear_done (pulse) | Write 1 to reset DONE and return FSM to IDLE |
| | | | [4] len_64 | 0 = LEN=32; 1 = LEN=64 |
| | | | [5] out_dim_64 | 0 = OUT_DIM=32; 1 = OUT_DIM=64 |
| | | | [6] enable_bias | 1 = add bias vector b to result |
| 0x04 | X_IN | W | [31:0] | Write packed int8 X elements (4 per word, little-endian) |
| 0x08 | W_IN | W | [31:0] | Write packed int8 W elements (4 per word, row-major) |
| 0x0C | B_IN | W | [31:0] | Write int32 bias element |
| 0x10 | Y_OUT | R | [31:0] | Read int32 result element at current read pointer |
| 0x14 | STATUS | R | [0] busy, [1] done | Mirror of CTRL status bits for polling |
| 0x18 | Y_NEXT | W | [0] advance (pulse) | Write 1 to advance Y read pointer by one element |"""

new_csr = """**Register map** (one row per register):

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
| 6 | enable_bias | W | 1 = add the bias vector b to the result |"""

assert old_csr in t, "CSR table not found verbatim!"
t = t.replace(old_csr, new_csr)

open(P, "w", encoding="utf-8").write(t)
print("restructure complete")
