# Exp LUT — specification

## Input range

- **Index:** signed integer in the range **-15 to 0** (inclusive).
- **Encoding:** 5-bit signed (e.g. `index[4:0]` where 5'b10000 = -16 is not used; 0 = exp(0), -1 = exp(-1), ..., -15 = exp(-15)).
- In the Verilog module, index is used as 4-bit unsigned address 0..15: address 0 → exp(0), address 1 → exp(-1), ..., address 15 → exp(-15). The CPU/software must pass the **non-negative** value `-index` (0..15) or the module accepts 5-bit signed and internally maps to 0..15.

## Output format

- **Width:** 16 bits.
- **Format:** **Q10** fixed-point — value represents `(LUT_entry / 1024)` as the approximate exp.
  - Example: exp(0) ≈ 1.0 → 1024.
  - Example: exp(-1) ≈ 0.37 → 377 (or 754/2); current table uses 754 for a slightly different scale; can be normalized to Q10 so 1024 = 1.0.
- Exact scaling should match the software LUT in `litex_port/tinyformer.c` (`exp_lut[16]`) for drop-in replacement.

## Intended software usage (MMIO)

1. **Write** the (non-negative) LUT index to the peripheral’s “index” register (e.g. 0 = exp(0), 1 = exp(-1), ..., 15 = exp(-15)). If the hardware accepts signed index, write the signed 5-bit value.
2. **Read** the “value” register to get the 16-bit fixed-point exp value.
3. Use this value in the softmax normalization (sum of exp, then divide) as in the C code — replace `score_to_exp(...)` with a CSR read when using the hardware LUT.

## Notes

- One cycle latency if output is combinatorial; add a register stage if needed for timing.
- For LiteX: typically one CSR for “write index” and one CSR for “read value”, or a single register that is written with index and read returns the LUT value (write-triggered lookup).
