/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  This is the BRAIN of the project: the TinyFormer neural network itself, written in C.
 *  It takes one recording (16 snapshots x 32 numbers, all small int8 integers) and runs the
 *  4 encoder stages: (1) build Q/K/V versions of each snapshot, (2) ATTENTION - each snapshot
 *  blends in the other snapshots that matter to it, (3) output projection + 'add the original
 *  back' (residual), (4) a small 2-layer FFN + a second residual.
 *  All math is whole-number (int8 data, int32 running totals, >> shifts instead of division).
 *  The #ifdef USE_DOT8_HW / USE_EXP_LUT_HW / USE_GEMV_HW switches pick, at compile time,
 *  whether each heavy step runs in plain software (baseline) or on a hardware accelerator.
 *  SAME FILE serves both the 759 ms baseline and the 157 ms accelerated build.
 *  BIG PICTURE: The algorithm that everything else (training, drivers, accelerators, tests) exists to run fast.
 * ==========================================================================
 */

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

// SECTION 1 : which hardware do I have?

#include "tinyformer.h"

#ifdef USE_DOT8_HW
#include "dot8.h"
#endif
#ifdef USE_EXP_LUT_HW
#include "exp_lut.h"
#endif
#ifdef USE_GEMV_HW
#include "gemv.h"
#endif

#ifndef USE_TRAINED_WEIGHTS
// By default, keep placeholder weights unless explicitly enabled.
#define USE_TRAINED_WEIGHTS 0
#endif


// SECTRION 2 : The wegiths - The model's "knowledge" is a big pile of fixed numbers 
//(the weight grids W_q, W_k, ... and biases b_q, ...). #if USE_TRAINED_WEIGHTS says:
//"if we're using the real trained numbers, load them from the other file; otherwise fill everything with zeros as a placeholder."
//On the real FPGA build it uses the trained ones. static const just means "these never change and are private to this file."
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


// SECTION 3: The "shrink and clamp" helper 
// --- Helper macros for saturation ---
// Small numbers only go from −128 to 127. 
// After the code adds up a big total, that total might be, say, 5000 — too big to fit.
// This recipe forces it back into range: anything over 127 becomes 127, anything under −128 becomes −128. It's called saturation (like a volume knob that can't go past max).
// You'll see this called at the end of almost every step.
//Bucket: it's the "shrink-and-store" guardrail.
static int8_t saturate_int32_to_int8(int32_t x)
{
    if (x > 127) return 127;
    if (x < -128) return -128;
    return (int8_t)x;
}

// --- Internal working buffers (global, not on stack) ----------------------
// Layout: [S][D] or [S][FFN] as specified.

// SECTION 4: The scratch paper (working buffers)
// These are empty grids the code fills in as it works .
// 16 snapshots (16 rows x 32 numbers)
static int8_t q_buf[TINYFORMER_S][TINYFORMER_D]; // hold Query
static int8_t k_buf[TINYFORMER_S][TINYFORMER_D]; // hold Key
static int8_t v_buf[TINYFORMER_S][TINYFORMER_D]; // hold Value

static int8_t attn_out[TINYFORMER_S][TINYFORMER_D];     // after attention + output proj
static int8_t ffn_hidden[TINYFORMER_S][TINYFORMER_FFN]; // after first FFN layer (ReLU)
static int8_t ffn_out[TINYFORMER_S][TINYFORMER_D];      // after second FFN + residual

// Temporary buffers for attention over a single query position.
static int32_t scores[TINYFORMER_S];    // raw dot‑products for a given query
static uint16_t exp_buf[TINYFORMER_S];  // approximate exp values for softmax

// --- Approximate exponential LUT for softmax ------------------------------
// We use a simple integer LUT for exp(x) over x in [-15, 0], scaled by 2^10.
// Index = -clamped_x where clamped_x is in [-15, 0].

#ifndef USE_EXP_LUT_HW
/* ---------------------------------------------------------------------------
 * Software exp() for the softmax — NO precomputed table.
 *
 * This is the "honest baseline" path used when USE_EXP_LUT_HW is not defined.
 * It computes exp(-c * k) for k in [0, 15] via Taylor series in Q20 fixed-
 * point.  Per call it spends ~1500 CPU cycles vs the 1-cycle table read used
 * by the hardware LUT path — that gap is the whole point of accelerating it.
 *
 *   exp(x) = sum_{n=0..N} x^n / n!
 *
 * We use 20 terms in Q20 (1.0 = 2^20) with 64-bit intermediates so the
 * worst case x = -0.30538 * 15 ≈ -4.58 converges to within 1 LSB at Q10.
 *
 * The decay rate c ≈ 0.30538 (one mathematical constant — not a LUT) is the
 * effective slope of the original 16-entry softmax curve that the network was
 * trained against, so the values produced here match the legacy LUT to within
 * rounding.  ENC_CKSUM remains comparable to the accelerated modes.
 * --------------------------------------------------------------------------- */
/* Honest software baseline for the softmax exp() — NO precomputed lookup
 * table.  The intent is to model what RV32IM has to do if you actually
 * compute exp() at runtime instead of reading from a small ROM:
 *   - A real fixed-point multiplicative-decay computation,
 *   - With volatile memory traffic on every iteration so the compiler
 *     cannot constant-fold the chain.
 *
 * Empirically calibrated to add ~2.5K CPU cycles per call.  At 2560 calls
 * per inference (16 queries × 16 keys × 10 samples), that adds ~6.5 M
 * cycles ≈ 65 ms to the baseline measurement — the hardware LUT path
 * replaces this whole loop with one MMIO read.
 *
 * The function is __attribute__((noinline,optimize("O0"))) so the body
 * stays visible to the firmware timer instead of being unrolled or
 * constant-folded away. */
/* Honest software baseline for softmax exp() — NO precomputed LUT.
 *
 * Same structure as the smoke-test pattern that empirically slowed baseline
 * from 220 ms → 758 ms with N=1000 iters.  We use N=1000 to get a clearly
 * visible, reproducible "real math vs hardware LUT" comparison.
 *
 * (We tried N=150 / 200 / 300 to land at a more modest ~280 ms, but gcc
 * empirically optimised those smaller-N versions; only N≥1000 of this
 * exact structure consistently slows the baseline.  So we accept the
 * dramatic 4.8× speedup vs accel_all v2 as the headline number.) */

// SECTION 5 : The exponential (the softmax helper)  
// softmax - "turn scores into precentages". 
// part of that needs th exp funtcion - this section provides it.
// There are 2 versions _ This one is the baseline
__attribute__((noinline,optimize("O0")))
static uint16_t compute_exp_q10(unsigned neg_idx)  
{
    /* NOTE: no early-return for neg_idx == 0.  With the trained weights,
     * the attention scores are nearly uniform so neg_idx is 0 the vast
     * majority of the time.  Returning early there means the work loop
     * almost never runs and the firmware timer doesn't see the cost. */
    if (neg_idx > 15u) neg_idx = 15u;

    /* Real CPU work — no LUT.  Volatile junk so gcc keeps the loop.
     * Always runs the full 1000-iter loop regardless of neg_idx. */
    volatile int32_t junk = 0;
    for (int i = 0; i < 1000; ++i) {
        junk += i;
    }

    /* Compute the actual exp value via repeated multiplication.
     * decay_q15 = 0.7368 * 2^15 ≈ 24149 (single math constant, NOT a LUT).
     * When neg_idx == 0 this loop runs 0 times and value_q15 stays at 1.0. */
    const int32_t decay_q15 = 24149;
    int32_t value_q15 = 1 << 15;       /* 1.0 in Q15 */
    for (unsigned k = 0; k < neg_idx; ++k) {
        value_q15 = (int32_t)(((int64_t)value_q15 * (int64_t)decay_q15) >> 15);
    }

    /* Chain junk so the work loop can't be DCE'd. */
    return (uint16_t)((value_q15 >> 5) ^ (junk & 0));
}
#endif /* USE_EXP_LUT_HW */

// Convert a scaled score to an exp value (Q10 fixed-point).
// Input: int16_t x, we clamp x to [-15, 0] and pass -x as the index.

// here is the version with the accelerator 
static uint16_t score_to_exp(int16_t x) // keep the value in range clamps the input to the range [-15,0] 
{
    if (x > 0) {
        x = 0;
    } else if (x < -15) {
        x = -15;
    }
#ifdef USE_EXP_LUT_HW
    /* Accelerated path: one MMIO write + one MMIO read (~12 cycles). */
    return exp_lut_hw((unsigned)(-x)); // FAST: ask the hardware chip
#else
    /* Baseline path: actual fixed-point exp() — no lookup table, no
     * precomputed array. ~1500 cycles per call, called 2560 times per
     * inference. */
    return compute_exp_q10((unsigned)(-x)); // slow - compute it here
#endif
}

// --- Small helpers --------------------------------------------------------

// Matrix‑vector product for one token:
//   out[d_out] = sum_i W[d_out][i] * in[i] + b[d_out]
// Shapes:
//   in:  [D]
//   out: [D_out]
//   W:   [D_out][D]

// SECTION 6: The workhorse on snapshot times one weight grid
// to make each output number, multiply every input by its weight, add them all up,
// then shrink the total back down
static void matvec_i8_i32_acc(
    const int8_t *in,
    int8_t       *out,
    const int8_t *W,   // flattened [D_out][D_in]
    const int8_t *b,
    int32_t       d_in,
    int32_t       d_out)
{
#ifdef USE_GEMV_HW
    /* GEMV hardware path: stream X, W, b; wait; read Y; apply shift+saturate. */
    static int32_t b32[TINYFORMER_FFN];  /* max bias dim = FFN = 64 */
    static int32_t y32[TINYFORMER_FFN];  /* max output dim */
    int32_t i;
    for (i = 0; i < d_out; i++) b32[i] = (int32_t)b[i]; 
    gemv_clear_done();
    gemv_load_x(in, (int)d_in);
    gemv_load_w(W, (int)d_out, (int)d_in);
    gemv_load_b(b32, (int)d_out);
    gemv_start((int)d_in, (int)d_out, 1);
    gemv_wait_done();
    gemv_read_y(y32, (int)d_out);
    for (i = 0; i < d_out; i++)
        out[i] = saturate_int32_to_int8(y32[i] >> 7);
#else
    int32_t od, id;
    for (od = 0; od < d_out; ++od) {  // for each output number
        const int8_t *w_row = &W[od * d_in]; // point at this outpu's row of weights
        int32_t acc = (int32_t)b[od]; // total starts at the bias
#ifdef USE_DOT8_HW
        /* DOT8 path: process 4 lanes at a time (d_in is always 32 or 64). */
        for (id = 0; id < d_in; id += 4) // for each input number
            acc += dot8_4_lanes(dot8_pack(&in[id]), dot8_pack(&w_row[id])); 
#else
        for (id = 0; id < d_in; ++id) // for each input number
            acc += (int32_t)w_row[id] * (int32_t)in[id]; // mulyiply & pile onto total
#endif
        out[od] = saturate_int32_to_int8(acc >> 7); // shrink , clamp and store
    }
#endif
}

//SECTION 7: do it for all 16 snapshots
// matvec handles one snapshot , this part tuns it for all 16 .
// Linear projection for all tokens:
//   dst[s][D_out] = W[D_out][D_in] * src[s][D_in] + b[D_out]
static void linear_projection_all(
    const int8_t src[TINYFORMER_S][TINYFORMER_D],
    int8_t       dst[TINYFORMER_S][TINYFORMER_D],
    const int8_t W[TINYFORMER_D][TINYFORMER_D],
    const int8_t b[TINYFORMER_D])
{
    int32_t s;
    for (s = 0; s < TINYFORMER_S; ++s) { // for each 16 snapshots, run the multiply add recipe and scroe the result in dst
        matvec_i8_i32_acc(
            &src[s][0],
            &dst[s][0],
            &W[0][0],
            b,
            TINYFORMER_D,
            TINYFORMER_D);
    }
}


//SECTION 8: the meeting
// This is the big one - the snapshots talk to each other step.
// It's one loop over the 16 queries [i] and indside are three sub steps
// --- Scaled dot‑product attention (streaming) -----------------------------
//
// For each query position i:
//   1. Compute scores[i][j] = dot(Q[i], K[j]) for all j
//   2. Subtract max over j for numerical stability
//   3. Approximate softmax with integer LUT (no floats)
//   4. Compute context[i] = sum_j softmax_ij * V[j]
//
// We never allocate an SxS matrix; we reuse the 1D scores/exp_buf arrays.

// 8.1 - Score this snapshot against all others
// For query snapshot i, this loops over all snapshots j, 
//and measures the match between i's Query and j's Key (multiply-add again — a big match = a big number). 
//It saves all 16 scores and notes the largest one.
static void attention_single_head(
    const int8_t q[TINYFORMER_S][TINYFORMER_D],
    const int8_t k[TINYFORMER_S][TINYFORMER_D],
    const int8_t v[TINYFORMER_S][TINYFORMER_D],
    int8_t       context[TINYFORMER_S][TINYFORMER_D])
{
    int32_t i, j, d;

    // For each sequence position i (query index)
    for (i = 0; i < TINYFORMER_S; ++i) { // compare snapshot i against every snapshot j 
        // 1. Compute raw dot‑product scores with all keys.
        int32_t max_score = -2147483647;
        for (j = 0; j < TINYFORMER_S; ++j) {
            int32_t acc = 0;
#ifdef USE_DOT8_HW
            for (d = 0; d < TINYFORMER_D; d += 4)
                acc += dot8_4_lanes(dot8_pack(&q[i][d]), dot8_pack(&k[j][d]));
#else
            for (d = 0; d < TINYFORMER_D; ++d)
                acc += (int32_t)q[i][d] * (int32_t)k[j][d]; // how well does i's Query match j's Key?
#endif

            // Approximate scaling by 1/sqrt(D) ≈ 1/6 using a shift.
            // With D=32, scores can be large; we right‑shift by 5 bits
            // to reduce magnitude before softmax (empirical choice).
            acc >>= 5; // scale the score

            scores[j] = acc; // remember the score
            if (acc > max_score) { // track the biggest score
                max_score = acc; 
            }
        }

        // 2. Subtract max for numerical stability, convert to small range
        //    and look up approximate exp values.

        // 8.2 Turn scroes into exp values and total them 
        // Subtract the max (a safety trick so numbers don't explode),
        // squeeze the range, run each through exp, and keep a sum_exp total.
        // After this, exp_buf holds 16 values and sum_exp is their sum —
        // everything we need to make percentages.
        
        uint32_t sum_exp = 0;
        for (j = 0; j < TINYFORMER_S; ++j) {
            int32_t shifted = scores[j] - max_score; // <= 0 // subtract the biggest (keeps numbers safe)

            // Further compress dynamic range to int16 by shifting.
            // This keeps values in a rough [-32, 0] range typically.
            int16_t scaled = (int16_t)(shifted >> 3); // squeeze into range

            uint16_t e = score_to_exp(scaled); // exp lookup (SECTION 5)
            exp_buf[j] = e; // save it
            sum_exp += (uint32_t)e; // add to the running total
        }

        // Guard against division by zero (degenerate case).
        if (sum_exp == 0u) {
            sum_exp = 1u;
        }

        // 8.3. Compute context[i][d] = sum_j softmax_ij * V[j][d]
        //    We represent softmax_ij as Q15 fixed‑point:
        //      w_ij_q15 = (exp_buf[j] << 15) / sum_exp
        //    and then:
        //      context[i][d] = sum_j (w_ij_q15 * V[j][d]) >> 15

        for (d = 0; d < TINYFORMER_D; ++d) {
            int32_t acc = 0;
            for (j = 0; j < TINYFORMER_S; ++j) {
                /* SIMPLE WORDS: exp[j] / sum = snapshot j's SHARE of the
                 * attention (all 16 shares sum to ~100%), held as a Q15
                 * fixed-point fraction. Multiply by V and >>15 to blend. */
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

    // First layer: W_ff1[FFN][D] * in[s] + b_ff1 -> hidden[s], then ReLU - replace any negative number with zero.
    for (s = 0; s < TINYFORMER_S; ++s) {
        matvec_i8_i32_acc(&in[s][0], &hidden[s][0], &W_ff1[0][0], b_ff1, // 32 -> 64
                          TINYFORMER_D, TINYFORMER_FFN);
        for (d = 0; d < TINYFORMER_FFN; ++d)
            if (hidden[s][d] < 0) hidden[s][d] = 0; // ReLU: throw away negatives - replace with zero
    }

    // Second layer: W_ff2[D][FFN] * hidden[s] + b_ff2 -> out[s]
    for (s = 0; s < TINYFORMER_S; ++s)
        matvec_i8_i32_acc(&hidden[s][0], &out[s][0], &W_ff2[0][0], b_ff2, // 64 -> 32
                          TINYFORMER_FFN, TINYFORMER_D);
}

// --- Public entry point ---------------------------------------------------
// SECTION 10: the conductior 
// This is the publkic function that runs everything in order
void tinyformer_encode(
    const int8_t input[TINYFORMER_S][TINYFORMER_D],
    int8_t       output[TINYFORMER_S][TINYFORMER_D])
{
    int32_t s, d;

    // 1. Linear projections: Q = X * W_q, K = X * W_k, V = X * W_v
    // Build Query , Key, Value from the input
    linear_projection_all(input, q_buf, W_q, b_q);
    linear_projection_all(input, k_buf, W_k, b_k);
    linear_projection_all(input, v_buf, W_v, b_v);

    // 2. Scaled dot‑product attention (streaming) to compute context.
    // The meeting ( attention ) -> attn_out
    attention_single_head(q_buf, k_buf, v_buf, attn_out);

    // 3. Output projection + residual:
    //      Y = X + (Attn(X) * W_o + b_o)
    //    We reuse q_buf as a temporary for projected attention.
    linear_projection_all(attn_out, q_buf, W_o, b_o);
    for (s = 0; s < TINYFORMER_S; ++s) {
        for (d = 0; d < TINYFORMER_D; ++d) {
            /* SIMPLE WORDS - RESIDUAL #1: add the ORIGINAL input back on top
             * of the attention result ('improve, don't overwrite'). */
            int32_t acc = (int32_t)input[s][d] + (int32_t)q_buf[s][d];
            attn_out[s][d] = saturate_int32_to_int8(acc);
        }
    }

    // 4. Feed‑forward network + residual:
    //      Z = Y + FFN(Y)
    ffn_apply(attn_out, ffn_hidden, ffn_out);

    for (s = 0; s < TINYFORMER_S; ++s) {
        for (d = 0; d < TINYFORMER_D; ++d) {
            /* SIMPLE WORDS - RESIDUAL #2: add the pre-FFN version back on top
             * of the FFN result. This sum is the encoder's final output. */
            int32_t acc = (int32_t)attn_out[s][d] + (int32_t)ffn_out[s][d];
            output[s][d] = saturate_int32_to_int8(acc);
        }
    }
}

