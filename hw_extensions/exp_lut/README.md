# Extension #2: Exp LUT (Softmax helper)

## What the Exp LUT does

The **Exp LUT** is a small read-only lookup table that maps a **signed integer index** (e.g. in the range -15..0) to a **fixed-point approximation of exp(index)**. In TinyFormer’s softmax we compute `exp(score - max_score)` for each key; after scaling, the exponent argument lies in a limited range, so a 16-entry LUT is sufficient.

**Hardware block:** given an index (e.g. 5-bit signed), the module outputs the corresponding exp value in a fixed Q-format (e.g. Q10 or Q15) in one cycle.

## Why it helps softmax

In `litex_port/tinyformer.c`, softmax is implemented in software with:

- A 16-entry C array `exp_lut[16]` for inputs roughly [-15, 0].
- `score_to_exp(int16_t x)` clamps `x` to [-15, 0], then indexes the LUT.

The inner loop over keys computes normalized attention weights and then a weighted sum. Moving the LUT into hardware:

- Reduces code size and avoids loading LUT values from memory.
- Can be exposed as a single MMIO read (write index, read value) or, later, as a custom instruction for even lower latency.

## Why MMIO (not ISA extension initially)

- **Simplicity:** A small, standalone Verilog module with a single index input and data output is easy to wrap as a LiteX CSR peripheral (one or two registers: index write, value read). No pipeline changes in the CPU.
- **Reuse:** The same block can be used from C by a thin wrapper (write index to CSR, read result), or later wrapped as a custom instruction if we want to squeeze more performance.
- **Risk:** Implementing a new instruction requires decode/execute/writeback integration and verification; MMIO gets the accelerator usable quickly.

So the **initial integration target is LiteX MMIO**; an optional custom instruction can be added later if needed.
