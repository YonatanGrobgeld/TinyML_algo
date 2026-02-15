// TinyFormer encoder block implementation for RV32IM bare‑metal.
//
// Constraints:
//  - Sequence length S = 16
//  - Model dimension D = 32
//  - Single attention head
//  - int8 weights & activations, int32 accumulators
//  - Streaming/tiled attention: NEVER allocate an SxS matrix
//  - No dynamic allocation, no OS, no threads, no SIMD, no PULP intrinsics
//
// This file is intentionally self‑contained and uses only fixed‑size arrays.

#include "tinyformer.h"

#ifndef USE_TRAINED_WEIGHTS
// By default, keep placeholder weights unless explicitly enabled.
#define USE_TRAINED_WEIGHTS 0
#endif

#if USE_TRAINED_WEIGHTS
#include "trained_weights.h"
#else

// --- Dummy weights (placeholders) -----------------------------------------
// Real deployments should replace these with trained parameters.
// Using partial initializers so that the remaining elements are zero‑filled
// by the C compiler.

// Linear projections: [D_out][D_in] with D_out = D_in = TINYFORMER_D
static const int8_t W_q[TINYFORMER_D][TINYFORMER_D] = { { 0 } };
static const int8_t W_k[TINYFORMER_D][TINYFORMER_D] = { { 0 } };
static const int8_t W_v[TINYFORMER_D][TINYFORMER_D] = { { 0 } };
static const int8_t W_o[TINYFORMER_D][TINYFORMER_D] = { { 0 } };

// Feed‑forward: D -> FFN -> D
static const int8_t W_ff1[TINYFORMER_FFN][TINYFORMER_D] = { { 0 } };
static const int8_t W_ff2[TINYFORMER_D][TINYFORMER_FFN] = { { 0 } };

// Optional biases (all zeros by default).
static const int8_t b_q[TINYFORMER_D] = { 0 };
static const int8_t b_k[TINYFORMER_D] = { 0 };
static const int8_t b_v[TINYFORMER_D] = { 0 };
static const int8_t b_o[TINYFORMER_D] = { 0 };
static const int8_t b_ff1[TINYFORMER_FFN] = { 0 };
static const int8_t b_ff2[TINYFORMER_D] = { 0 };

#endif  // USE_TRAINED_WEIGHTS

// --- Helper macros for saturation ---

static int8_t saturate_int32_to_int8(int32_t x)
{
    if (x > 127) return 127;
    if (x < -128) return -128;
    return (int8_t)x;
}

// --- Internal working buffers (global, not on stack) ----------------------
// Layout: [S][D] or [S][FFN] as specified.

static int8_t q_buf[TINYFORMER_S][TINYFORMER_D];
static int8_t k_buf[TINYFORMER_S][TINYFORMER_D];
static int8_t v_buf[TINYFORMER_S][TINYFORMER_D];

static int8_t attn_out[TINYFORMER_S][TINYFORMER_D];     // after attention + output proj
static int8_t ffn_hidden[TINYFORMER_S][TINYFORMER_FFN]; // after first FFN layer (ReLU)
static int8_t ffn_out[TINYFORMER_S][TINYFORMER_D];      // after second FFN + residual

// Temporary buffers for attention over a single query position.
static int32_t scores[TINYFORMER_S];    // raw dot‑products for a given query
static uint16_t exp_buf[TINYFORMER_S];  // approximate exp values for softmax

// --- Approximate exponential LUT for softmax ------------------------------
// We use a simple integer LUT for exp(x) over x in [-15, 0], scaled by 2^10.
// Index = -clamped_x where clamped_x is in [-15, 0].

static const uint16_t exp_lut[16] = {
    1024, // e^0   ~ 1.0  * 2^10
     754, // e^-1  ~ 0.74
     556, // e^-2  ~ 0.55
     410, // e^-3
     302, // e^-4
     223, // e^-5
     165, // e^-6
     122, // e^-7
      90, // e^-8
      67, // e^-9
      50, // e^-10
      37, // e^-11
      28, // e^-12
      21, // e^-13
      16, // e^-14
      12  // e^-15
};

// Convert a scaled score to an index into exp_lut.
// Input: int16_t x, we clamp x to [-15, 0] and return -x as index.
static uint16_t score_to_exp(int16_t x)
{
    if (x > 0) {
        x = 0;
    } else if (x < -15) {
        x = -15;
    }
    return exp_lut[(uint16_t)(-x)];
}

// --- Small helpers --------------------------------------------------------

// Matrix‑vector product for one token:
//   out[d_out] = sum_i W[d_out][i] * in[i] + b[d_out]
// Shapes:
//   in:  [D]
//   out: [D_out]
//   W:   [D_out][D]
static void matvec_i8_i32_acc(
    const int8_t *in,
    int8_t       *out,
    const int8_t *W,   // flattened [D_out][D_in]
    const int8_t *b,
    int32_t       d_in,
    int32_t       d_out)
{
    int32_t od, id;
    for (od = 0; od < d_out; ++od) {
        const int8_t *w_row = &W[od * d_in];
        int32_t acc = (int32_t)b[od];
        for (id = 0; id < d_in; ++id) {
            acc += (int32_t)w_row[id] * (int32_t)in[id];
        }
        out[od] = saturate_int32_to_int8(acc >> 7); // crude scaling to keep in int8 range
    }
}

// Linear projection for all tokens:
//   dst[s][D_out] = W[D_out][D_in] * src[s][D_in] + b[D_out]
static void linear_projection_all(
    const int8_t src[TINYFORMER_S][TINYFORMER_D],
    int8_t       dst[TINYFORMER_S][TINYFORMER_D],
    const int8_t W[TINYFORMER_D][TINYFORMER_D],
    const int8_t b[TINYFORMER_D])
{
    int32_t s;
    for (s = 0; s < TINYFORMER_S; ++s) {
        matvec_i8_i32_acc(
            &src[s][0],
            &dst[s][0],
            &W[0][0],
            b,
            TINYFORMER_D,
            TINYFORMER_D);
    }
}

// --- Scaled dot‑product attention (streaming) -----------------------------
//
// For each query position i:
//   1. Compute scores[i][j] = dot(Q[i], K[j]) for all j
//   2. Subtract max over j for numerical stability
//   3. Approximate softmax with integer LUT (no floats)
//   4. Compute context[i] = sum_j softmax_ij * V[j]
//
// We never allocate an SxS matrix; we reuse the 1D scores/exp_buf arrays.

static void attention_single_head(
    const int8_t q[TINYFORMER_S][TINYFORMER_D],
    const int8_t k[TINYFORMER_S][TINYFORMER_D],
    const int8_t v[TINYFORMER_S][TINYFORMER_D],
    int8_t       context[TINYFORMER_S][TINYFORMER_D])
{
    int32_t i, j, d;

    // For each sequence position i (query index)
    for (i = 0; i < TINYFORMER_S; ++i) {
        // 1. Compute raw dot‑product scores with all keys.
        int32_t max_score = -2147483647;
        for (j = 0; j < TINYFORMER_S; ++j) {
            int32_t acc = 0;
            for (d = 0; d < TINYFORMER_D; ++d) {
                acc += (int32_t)q[i][d] * (int32_t)k[j][d];
            }

            // Approximate scaling by 1/sqrt(D) ≈ 1/6 using a shift.
            // With D=32, scores can be large; we right‑shift by 5 bits
            // to reduce magnitude before softmax (empirical choice).
            acc >>= 5;

            scores[j] = acc;
            if (acc > max_score) {
                max_score = acc;
            }
        }

        // 2. Subtract max for numerical stability, convert to small range
        //    and look up approximate exp values.
        uint32_t sum_exp = 0;
        for (j = 0; j < TINYFORMER_S; ++j) {
            int32_t shifted = scores[j] - max_score; // <= 0

            // Further compress dynamic range to int16 by shifting.
            // This keeps values in a rough [-32, 0] range typically.
            int16_t scaled = (int16_t)(shifted >> 3);

            uint16_t e = score_to_exp(scaled);
            exp_buf[j] = e;
            sum_exp += (uint32_t)e;
        }

        // Guard against division by zero (degenerate case).
        if (sum_exp == 0u) {
            sum_exp = 1u;
        }

        // 3. Compute context[i][d] = sum_j softmax_ij * V[j][d]
        //    We represent softmax_ij as Q15 fixed‑point:
        //      w_ij_q15 = (exp_buf[j] << 15) / sum_exp
        //    and then:
        //      context[i][d] = sum_j (w_ij_q15 * V[j][d]) >> 15

        for (d = 0; d < TINYFORMER_D; ++d) {
            int32_t acc = 0;
            for (j = 0; j < TINYFORMER_S; ++j) {
                uint16_t w_q15 = (uint16_t)(((uint32_t)exp_buf[j] << 15) / sum_exp);
                acc += ((int32_t)w_q15 * (int32_t)v[j][d]) >> 15;
            }
            context[i][d] = saturate_int32_to_int8(acc);
        }
    }
}

// --- Feed‑forward network (FFN) -------------------------------------------
//
// For each token x (dimension D):
//   h = ReLU(W_ff1 * x + b_ff1)   // h in R^FFN
//   y = W_ff2 * h + b_ff2        // y in R^D

static void ffn_apply(
    const int8_t in[TINYFORMER_S][TINYFORMER_D],
    int8_t       hidden[TINYFORMER_S][TINYFORMER_FFN],
    int8_t       out[TINYFORMER_S][TINYFORMER_D])
{
    int32_t s, d;

    // First layer + ReLU
    for (s = 0; s < TINYFORMER_S; ++s) {
        // h = W_ff1 * in[s] + b_ff1
        // W_ff1: [FFN][D]
        for (d = 0; d < TINYFORMER_FFN; ++d) {
            const int8_t *w_row = &W_ff1[d][0];
            int32_t acc = (int32_t)b_ff1[d];
            int32_t k;
            for (k = 0; k < TINYFORMER_D; ++k) {
                acc += (int32_t)w_row[k] * (int32_t)in[s][k];
            }
            // Simple scaling then ReLU in int8 space.
            acc >>= 7;
            if (acc < 0) {
                hidden[s][d] = 0;
            } else {
                hidden[s][d] = saturate_int32_to_int8(acc);
            }
        }
    }

    // Second layer
    for (s = 0; s < TINYFORMER_S; ++s) {
        for (d = 0; d < TINYFORMER_D; ++d) {
            const int8_t *w_row = &W_ff2[d][0];
            int32_t acc = (int32_t)b_ff2[d];
            int32_t k;
            for (k = 0; k < TINYFORMER_FFN; ++k) {
                acc += (int32_t)w_row[k] * (int32_t)hidden[s][k];
            }
            acc >>= 7;
            out[s][d] = saturate_int32_to_int8(acc);
        }
    }
}

// --- Public entry point ---------------------------------------------------

void tinyformer_encode(
    const int8_t input[TINYFORMER_S][TINYFORMER_D],
    int8_t       output[TINYFORMER_S][TINYFORMER_D])
{
    int32_t s, d;

    // 1. Linear projections: Q = X * W_q, K = X * W_k, V = X * W_v
    linear_projection_all(input, q_buf, W_q, b_q);
    linear_projection_all(input, k_buf, W_k, b_k);
    linear_projection_all(input, v_buf, W_v, b_v);

    // 2. Scaled dot‑product attention (streaming) to compute context.
    attention_single_head(q_buf, k_buf, v_buf, attn_out);

    // 3. Output projection + residual:
    //      Y = X + (Attn(X) * W_o + b_o)
    //    We reuse q_buf as a temporary for projected attention.
    linear_projection_all(attn_out, q_buf, W_o, b_o);
    for (s = 0; s < TINYFORMER_S; ++s) {
        for (d = 0; d < TINYFORMER_D; ++d) {
            int32_t acc = (int32_t)input[s][d] + (int32_t)q_buf[s][d];
            attn_out[s][d] = saturate_int32_to_int8(acc);
        }
    }

    // 4. Feed‑forward network + residual:
    //      Z = Y + FFN(Y)
    ffn_apply(attn_out, ffn_hidden, ffn_out);

    for (s = 0; s < TINYFORMER_S; ++s) {
        for (d = 0; d < TINYFORMER_D; ++d) {
            int32_t acc = (int32_t)attn_out[s][d] + (int32_t)ffn_out[s][d];
            output[s][d] = saturate_int32_to_int8(acc);
        }
    }
}

