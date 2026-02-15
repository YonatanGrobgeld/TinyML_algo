# GEMV accelerator — specification

## Overview

The GEMV block computes **Y = W × X + b**:
- **W**: int8 matrix, `OUT_DIM` rows × `LEN` columns (row-major).
- **X**: int8 vector, length `LEN`.
- **b**: int32 bias vector, length `OUT_DIM` (optional).
- **Y**: int32 output vector, length `OUT_DIM`.

All multiplies are int8×int8; accumulation is int32. No scaling or saturation inside the block — software is responsible for requantizing Y to int8 if needed.

## Supported shapes and data types

| Parameter  | Allowed values | Notes                    |
|------------|----------------|--------------------------|
| LEN        | 32, 64         | Input vector length      |
| OUT_DIM    | 32, 64         | Output vector length     |
| W elements | int8           | Row-major, OUT_DIM×LEN   |
| X elements | int8           | LEN                      |
| b elements | int32          | OUT_DIM (optional)       |
| Y elements | int32          | OUT_DIM                  |

## Fixed-point / arithmetic

- **int8 × int8 → int32:** Each product is done with sign extension to 32 bits. No intermediate truncation.
- **Accumulation:** Per output row, `acc = b[i]` (if bias enabled) then `acc += sum_k (W[i][k] * X[k])`. Result is stored as int32 in Y[i].
- **No rounding or scaling** in hardware; software may apply shift and saturate to int8 (e.g. as in `tinyformer.c`).

## CSR register map

All registers are 32-bit, word-aligned. Base address is SoC-dependent (assigned when the peripheral is added to the LiteX design). **START** and **CLEAR_DONE** are implemented as **one-cycle pulses** in the LiteX wrapper (write CTRL with the bit set; the wrapper drives the pulse).

| Offset (bytes) | Name    | R/W | Width | Semantics |
|----------------|---------|-----|-------|-----------|
| 0x00           | CTRL    | R/W | 32    | Control: start (pulse), clear_done (pulse), len_64, out_dim_64, enable_bias. |
| 0x04           | X_IN    | W   | 32    | Write int8 into next X slot (low 8 bits). |
| 0x08           | W_IN    | W   | 32    | Write int8 into next W slot (low 8 bits), row-major. |
| 0x0C           | B_IN    | W   | 32    | Write int32 into next bias slot (optional). |
| 0x10           | Y_OUT   | R   | 32    | Read int32 at current Y index (does not advance pointer). |
| 0x14           | STATUS  | R   | 32    | [0]=busy, [1]=done (combinational from core). |
| 0x18           | Y_NEXT  | W   | 32    | Write any value to advance Y read pointer by one (pulse). |

### CTRL (0x00) bit layout

| Bit(s) | Name         | R/W | Description |
|--------|--------------|-----|-------------|
| 0      | start        | W   | **Pulse:** write 1 to start GEMV (one-cycle pulse). Ignored if busy. |
| 1      | busy         | R   | 1 while compute is in progress (read from STATUS). |
| 2      | done         | R   | 1 when compute finished (read from STATUS). Sticky until clear. |
| 3      | clear_done   | W   | **Pulse:** write 1 to clear done and reset Y read pointer. |
| 4      | len_64       | W   | 0 = LEN 32, 1 = LEN 64. Set before start. |
| 5      | out_dim_64   | W   | 0 = OUT_DIM 32, 1 = OUT_DIM 64. Set before start. |
| 6      | enable_bias  | W   | 1 = add bias. 0 = no bias. |
| 31:7   | —            | —   | Reserved. |

### X_IN (0x04)

- **Write:** data[7:0] = one int8 value. Each write goes to the next X slot (0 to LEN-1). Wraps or undefined after LEN writes; software should write exactly LEN times before start.
- **Read:** undefined or reserved.

### W_IN (0x08)

- **Write:** data[7:0] = one int8 weight. Row-major order: row 0 (LEN elements), then row 1, … Total OUT_DIM×LEN writes before start.
- **Read:** undefined or reserved.

### B_IN (0x0C) — optional

- **Write:** data[31:0] = one int32 bias value. OUT_DIM writes. If not implemented in v1, mark as TODO and document.
- **Read:** undefined or reserved.

### Y_OUT (0x10)

- **Read:** returns Y at the current read index (0 to OUT_DIM-1). Does **not** advance the index. Valid after done=1. After clear_done, index resets to 0.
- **Write:** no effect.

### STATUS (0x14)

- **Read:** [0]=busy, [1]=done. Combinational from core. Poll until done before reading Y.

### Y_NEXT (0x18)

- **Write:** any value. Generates a one-cycle pulse to advance the Y read pointer. Call after each Y_OUT read to get the next element.
- **Read:** undefined or reserved.

---

## Expected calling sequence (software)

1. **Clear done (pulse)**
   - Write CTRL with **only** `clear_done = 1` to clear done and reset Y read pointer. (LiteX wrapper turns this into a one-cycle pulse.)

2. **Load X**
   - Write LEN bytes to X_IN (one int8 per write, low 8 bits of each word).

3. **Load W**
   - Write OUT_DIM×LEN bytes to W_IN in row-major order (one int8 per write).

4. **Load b (if enable_bias)**
   - Write OUT_DIM int32 words to B_IN.

5. **Start (pulse)**
   - Write CTRL with `start = 1` and config bits `len_64`, `out_dim_64`, `enable_bias` as needed. One write generates a start pulse; hardware sets busy, then clears it and sets done when complete.

6. **Wait**
   - Poll STATUS until `done == 1` (bit 1).

7. **Read Y stream**
   - For each i from 0 to OUT_DIM-1: read Y_OUT (get Y[i]), then write Y_NEXT (advance pointer).

8. **Next run**
   - Write CTRL with `clear_done = 1` (pulse), then repeat from step 2.

---

## TinyFormer use cases (shapes)

| Layer        | OUT_DIM | LEN | Notes              |
|-------------|---------|-----|--------------------|
| Q/K/V/O     | 32      | 32  | len_64=0, out_dim_64=0 |
| FFN1        | 64      | 32  | len_64=0, out_dim_64=1 |
| FFN2        | 32      | 64  | len_64=1, out_dim_64=0 |
