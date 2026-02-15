// TinyFormer encoder for RV32IM bare‑metal (LiteX / VexRiscv)
// Portable C API, no dynamic allocation, fixed shapes.
//
// Sequence length: S = 16
// Model dimension: D = 32
// Single attention head, int8 weights/activations, int32 accumulators.

#ifndef TINYFORMER_H
#define TINYFORMER_H

#include <stdint.h>

// --- Model hyperparameters (fixed for this kernel) ---
#define TINYFORMER_S   16
#define TINYFORMER_D   32
#define TINYFORMER_FFN 64

// Public API: encode a single TinyFormer block.
//
//  - input  : [TINYFORMER_S][TINYFORMER_D] int8_t tokens
//  - output : [TINYFORMER_S][TINYFORMER_D] int8_t tokens
//
// The function:
//  1. Applies Q/K/V projections
//  2. Computes scaled dot‑product attention (streaming, no SxS buffer)
//  3. Applies output projection + residual
//  4. Applies feed‑forward network (ReLU) + residual
//
// Weights are stored as global const int8_t arrays in tinyformer.c
// and can be replaced by real trained parameters later.
void tinyformer_encode(
    const int8_t input[TINYFORMER_S][TINYFORMER_D],
    int8_t       output[TINYFORMER_S][TINYFORMER_D]);

#endif // TINYFORMER_H

