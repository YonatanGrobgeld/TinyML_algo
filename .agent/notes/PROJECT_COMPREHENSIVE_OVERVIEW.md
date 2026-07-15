# TinyML Algorithm: Comprehensive Project Overview

## Table of Contents

1. [Project Vision](#project-vision)
2. [Stage 1: Algorithm Architecture](#stage-1-algorithm-architecture)
3. [Stage 2: CPU Baseline Implementation](#stage-2-cpu-baseline-implementation)
4. [Stage 3: Hardware Accelerators](#stage-3-hardware-accelerators)
5. [Performance Comparison](#performance-comparison)
6. [System Integration](#system-integration)

---

## Project Vision

This project implements a **TinyFormer encoder** (single-block Transformer-style model) on an FPGA-hosted RISC-V soft core (VexRiscv) running LiteX. The goal is to compare three implementation stages:

1. **Baseline**: Pure software on unmodified core
2. **Accelerated**: Using custom hardware extensions (custom instruction, LUT peripheral, matrix-vector accelerator)
3. **Performance**: Measure and compare throughput across configurations

**Target hardware**: Nexys4DDR FPGA, VexRiscv (RV32IM), bare-metal (no OS)

---

# Stage 1: Algorithm Architecture

## 1.1 Model Overview

### Model Dimensions

| Parameter | Value | Description |
|-----------|-------|-------------|
| Sequence Length (S) | 16 | Number of input tokens/timesteps |
| Model Dimension (D) | 32 | Feature vector size per timestep |
| FFN Hidden Size | 64 | Intermediate dimension in feed-forward network |
| Attention Heads | 1 | Single-head attention (simplified) |
| Data Type | int8 | Weights and activations (everywhere) |
| Accumulator Type | int32 | Internal computation precision |

### Input/Output Specification

**Input**: `int8_t input[16][32]`
- 16 timesteps (tokens)
- 32 features per timestep
- Pre-quantized (from preprocessing pipeline)
- Z-scored using training statistics

**Output**: `int8_t output[16][32]`
- Same shape as input
- After passing through attention + FFN blocks
- Used by classifier head (mean-pool + linear) for activity recognition

---

## 1.2 Detailed Algorithm Pipeline

### Stage 1: Q/K/V Projections

**Purpose**: Compute Query, Key, and Value tensors from input tokens

**Matrices**:
- **W_q**: [32][32] (shape: D × D)
- **W_k**: [32][32] (shape: D × D)
- **W_v**: [32][32] (shape: D × D)
- **b_q, b_k, b_v**: [32] each (biases)

**Computation**:
```
Q[i][d] = sum_k (W_q[d][k] * input[i][k]) + b_q[d]   for all i in [0..15], d in [0..31]
K[i][d] = sum_k (W_k[d][k] * input[i][k]) + b_k[d]
V[i][d] = sum_k (W_v[d][k] * input[i][k]) + b_v[d]
```

**Quantization**:
- Inner products computed in int32
- Result right-shifted by 7 bits and saturated to int8
- Produces tensors: Q, K, V each of shape [16][32]

**Data Movement**: 16 matrix-vector products × 3 = **48 matvec operations**

---

### Stage 2: Scaled Dot-Product Attention (Streaming)

**Purpose**: Compute attention weights and weighted context aggregation

**Key Innovation**: *Streaming attention* — processes one query position at a time, reusing small 1D buffers instead of allocating a full 16×16 attention matrix.

#### Sub-Stage 2a: Compute Attention Scores

For each query position `i` and all key positions `j`:
```
score[i][j] = (1/sqrt(D)) * dot(Q[i], K[j])
            = (1/sqrt(D)) * sum_d (Q[i][d] * K[j][d])
```

With D=32, √D ≈ 5.66; approximated by right-shift by 5 bits (÷32).

**Data**: 
- Inner products: 16 query positions × 16 key positions × 32 dimensions = **8192 multiplications**
- Temporary buffers: `scores[16]` (int32), one per query per computation

#### Sub-Stage 2b: Softmax Approximation

For each query position `i`:

1. **Find maximum score** (numerical stability):
   ```
   max_score = max(score[i][0..15])
   ```

2. **Shift and approximate exp** (no floating-point):
   ```
   For each j:
     shifted = score[i][j] - max_score  (always ≤ 0, bounded range)
     scaled = shifted >> 3               (further compression to [-32, 0])
     exp_approx[j] = LUT[clamp(scaled, -15, 0)]  (Q10 fixed-point)
   ```

3. **Normalize** (Q15 fixed-point):
   ```
   sum_exp = sum_j(exp_approx[j])
   weight[i][j] = (exp_approx[j] << 15) / sum_exp
   ```

**LUT Table** (exp approximation in Q10 fixed-point, indices 0..15):
- Index 0: exp(0) = 1024
- Index 1: exp(-1) ≈ 754
- Index 2: exp(-2) ≈ 556
- ...
- Index 15: exp(-15) ≈ 12

Exact values stored in `exp_lut[16]` in software.

#### Sub-Stage 2c: Weighted Value Aggregation

```
For each query position i and dimension d:
  context[i][d] = sum_j (weight[i][j] * V[j][d])  (Q15 arithmetic)
  context[i][d] = (int32_t result) >> 15, saturate to int8
```

**Data Movement**: 16 × 16 × 32 = **8192 multiplications** (weighted sum)

**Output**: `context[16][32]` (int8)

---

### Stage 3: Output Projection + Residual Connection

**Purpose**: Project attention output back to model dimension and add to input (residual)

**Matrices**:
- **W_o**: [32][32] (shape: D × D)
- **b_o**: [32] (bias)

**Computation**:
```
projected[i][d] = sum_k (W_o[d][k] * context[i][k]) + b_o[d]
output[i][d] = saturate(input[i][d] + projected[i][d])
```

**Quantization**: Same as projections (int32 accumulation, right-shift by 7, saturate to int8)

**Data Movement**: 16 matvec operations

---

### Stage 4: Feed-Forward Network (FFN)

**Purpose**: Position-wise feed-forward transformation with nonlinearity

#### Sub-Stage 4a: FFN Layer 1 (Expansion)

**Matrices**:
- **W_ff1**: [64][32] (shape: FFN × D)
- **b_ff1**: [64] (bias)

**Computation**:
```
hidden[i][d] = ReLU(sum_k (W_ff1[d][k] * attn_out[i][k]) + b_ff1[d])
```

Where ReLU in int8 space: `if (value < 0) return 0; else return value;`

**Data Movement**: 16 × 64 = **1024 multiplications**

**Output**: `hidden[16][64]` (int8)

#### Sub-Stage 4b: FFN Layer 2 (Reduction)

**Matrices**:
- **W_ff2**: [32][64] (shape: D × FFN)
- **b_ff2**: [32] (bias)

**Computation**:
```
ffn_out[i][d] = sum_k (W_ff2[d][k] * hidden[i][k]) + b_ff2[d]
```

**Data Movement**: 16 × 32 = **512 multiplications**

#### Sub-Stage 4c: Residual and Final Output

```
output[i][d] = saturate(attn_out[i][d] + ffn_out[i][d])
```

**Output**: `output[16][32]` (int8)

---

## 1.3 Algorithm Summary Table

| Stage | Operation | Matrices | Total Multiplications | Output Shape |
|-------|-----------|----------|----------------------|--------------|
| 1 | Q/K/V projections | W_q, W_k, W_v (3×D²) | 3 × 16 × 32² = 49,152 | [16][32] each |
| 2a | Attention scores | (Q, K inner products) | 16 × 16 × 32 = 8,192 | [16][16] |
| 2b | Softmax | LUT + normalization | 16 × 16 = 256 (lookups) | [16][16] |
| 2c | Value aggregation | (attention × V) | 16 × 16 × 32 = 8,192 | [16][32] |
| 3 | Output projection | W_o (D²) | 16 × 32² = 16,384 | [16][32] |
| 4a | FFN layer 1 | W_ff1 (FFN × D) | 16 × 64 × 32 = 32,768 | [16][64] |
| 4b | FFN layer 2 | W_ff2 (D × FFN) | 16 × 32 × 64 = 32,768 | [16][32] |
| **Total** | | | **~147,456 multiplications** | [16][32] |

---

## 1.4 Algorithm Block Diagram

```
                       Input [16][32]
                            │
                   ┌────────┼────────┐
                   ▼        ▼        ▼
          ┌─────────────────────────────────┐
          │   Q/K/V Projections             │
          │   (Linear: W_q, W_k, W_v)       │
          │   16 × 32² × 3 multiplications  │
          └─────┬────────────────────────────┘
                │
        Q[16][32], K[16][32], V[16][32]
                │
          ┌─────▼─────────────────────────┐
          │  Scaled Dot-Product Attention │
          │  (Streaming, 1 query at time) │
          ├──────────────────────────────┤
          │  1. Scores: Q·K (8K ops)     │
          │  2. Softmax: LUT + norm      │
          │  3. Context: attn·V (8K ops) │
          └─────┬──────────────────────────┘
                │
        Context[16][32]
                │
          ┌─────▼──────────────────────┐
          │  Output Projection + Res   │
          │  (W_o, 16 × 1024 ops)      │
          │  attn_out += input (res)   │
          └─────┬──────────────────────┘
                │
        attn_out[16][32]
                │
          ┌─────▼──────────────────────┐
          │  FFN Layer 1 (Expand)      │
          │  (W_ff1, 32K ops + ReLU)   │
          └─────┬──────────────────────┘
                │
        hidden[16][64]
                │
          ┌─────▼──────────────────────┐
          │  FFN Layer 2 (Reduce)      │
          │  (W_ff2, 32K ops)          │
          │  + Residual from attn_out  │
          └─────┬──────────────────────┘
                │
                ▼
           Output [16][32]
```

---

# Stage 2: CPU Baseline Implementation

## 2.1 Baseline Architecture

The baseline implementation is **pure C, no hardware acceleration**. All computation runs on VexRiscv RV32IM core with standard integer instructions only.

### Key Characteristics
- **No custom instructions**: Uses only standard RV32IM ISA
- **No peripherals**: All computation done in CPU
- **Fixed-size buffers**: Deterministic memory usage, no dynamic allocation
- **Quantization**: int8 weights/activations, int32 accumulators internally

---

## 2.2 Core Computation Pattern: Matrix-Vector Product

Nearly every hot path in the algorithm is a matrix-vector product (matvec):

```c
// Baseline matvec: Y = W*X + b
void matvec_i8_i32_acc(
    const int8_t *in,      // input vector [D_in]
    int8_t       *out,     // output vector [D_out]
    const int8_t *W,       // matrix, row-major [D_out][D_in]
    const int8_t *b,       // bias [D_out]
    int32_t       d_in,
    int32_t       d_out)
{
    for (int od = 0; od < d_out; ++od) {
        const int8_t *w_row = &W[od * d_in];
        int32_t acc = (int32_t)b[od];
        
        // Inner loop: dot product
        for (int id = 0; id < d_in; ++id) {
            acc += (int32_t)w_row[id] * (int32_t)in[id];
        }
        
        out[od] = saturate_int32_to_int8(acc >> 7);  // Scale and saturate
    }
}
```

**CPU Instructions per iteration**:
- Load weight + Load input + Sign-extend both to int32
- Multiply (int32)
- Add to accumulator
- Store back (6-8 instructions per inner iteration)

With 32 or 64 dimensional dot products, this becomes a significant CPU bottleneck.

---

## 2.3 Bottleneck Analysis: Data Path

### Critical Bottleneck #1: Repeated Dot Products

**In attention scores** (Q·K computation):
```
for query i in 0..15:
  for key j in 0..15:
    score[i][j] = dot(Q[i], K[j])  // 32 multiplications per dot
```

Total: 16 × 16 × 32 = **8,192 multiplications**

**CPU Implementation**:
```c
// Inner loop (executed 8192 times total)
for (d = 0; d < 32; ++d) {
    acc += (int32_t)q[i][d] * (int32_t)k[j][d];  // ~6 instructions
}
```

**Problem**: Each multiply+add requires 6-8 RV32IM instructions. Total: ~50,000 instructions for 8K multiplications.

### Critical Bottleneck #2: Linear Projections

**Q/K/V projections** alone require:
- 3 weight matrices × 16 tokens × 32 dimensions = **49,152 multiplications**
- At 6 instructions per multiply: ~300,000 instructions

**Bottleneck type**: **Multiply-limited**
- RV32I has no single-cycle multiply (mul takes multiple cycles on area-optimized cores)
- Each matvec operation is multiply-bound, not memory-bound (weights already loaded)

---

## 2.4 Bottleneck Analysis: Control Path

### Sub-optimal Loop Structure

**Nested loops in attention**:
```c
for (i = 0; i < 16; ++i) {           // Query loop
    for (j = 0; j < 16; ++j) {       // Key loop
        for (d = 0; d < 32; ++d) {   // Dimension loop (multiply-bound)
            acc += q[i][d] * k[j][d];
        }
    }
}
```

**Loop overhead**:
- Each inner `d` loop: setup, increment, branch (~3 instructions/iteration)
- 16 × 16 × 32 = 8,192 loop iterations → 24,576 loop overhead instructions
- Total instructions: ~74,000 for 8K multiplications

**Problem**: Loop overhead is 25-30% of total cycles, but **cannot be eliminated** without wider datapaths or custom instructions.

---

## 2.5 Baseline Performance Characteristics

### Instruction Breakdown (per sample, ~16 tokens)

| Operation | Multiplications | Instructions | Cycles (est.) |
|-----------|-----------------|--------------|---------------|
| Q/K/V projections | 49,152 | 295,000 | 295,000 |
| Attention scores | 8,192 | 50,000 | 50,000 |
| Softmax + normalization | 256 | 15,000 | 15,000 |
| Value aggregation | 8,192 | 50,000 | 50,000 |
| Output projection | 16,384 | 100,000 | 100,000 |
| FFN layer 1 | 32,768 | 200,000 | 200,000 |
| FFN layer 2 | 32,768 | 200,000 | 200,000 |
| Residuals + misc | - | 20,000 | 20,000 |
| **Total** | **~147,456** | **~930,000** | **~930,000** |

**Baseline cycles per sample**: ~930,000 cycles (assuming single-cycle multiply, which RV32IM may not have)

**With realistic multiply latency** (2-3 cycles): 1.2M - 1.4M cycles per sample

---

## 2.6 Baseline Code Structure

Located in `/litex_port/common/tinyformer.c`:

```
1. Placeholder or trained weights (global arrays)
2. Helper macros (saturate_int32_to_int8)
3. Global buffers (q_buf, k_buf, v_buf, attn_out, ffn_hidden, ffn_out)
4. LUT table for softmax approximation (exp_lut[16])
5. matvec_i8_i32_acc() — core multiply-accumulate
6. linear_projection_all() — applies matvec to all tokens
7. attention_single_head() — streaming attention
8. ffn_apply() — feed-forward layers
9. tinyformer_encode() — main entry point
```

---

# Stage 3: Hardware Accelerators

## 3.1 Accelerator Strategy Overview

Three hardware extensions target the bottlenecks identified in the baseline:

| Accelerator | Bottleneck Addressed | Type | Where |
|-------------|---------------------|------|-------|
| **DOT8** | Multiply-bound loops in dot products | Custom ISA instruction | CPU pipeline |
| **EXP LUT** | Softmax exponential lookup | Memory-mapped peripheral | MMIO |
| **GEMV** | Large matrix-vector products | Accelerator core | MMIO peripheral |

---

## 3.2 Accelerator #1: DOT8 (Custom Instruction)

### Purpose

Replace nested dot-product loops with a single-cycle instruction for 4-lane int8 dot products.

### Design

**Instruction encoding**:
- **Opcode**: custom-0 (0x0B, bits [6:0])
- **Funct7**: 0x01 (bits [31:25])
- **rs1, rs2, rd**: Standard register fields (32-bit)

**Operands**:
- **rs1**: First packed vector (4 × int8, little-endian byte packing)
  - Byte 0 (LSB): lane 0
  - Byte 1: lane 1
  - Byte 2: lane 2
  - Byte 3 (MSB): lane 3
- **rs2**: Second packed vector (same format)
- **rd**: Result (32-bit signed int32)

**Operation**:
```
rd = (int32_t)rs1[0] * (int32_t)rs2[0] +
     (int32_t)rs1[1] * (int32_t)rs2[1] +
     (int32_t)rs1[2] * (int32_t)rs2[2] +
     (int32_t)rs1[3] * (int32_t)rs2[3]
```

### Implementation Details

#### VexRiscv Plugin (Scala)

Located in `hw_extensions/dot8/Dot8Plugin.scala`:

```scala
// Simplified representation
class Dot8Plugin extends Plugin[VexRiscv] {
  override def setup(pipeline: VexRiscv): Unit = {
    // Register custom instruction pattern
    pipeline.add(Decode stage) {
      when(instr[6:0] == 0x0B && instr[31:25] == 0x01) {
        decodeSignal := CustomDot8
      }
    }
    
    // Execute stage
    pipeline.add(Execute stage) {
      when(decodeSignal == CustomDot8) {
        val a = rs1Data.asBytes()
        val b = rs2Data.asBytes()
        resultData := (
          (a[0].asSInt(8).asUInt(32) * b[0].asSInt(8).asUInt(32)) +
          (a[1].asSInt(8).asUInt(32) * b[1].asSInt(8).asUInt(32)) +
          (a[2].asSInt(8).asUInt(32) * b[2].asSInt(8).asUInt(32)) +
          (a[3].asSInt(8).asUInt(32) * b[3].asSInt(8).asUInt(32))
        ).asSInt(32)
      }
    }
  }
}
```

**Key Design Choices**:
- **Single-cycle**: Decode, execute, writeback in one cycle (critical path: 4 multipliers + 3 adders)
- **No pipeline stall**: Results available next cycle
- **Deterministic latency**: Allows compiler to schedule around predictably

#### Software Driver

File: `hw_extensions/dot8/sw/dot8.h`

```c
// Packing helper
static inline uint32_t dot8_pack(const int8_t a[4]) {
    return (uint32_t)(uint8_t)a[0]
         | ((uint32_t)(uint8_t)a[1] << 8)
         | ((uint32_t)(uint8_t)a[2] << 16)
         | ((uint32_t)(uint8_t)a[3] << 24);
}

// Custom instruction wrapper
static inline int32_t dot8_4_lanes(uint32_t a_packed, uint32_t b_packed) {
    int32_t result;
    asm volatile(
        "custom0 %0, %1, %2, 0x01"  // funct7=0x01 in bits[31:25]
        : "=r"(result)
        : "r"(a_packed), "r"(b_packed)
    );
    return result;
}
```

**Fallback (software)**:
```c
#ifndef USE_DOT8_HW
// Software reference implementation
static inline int32_t dot8_4_lanes(uint32_t a_packed, uint32_t b_packed) {
    int8_t a0 = (int8_t)(a_packed >> 0);
    int8_t a1 = (int8_t)(a_packed >> 8);
    int8_t a2 = (int8_t)(a_packed >> 16);
    int8_t a3 = (int8_t)(a_packed >> 24);
    // ... similar for b ...
    return (int32_t)a0*b0 + (int32_t)a1*b1 + 
           (int32_t)a2*b2 + (int32_t)a3*b3;
}
#endif
```

### Integration into TinyFormer

The baseline's inner loops:
```c
// Before (8 instructions per multiply + add)
for (d = 0; d < 32; ++d) {
    acc += (int32_t)q[i][d] * (int32_t)k[j][d];
}
```

Transformed with DOT8:
```c
// After (vectorized by 4)
for (d = 0; d < 32; d += 4) {
    uint32_t q_packed = dot8_pack(&q[i][d]);
    uint32_t k_packed = dot8_pack(&k[j][d]);
    acc += dot8_4_lanes(q_packed, k_packed);  // 1 instruction!
}
```

**Speedup**: 
- **Before**: 32 × 8 = 256 instructions
- **After**: 8 packs (2 instructions each) + 8 DOT8 (1 instruction each) + 8 adds (1 instruction each) = 40 instructions
- **Reduction**: 6.4× fewer instructions for this inner loop

### Expected Speedup: DOT8 Alone

**Multiplications**: 147,456 total
- Can be parallelized 4-at-a-time with DOT8
- Each DOT8 replaces ~8 baseline instructions

**Estimated speedup**: 4-5× for multiply-heavy operations

---

## 3.3 Accelerator #2: EXP LUT (Lookup Table Peripheral)

### Purpose

Offload softmax exponential function to dedicated hardware LUT, eliminating software table lookups and computation overhead.

### Design

**Interface**: Memory-mapped peripheral with two registers:
1. **Index register** (write): Select which exp value to retrieve (0-15)
2. **Value register** (read): Get pre-computed exp value in Q10 fixed-point

### Hardware Implementation

#### Verilog Core (exp_lut.v)

```verilog
module exp_lut_core (
    input  clk,
    input  [3:0] index,     // 0..15 for exp(0) down to exp(-15)
    output [15:0] value     // Q10 fixed-point output
);

  // Hardcoded LUT
  reg [15:0] lut [0:15];
  
  always @(*) begin
    case(index)
      4'd0:  value = 16'h0400;  // exp(0)   = 1024 (Q10)
      4'd1:  value = 16'h02F2;  // exp(-1)  = 754
      4'd2:  value = 16'h022C;  // exp(-2)  = 556
      // ... all 16 entries ...
      4'd15: value = 16'h000C;  // exp(-15) = 12
    endcase
  end

endmodule
```

#### LiteX Integration (litex_port.py)

```python
# CSR registers accessible by firmware
class ExpLutModule(Module):
    def __init__(self, platform):
        self.sink = sink = Record([
            ("index", 4),
            ("value_out", 16),
            ("we", 1),  # write enable
        ])
        
        # Map to CSR
        self.csr = CSRRegionMapping(
            0xF0000000,  # Base address (example)
            {
                "INDEX": (0x00, self.sink.index),
                "VALUE": (0x04, self.sink.value_out),
            }
        )
```

### Software Driver

File: `hw_extensions/exp_lut/sw/exp_lut.c`

```c
#define EXP_LUT_BASE  0xF0000000  // Or from generated CSR

static inline uint16_t exp_lut_hw(int idx) {
    if (idx < 0) idx = 0;
    if (idx > 15) idx = 15;
    
    // Write index to peripheral
    *(volatile uint32_t *)(EXP_LUT_BASE + 0x00) = idx;
    
    // Read value (combinatorial or registered)
    return (uint16_t)(*(volatile uint32_t *)(EXP_LUT_BASE + 0x04));
}
```

**Fallback (internal table)**:
```c
#ifndef USE_EXP_LUT_HW
static const uint16_t exp_lut_golden[16] = {
    1024, 754, 556, 410, 302, 223, 165, 122,
    90, 67, 50, 37, 28, 21, 16, 12
};

static inline uint16_t exp_lut_hw(int idx) {
    if (idx < 0) idx = 0;
    if (idx > 15) idx = 15;
    return exp_lut_golden[idx];
}
#endif
```

### Integration into TinyFormer

**Baseline** (every softmax computation):
```c
// Inside attention_single_head(), called per query position
for (j = 0; j < 16; ++j) {
    int16_t scaled = (int16_t)(scores[j] - max_score) >> 3;
    uint16_t e = score_to_exp(scaled);  // Table lookup + clamp
    exp_buf[j] = e;
    sum_exp += (uint32_t)e;
}

// score_to_exp() implementation
static uint16_t score_to_exp(int16_t x) {
    if (x > 0) x = 0;
    else if (x < -15) x = -15;
    return exp_lut[(uint16_t)(-x)];  // Array access
}
```

**With hardware LUT**:
```c
for (j = 0; j < 16; ++j) {
    int16_t scaled = (int16_t)(scores[j] - max_score) >> 3;
    if (scaled > 0) scaled = 0;
    else if (scaled < -15) scaled = -15;
    uint16_t e = exp_lut_hw(-scaled);  // Single MMIO read
    exp_buf[j] = e;
    sum_exp += (uint32_t)e;
}
```

### Expected Speedup: EXP LUT Alone

**Operations**: 16 queries × 16 keys = 256 lookups per sample

**Baseline cost per lookup**: 
- Array indexing: 2-3 instructions
- Clamping: 4-6 instructions
- Total: ~6 instructions × 256 = 1,536 instructions

**Hardware LUT cost per lookup**:
- MMIO write (index): 1 instruction
- MMIO read (value): 1 instruction (may stall if value takes multiple cycles)
- Total: ~2 instructions × 256 = 512 instructions

**Estimated speedup**: 3× for softmax operations (though these are not the bottleneck)

---

## 3.4 Accelerator #3: GEMV (Matrix-Vector Multiplication)

### Purpose

Accelerate large matrix-vector products (Y = W×X + b) used in all linear layers of the encoder.

### Design

**Compute core**: Streams data via CSR registers, performs matrix-vector multiply, returns results.

**Supported shapes**: 
- Vector length (LEN): 32 or 64
- Output dimension (OUT_DIM): 32 or 64

**Data flow**:
```
CPU → [Stream X]  →   ┌──────────┐
      [Stream W]  →   │  GEMV    │   → [Output Y]
      [Stream b]  →   │  Core    │
                      └──────────┘
```

### Hardware Implementation

#### RTL Core (gemv_core.v)

Simplified state machine:

```verilog
module gemv_core (
    input clk,
    input [31:0] x_in,         // Input vector element (int8)
    input [31:0] w_in,         // Weight element (int8)
    input [31:0] b_in,         // Bias element (int32, optional)
    output [31:0] y_out,       // Result element (int32)
    input start,               // Begin computation
    input clear_done,
    output busy,
    output done,
    input enable_bias,
    input len_64,              // Vector length: 0=32, 1=64
    input out_dim_64           // Output dimension: 0=32, 1=64
);

  // FSM and data path
  localparam IDLE = 0, LOAD_X = 1, LOAD_W = 2, COMPUTE = 3, WAIT_READ = 4;
  
  reg [3:0] state;
  reg [5:0] x_idx, w_row, w_col;
  reg [31:0] accumulators [0:63]; // max 64 output elements
  reg [31:0] current_y_out;
  reg [5:0] y_read_idx;
  
  // Simplified compute: for each output row, dot product with X
  always @(posedge clk) begin
    case(state)
      IDLE: if (start) state <= LOAD_X;
      
      LOAD_X:  // Collect X vector
        if (x_idx < len) begin
          x_data[x_idx] <= x_in[7:0];  // Low 8 bits
          x_idx <= x_idx + 1;
        end else begin
          x_idx <= 0;
          state <= LOAD_W;
        end
      
      LOAD_W:  // Collect W matrix (row-major)
        if (w_row < out_dim) begin
          if (w_col < len) begin
            w_data[w_row][w_col] <= w_in[7:0];
            w_col <= w_col + 1;
          end else begin
            w_col <= 0;
            w_row <= w_row + 1;
          end
        end else begin
          state <= COMPUTE;
        end
      
      COMPUTE:  // Compute Y = W * X + b (optionally)
        for (i = 0; i < out_dim; i = i + 1) begin
          acc = enable_bias ? b_data[i] : 32'h0;
          for (j = 0; j < len; j = j + 1) begin
            acc = acc + (sign_extend(w_data[i][j]) * 
                               sign_extend(x_data[j]));
          end
          accumulators[i] <= acc;
        end
        state <= WAIT_READ;
      
      WAIT_READ:  // CPU reads results via Y_OUT/Y_NEXT
        if (clear_done) begin
          y_read_idx <= 0;
          state <= IDLE;
        end
    endcase
  end
  
  assign y_out = accumulators[y_read_idx];
  assign busy = (state != IDLE);
  assign done = (state == WAIT_READ);

endmodule
```

#### LiteX CSR Wrapper

File: `hw_extensions/gemv/litex/gemv_periph.py`

```python
class GemvPeripheral(Module):
    def __init__(self):
        self.ctrl = CSRStorage(32)        # CTRL register
        self.x_in = CSRStorage(32)        # Write X
        self.w_in = CSRStorage(32)        # Write W
        self.b_in = CSRStorage(32)        # Write b
        self.y_out = CSRStatus(32)        # Read Y
        self.status = CSRStatus(32)       # Read busy/done
        self.y_next = CSRStorage(32)      # Pulse to advance Y
        
        # CSR mapping at base address (e.g., 0xF0001000)
        # Offsets: 0x00 CTRL, 0x04 X_IN, 0x08 W_IN, 0x0C B_IN, 
        #          0x10 Y_OUT, 0x14 STATUS, 0x18 Y_NEXT
```

#### CSR Register Map

| Offset | Name | R/W | Bits | Description |
|--------|------|-----|------|-------------|
| 0x00 | CTRL | R/W | [0] start (pulse), [1] busy (ro), [2] done (ro), [3] clear_done (pulse), [4] len_64, [5] out_dim_64, [6] enable_bias |
| 0x04 | X_IN | W | [7:0] int8 X element |
| 0x08 | W_IN | W | [7:0] int8 W element |
| 0x0C | B_IN | W | [31:0] int32 bias |
| 0x10 | Y_OUT | R | [31:0] int32 result |
| 0x14 | STATUS | R | [0] busy, [1] done |
| 0x18 | Y_NEXT | W | Write pulse to advance read pointer |

### Software Driver

File: `hw_extensions/gemv/sw/gemv.c`

```c
struct gemv_ctx {
    uint32_t base_addr;
};

void gemv_init(struct gemv_ctx *ctx, uint32_t base) {
    ctx->base_addr = base;
}

void gemv_clear_done(struct gemv_ctx *ctx) {
    *(volatile uint32_t *)(ctx->base_addr + 0x00) = (1 << 3);  // clear_done pulse
}

void gemv_load_x(struct gemv_ctx *ctx, const int8_t *x, int len) {
    for (int i = 0; i < len; i++) {
        *(volatile uint32_t *)(ctx->base_addr + 0x04) = (uint32_t)(uint8_t)x[i];
    }
}

void gemv_load_w(struct gemv_ctx *ctx, const int8_t *w, int out_dim, int len) {
    for (int i = 0; i < out_dim * len; i++) {
        *(volatile uint32_t *)(ctx->base_addr + 0x08) = (uint32_t)(uint8_t)w[i];
    }
}

void gemv_load_b(struct gemv_ctx *ctx, const int32_t *b, int out_dim, int enable_bias) {
    if (!enable_bias) return;
    for (int i = 0; i < out_dim; i++) {
        *(volatile uint32_t *)(ctx->base_addr + 0x0C) = b[i];
    }
}

void gemv_start(struct gemv_ctx *ctx, int len_64, int out_dim_64) {
    uint32_t ctrl = (1 << 0);  // start pulse
    if (len_64) ctrl |= (1 << 4);
    if (out_dim_64) ctrl |= (1 << 5);
    *(volatile uint32_t *)(ctx->base_addr + 0x00) = ctrl;
}

void gemv_wait_done(struct gemv_ctx *ctx) {
    while (!(*(volatile uint32_t *)(ctx->base_addr + 0x14) & (1 << 1))) {
        // Poll STATUS.done
    }
}

int32_t gemv_read_y(struct gemv_ctx *ctx) {
    return *(volatile int32_t *)(ctx->base_addr + 0x10);
}

void gemv_advance_y(struct gemv_ctx *ctx) {
    *(volatile uint32_t *)(ctx->base_addr + 0x18) = 1;  // Y_NEXT pulse
}
```

### Integration into TinyFormer

**Baseline matvec**:
```c
// Y = W × X + b (pure software)
void matvec_i8_i32_acc(const int8_t *in, int8_t *out,
                       const int8_t *W, const int8_t *b,
                       int32_t d_in, int32_t d_out) {
    for (int od = 0; od < d_out; ++od) {
        const int8_t *w_row = &W[od * d_in];
        int32_t acc = (int32_t)b[od];
        for (int id = 0; id < d_in; ++id) {
            acc += (int32_t)w_row[id] * (int32_t)in[id];
        }
        out[od] = saturate_int32_to_int8(acc >> 7);
    }
}
```

**With GEMV accelerator**:
```c
// Y = W × X + b (using GEMV hardware)
void matvec_gemv(struct gemv_ctx *ctx, const int8_t *in, int32_t *out,
                 const int8_t *W, const int32_t *b,
                 int len, int out_dim) {
    gemv_clear_done(ctx);
    gemv_load_x(ctx, in, len);
    gemv_load_w(ctx, W, out_dim, len);
    gemv_load_b(ctx, b, out_dim, 1);  // enable_bias=1
    
    int len_64 = (len == 64) ? 1 : 0;
    int out_dim_64 = (out_dim == 64) ? 1 : 0;
    gemv_start(ctx, len_64, out_dim_64);
    
    gemv_wait_done(ctx);
    for (int i = 0; i < out_dim; i++) {
        out[i] = gemv_read_y(ctx);
        gemv_advance_y(ctx);
    }
}
```

### Expected Speedup: GEMV Alone

**Operations accelerated**:
- Q/K/V projections: 3 × 16 × 1024 = 49,152 mul (48 matves of 32×32)
- Output projection: 16 × 1024 = 16,384 mul (16 matves of 32×32)
- FFN layer 1: 16 × 2048 = 32,768 mul (16 matves of 64×32)
- FFN layer 2: 16 × 2048 = 32,768 mul (16 matves of 32×64)
- **Total**: 131,072 multiplications (89% of total work)

**Baseline cost for one 32×32 matvec**: 
- Inner loop: 32 × 8 instructions = 256 instructions
- Outer loop + setup: 50 instructions
- Total: ~300 instructions per matvec

**GEMV accelerator cost per matvec**:
- Stream X: 32 MMIO writes = 32 instructions
- Stream W: 1024 MMIO writes = 1024 instructions
- Stream b: 32 MMIO writes = 32 instructions
- Start: 1 instruction
- Wait done: ~10 cycles polling
- Read Y: 32 + 32 MMIO (read + advance) = 64 instructions
- **Total**: ~1,200 instructions + hardware compute time

**But**: GEMV compute happens in parallel with CPU fetching next data
- With pipelined streaming: net speedup from parallelism

**Estimated speedup**: 3-5× for GEMV-heavy operations

---

## 3.5 Combined Accelerators: Synergistic Effects

### All Three Together (DOT8 + EXP LUT + GEMV)

| Operation | Baseline Inst. | DOT8 | DOT8+LUT | DOT8+GEMV | All Three |
|-----------|----------------|------|----------|-----------|-----------|
| Q/K/V proj | 150K | 30K | 30K | 20K | 20K |
| Attn scores | 50K | 10K | 10K | 10K | 10K |
| Softmax | 15K | 15K | 5K | 15K | 5K |
| Value agg | 50K | 10K | 10K | 10K | 10K |
| Output proj | 100K | 20K | 20K | 15K | 15K |
| FFN layer 1 | 200K | 40K | 40K | 30K | 30K |
| FFN layer 2 | 200K | 40K | 40K | 30K | 30K |
| Misc | 20K | 20K | 20K | 20K | 20K |
| **Total** | **930K** | **185K** | **175K** | **150K** | **140K** |

**Estimated speedups**:
- **DOT8 only**: 5× reduction
- **DOT8 + EXP LUT**: 5.3×
- **DOT8 + GEMV**: 6.2×
- **All three**: **6.6× speedup** overall

---

# Stage 4: Verification & Testing

## 4.1 Self-Tests

Each accelerator includes an on-target self-test:

### DOT8 Self-Test

File: `litex_port/tests_dot8.c`

```c
int test_dot8(void) {
    // Test vectors
    int8_t a[4] = {1, 2, 3, 4};
    int8_t b[4] = {5, 6, 7, 8};
    
    // Expected: 1*5 + 2*6 + 3*7 + 4*8 = 5 + 12 + 21 + 32 = 70
    uint32_t a_packed = dot8_pack(a);
    uint32_t b_packed = dot8_pack(b);
    int32_t result = dot8_4_lanes(a_packed, b_packed);
    
    if (result != 70) {
        uart_write_string("DOT8 FAIL\r\n");
        return 1;
    }
    uart_write_string("DOT8 PASS\r\n");
    return 0;
}
```

### EXP LUT Self-Test

File: `litex_port/tests_lut.c`

```c
int test_lut(void) {
    // Golden reference table
    const uint16_t golden_lut[16] = {
        1024, 754, 556, 410, 302, 223, 165, 122,
        90, 67, 50, 37, 28, 21, 16, 12
    };
    
    for (int i = 0; i < 16; i++) {
        uint16_t hw_val = exp_lut_hw(i);
        if (hw_val != golden_lut[i]) {
            uart_write_string("LUT FAIL index=");
            uart_write_uint32(i);
            uart_write_string("\r\n");
            return 1;
        }
    }
    uart_write_string("LUT PASS\r\n");
    return 0;
}
```

### GEMV Self-Test

File: `litex_port/tests_gemv.c`

```c
int test_gemv(void) {
    struct gemv_ctx ctx;
    gemv_init(&ctx, GEMV_BASE);
    
    // Test 32×32 matrix-vector
    int8_t X[32] = { /*...deterministic LCG values...*/ };
    int8_t W[32*32] = { /*...deterministic LCG values...*/ };
    int32_t b[32] = { /*...deterministic LCG values...*/ };
    
    // Compute reference in software
    int32_t ref_Y[32];
    for (int i = 0; i < 32; i++) {
        int32_t acc = b[i];
        for (int j = 0; j < 32; j++) {
            acc += (int32_t)W[i*32+j] * (int32_t)X[j];
        }
        ref_Y[i] = acc;
    }
    
    // Run hardware GEMV
    int32_t hw_Y[32];
    gemv_clear_done(&ctx);
    gemv_load_x(&ctx, X, 32);
    gemv_load_w(&ctx, W, 32, 32);
    gemv_load_b(&ctx, b, 32, 1);
    gemv_start(&ctx, 0, 0);  // len=32, out_dim=32
    gemv_wait_done(&ctx);
    
    for (int i = 0; i < 32; i++) {
        hw_Y[i] = gemv_read_y(&ctx);
        gemv_advance_y(&ctx);
    }
    
    // Compare
    for (int i = 0; i < 32; i++) {
        if (hw_Y[i] != ref_Y[i]) {
            uart_write_string("GEMV FAIL i=");
            uart_write_uint32(i);
            uart_write_string(" ref=");
            uart_write_int32(ref_Y[i]);
            uart_write_string(" hw=");
            uart_write_int32(hw_Y[i]);
            uart_write_string("\r\n");
            return 1;
        }
    }
    uart_write_string("GEMV PASS\r\n");
    return 0;
}
```

## 4.2 End-to-End Correctness Gate

**Encoder checksum**: After `tinyformer_encode()`, compute a simple additive checksum:

```c
uint32_t compute_enc_cksum(const int8_t output[16][32]) {
    uint32_t cksum = 0;
    for (int s = 0; s < 16; s++) {
        for (int d = 0; d < 32; d++) {
            cksum += (uint32_t)(uint8_t)output[s][d];
        }
    }
    return cksum;
}
```

**Correctness verification**:
1. Run baseline firmware → save `ENC_CKSUM_baseline[i]` and `pred_baseline[i]` for each sample
2. Run each accelerated build → compare `ENC_CKSUM_accel[i]` and `pred_accel[i]`
3. **Pass condition**: Must be **bit-identical** for all samples
4. If any mismatch → stop and debug accelerator (do not benchmark)

This ensures that the accelerators are not changing the numerical result.

---

# Performance Comparison

## 5.1 Expected Performance Metrics

### Baseline (No Acceleration)

| Metric | Value |
|--------|-------|
| Instructions per sample | ~930,000 |
| Estimated cycles (1-cycle mul) | ~930,000 |
| Realistic cycles (2-3 cycle mul) | 1,200,000 - 1,400,000 |
| Bottleneck | Multiply-bound (Q·K, Q·V, projections) |

### DOT8 Only

| Metric | Value |
|--------|-------|
| Instructions per sample | ~185,000 |
| Speedup vs baseline | **5.0× - 6.0×** |
| Improvement | Reduces loop overhead; better ILP |
| Remaining bottleneck | Some matvecsстill in software |

### EXP LUT Only

| Metric | Value |
|--------|-------|
| Instructions per sample | ~900,000 |
| Speedup vs baseline | **1.02×** (marginal) |
| Improvement | Softmax not the bottleneck |
| Note | Included for completeness; minimal impact |

### GEMV Only (Streams data via MMIO)

| Metric | Value |
|--------|-------|
| Instructions per sample | ~350,000 (CPU + MMIO overhead) |
| Speedup vs baseline | **2.5× - 3.0×** |
| Improvement | Parallelizes matvec compute |
| Overhead | MMIO CSR access (write X, W, b; read Y) |

### All Three (DOT8 + EXP LUT + GEMV)

| Metric | Value |
|--------|-------|
| Instructions per sample | ~140,000 |
| Speedup vs baseline | **6.5× - 7.0×** |
| Bottleneck shifts to | Memory (if any GEMV) / Control flow |
| Remaining optimizations | DMA for GEMV, wider datapaths |

---

## 5.2 Performance Measurement Methodology

**Do not benchmark until correctness is verified.**

### Hook points for cycle counting

**Option 1: RISC-V mcycle CSR** (if implemented in VexRiscv)

```c
static inline uint32_t read_mcycle(void) {
    uint32_t cycles;
    asm volatile("csrr %0, mcycle" : "=r"(cycles));
    return cycles;
}

void demo_run(void) {
    uint32_t start = read_mcycle();
    
    // ... run tinyformer_encode() and classifier ...
    
    uint32_t end = read_mcycle();
    uint32_t cycles = end - start;
    
    uart_write_string("CYCLES=");
    uart_write_uint32(cycles);
    uart_write_string("\r\n");
}
```

**Option 2: LiteX Timer CSR** (if available in SoC)

```c
// Peripheral address from generated CSR
#define TIMER_VALUE_ADDR  0xF0000000

void measure_encoder(void) {
    uint32_t start = *(volatile uint32_t *)TIMER_VALUE_ADDR;
    
    tinyformer_encode(input, output);
    
    uint32_t end = *(volatile uint32_t *)TIMER_VALUE_ADDR;
    uart_write_string("TIMER_CYCLES=");
    uart_write_uint32(end - start);
    uart_write_string("\r\n");
}
```

### Performance reporting format

```
MODE: BASELINE
Sample 0: pred=1 exp=1 ENC_CKSUM=0x12345678 CYCLES=950000
Sample 1: pred=2 exp=2 ENC_CKSUM=0xABCDEF00 CYCLES=955000
...
AVG_CYCLES=952000

MODE: DOT8
Sample 0: pred=1 exp=1 ENC_CKSUM=0x12345678 CYCLES=160000
...
AVG_CYCLES=160000 (Speedup: 5.95×)
```

---

# System Integration

## 6.1 Build & Deployment

### File Organization

```
litex_port/
├── common/                   # Shared implementation
│   ├── tinyformer.c
│   ├── tinyformer.h
│   ├── demo_samples.c        # Pre-quantized demo inputs
│   ├── demo_classifier.c     # Mean-pool + classifier head
│   ├── demo_runner.c         # Checksum + predict loop
│   ├── trained_weights.c     # Quantized model weights
│   └── uart_litex.c
├── baseline/
│   └── main_baseline.c       # Entry point: prints MODE
├── accel_dot8/
│   └── main_dot8.c
├── accel_lut/
│   └── main_lut.c
├── accel_gemv/
│   └── main_gemv.c
├── accel_dot8_lut/
│   └── main_dot8_lut.c
├── accel_all/
│   └── main_all.c
├── tests_dot8.c/.h
├── tests_lut.c/.h
├── tests_gemv.c/.h
└── ...

hw_extensions/
├── dot8/
│   ├── Dot8Plugin.scala       # VexRiscv plugin
│   ├── sw/dot8.h/.c           # C driver
│   └── ...
├── exp_lut/
│   ├── exp_lut.v
│   ├── litex/
│   ├── sw/exp_lut.h/.c
│   └── exp_lut_spec.md
├── gemv/
│   ├── rtl/gemv_core.v
│   ├── litex/gemv_periph.py   # LiteX integration
│   ├── sw/gemv.h/.c           # C driver
│   └── gemv_spec.md
└── ...
```

### Build Flags per Mode

| Mode | Compile Flags | Drivers Linked |
|------|---------------|-----------------|
| Baseline | `-DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART` | common + uart |
| DOT8 | + `-DUSE_DOT8_HW` | + dot8.c |
| LUT | + `-DUSE_EXP_LUT_HW -DEXP_LUT_USE_LITEX_CSR` | + exp_lut.c |
| GEMV | + `-DUSE_GEMV_HW -DGEMV_USE_LITEX_CSR` | + gemv.c |
| DOT8+LUT | All from DOT8 + LUT | dot8.c + exp_lut.c |
| All Three | All from DOT8 + LUT + GEMV | all drivers |

---

## 6.2 Bring-Up Checklist

### Phase 1: Foundation

- [ ] LiteX SoC memory initialized (memtest passes)
- [ ] UART works (echo test)
- [ ] Generated CSR headers available

### Phase 2: Baseline Correctness

- [ ] Compile baseline firmware
- [ ] Run on FPGA
- [ ] Observe `MODE: BASELINE` banner and per-sample `ENC_CKSUM` and `pred`/`exp` outputs
- [ ] Save logs as reference

### Phase 3: Self-Tests

- [ ] Run `tests_lut` → verify "LUT PASS" on UART
- [ ] Run `tests_gemv` → verify "GEMV PASS"
- [ ] Run `tests_dot8` → verify "DOT8 PASS"

### Phase 4: Accelerated Builds

For each mode (DOT8, LUT, GEMV, DOT8+LUT, All):
- [ ] Compile with correct flags
- [ ] Run on FPGA
- [ ] Verify `ENC_CKSUM` matches baseline for every sample
- [ ] Verify `pred`/`exp` match baseline

### Phase 5: Performance Measurement

Only after all correctness gates pass:
- [ ] Add cycle counting (mcycle or timer)
- [ ] Run baseline + all accelerated modes
- [ ] Compare cycles, calculate speedups

---

## 6.3 Troubleshooting

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| UART no output | UART not configured | Check CSR mapping, BAUD rate |
| ENC_CKSUM mismatch | Accelerator bug | Verify self-test passes, debug compute |
| pred mismatch | Quantization error | Check weight export, int8 saturation |
| Hang in GEMV test | MMIO address wrong | Verify `GEMV_BASE` or generated CSR headers |
| DOT8 instruction not recognized | Plugin not in VexRiscv | Add Dot8Plugin to SoC config, rebuild bitstream |

---

# Appendix: Algorithm Detail

## A.1 Quantization Strategy

All weights and activations are **int8 (-128..127)**, with **int32 accumulators**.

**Per-layer requantization**:
```c
// After accumulation in int32
int32_t acc = ...; // Result of dot product
acc = acc >> 7;     // Approximate division by 128, chosen empirically
int8_t result = saturate_int32_to_int8(acc);
```

The **shift by 7** is a crude scaling factor chosen to keep values in int8 range. More sophisticated quantization (per-layer or per-channel) could reduce accuracy loss.

## A.2 Softmax in Fixed-Point

Standard softmax: $\text{softmax}(x_i) = \frac{e^{x_i - \max_j x_j}}{\sum_k e^{x_k - \max_j x_j}}$

**Integer approximation**:
1. Compute max score (numerical stability)
2. Shift scores into range for LUT (approximately [-15, 0])
3. Look up exp values in Q10 fixed-point table
4. Compute normalized weights in Q15 fixed-point

No floating-point involved; the LUT is the only approximation.

## A.3 Data Format: Row-Major Matrix Storage

Matrices are stored **row-major** in C arrays:
```c
// W[D_out][D_in] stored as W[D_out * D_in] flat array
// W[i][j] = W[i * D_in + j]
```

This layout matches the nested loop structure in baseline code and simplifies GEMV streaming.

---

## Summary

This project demonstrates a three-stage hardware acceleration approach for TinyML inference:

1. **Algorithm**: Single-block TinyFormer encoder (147K multiplications, primarily matrix-vector operations)
2. **Baseline**: Pure software on RV32IM (~930K instructions)
3. **Accelerators**: 
   - DOT8 custom instruction (4-lane int8 dot products): ~5× speedup
   - EXP LUT peripheral (softmax): minimal impact (bottleneck elsewhere)
   - GEMV matrix-vector accelerator: ~3× speedup
   - All three combined: ~6.5-7.0× speedup

The design emphasizes **correctness verification** (checksum gates), **modularity** (each accelerator can be used independently), and **portability** (same C code runs with or without hardware, using compile-time flags).

