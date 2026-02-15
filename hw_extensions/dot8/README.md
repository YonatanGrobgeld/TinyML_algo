# Extension #1: DOT8 — INT8 Dot-Product / MAC

## What DOT8 is

**DOT8** is a custom RISC-V operation that computes a **packed int8 dot-product** and returns an **int32** result. Conceptually:

- **Inputs:** two 32-bit registers interpreted as packed int8 lanes (e.g. 4×int8 per register, or 8×int8 if using both rs1 and rs2 as one contiguous vector).
- **Output:** one int32 value in `rd`, typically the sum of products: `sum_i (a_i * b_i)` with optional accumulation (MAC).

Exact packing (how many lanes, whether rs1/rs2 are 4×8 or 8×8) is defined in `encoding.md`. The key point is: **one instruction replaces an inner loop** of multiply-accumulate over int8 pairs.

## Where it is used in TinyFormer

In `litex_port/tinyformer.c`, almost every hot path is a dot-product or matrix-vector product over int8:

- **Q/K/V projections:** `matvec_i8_i32_acc` — inner loop `acc += (int32_t)w_row[id] * (int32_t)in[id]`.
- **Attention scores:** for each query `i` and key `j`, `acc += (int32_t)q[i][d] * (int32_t)k[j][d]` over `d`.
- **Attention context:** weighted sum over values, same pattern.
- **FFN:** both layers are matvec over int8 with int32 accumulation.

Replacing these inner loops with a DOT8 instruction (or a small sequence of DOT8) reduces dynamic instruction count and improves throughput, especially if the CPU has a narrow pipeline.

## Why a custom instruction (not MMIO)

- **Latency:** A dot-product over 4–8 lanes is a single-cycle (or short) operation in the datapath. MMIO would require multiple bus transactions (write operands, read result), which is far slower than register-to-register.
- **Code shape:** The C code already has tight loops; we want to replace the body with one or a few instructions, not with function calls to MMIO drivers.
- **VexRiscv model:** Custom instructions are the standard way to add ALU-like ops; they fit the decode/execute/writeback pipeline and use the same register file.

Hence DOT8 is designed as a **VexRiscv custom instruction** (SpinalHDL plugin), not as a coprocessor behind MMIO.

## On-target test and USE_DOT8_HW

- **Self-test:** `litex_port/tests_dot8.c` plus `hw_extensions/dot8/sw/dot8.c` (see root README § Hardware extension self-tests).
- **Define `USE_DOT8_HW`** only when the Dot8Plugin is included in your VexRiscv CPU config. With the plugin present, the custom instruction executes and the test compares HW vs SW reference. Without the plugin, leave `USE_DOT8_HW` undefined: the test still runs using the software fallback (SW vs SW) and passes.
- **Integration:** Add `Dot8Plugin` to your VexRiscv plugin list (e.g. in LiteX VexRiscv config or SpinalHDL build). Rebuild the SoC and firmware with `-DUSE_DOT8_HW` so `dot8_4_lanes()` uses the inline asm.
