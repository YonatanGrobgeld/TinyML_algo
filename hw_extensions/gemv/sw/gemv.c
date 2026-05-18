/*
 * GEMV accelerator — C driver (V2).
 *
 * V2 vs V1:
 *  - X_IN and W_IN are now 32-bit CSRs that take 4 packed signed int8 lanes
 *    per write (lane 0 = LSB).  4x fewer MMIO writes for X and W loading.
 *  - The hardware does a 4-lane MAC per cycle, so compute is 4x faster too.
 *  - Public API (gemv_load_x / gemv_load_w / gemv_load_b / gemv_start / ...)
 *    is unchanged — callers still pass int8 arrays; this driver packs them.
 *
 * START and CLEAR_DONE are one-cycle pulses driven by the LiteX wrapper.
 * Y read pointer is advanced by writing to Y_NEXT (not by reading Y_OUT).
 *
 * Two backends: GEMV_USE_LITEX_CSR (generated/csr.h) or GEMV_BASE (raw MMIO).
 */

#include "gemv.h"
#include <stddef.h>

/* --- CSR access: LiteX generated or raw MMIO --- */
#if defined(GEMV_USE_LITEX_CSR)
#  include <generated/csr.h>
#  define GEMV_READ_CTRL()     gemv_ctrl_read()
#  define GEMV_WRITE_CTRL(v)   gemv_ctrl_write(v)
#  define GEMV_READ_STATUS()   gemv_status_read()
/* V2: X_IN and W_IN take a 32-bit packed word (4 int8 lanes). */
#  define GEMV_WRITE_X(v)      gemv_x_in_write((uint32_t)(v))
#  define GEMV_WRITE_W(v)      gemv_w_in_write((uint32_t)(v))
#  define GEMV_WRITE_B(v)      gemv_b_in_write((uint32_t)(v))
#  define GEMV_READ_Y()        gemv_y_out_read()
#  define GEMV_WRITE_Y_NEXT()  gemv_y_next_write(1u)
#else
#  ifndef GEMV_BASE
#    error "Define GEMV_BASE or GEMV_USE_LITEX_CSR"
#  endif
#  define GEMV_REG(off)   (*(volatile uint32_t *)(GEMV_BASE + (off)))
#  define GEMV_READ_CTRL()    GEMV_REG(GEMV_CTRL)
#  define GEMV_WRITE_CTRL(v) (GEMV_REG(GEMV_CTRL) = (uint32_t)(v))
#  define GEMV_READ_STATUS() GEMV_REG(GEMV_STATUS)
#  define GEMV_WRITE_X(v)    (GEMV_REG(GEMV_X_IN) = (uint32_t)(v))
#  define GEMV_WRITE_W(v)    (GEMV_REG(GEMV_W_IN) = (uint32_t)(v))
#  define GEMV_WRITE_B(v)    (GEMV_REG(GEMV_B_IN) = (uint32_t)(v))
#  define GEMV_READ_Y()      GEMV_REG(GEMV_Y_OUT)
#  define GEMV_WRITE_Y_NEXT() (GEMV_REG(GEMV_Y_NEXT) = 1u)
#endif

static uintptr_t s_gemv_base;

/* Pack four signed int8 lanes into a 32-bit word, lane 0 = LSB. */
static inline uint32_t pack4_i8(const int8_t *p)
{
    return  ((uint32_t)(uint8_t)p[0])
         | (((uint32_t)(uint8_t)p[1]) << 8)
         | (((uint32_t)(uint8_t)p[2]) << 16)
         | (((uint32_t)(uint8_t)p[3]) << 24);
}

void gemv_init(uintptr_t base_addr)
{
    s_gemv_base = base_addr;
#if !defined(GEMV_USE_LITEX_CSR)
    (void)s_gemv_base; /* unused when using LiteX CSRs */
#endif
}

void gemv_clear_done(void)
{
    /* Single write with clear_done bit = pulse on LiteX wrapper */
    GEMV_WRITE_CTRL(GEMV_CTRL_CLEAR_DONE);
}

/* V2: write 4 lanes per CSR access.  len is always 32 or 64 (divisible by 4). */
void gemv_load_x(const int8_t *x, int len)
{
    if (x == NULL) return;
    for (int i = 0; i < len; i += 4)
        GEMV_WRITE_X(pack4_i8(&x[i]));
}

/* V2: write 4 lanes per CSR access.  Total bytes = out_dim*len, divisible by 4. */
void gemv_load_w(const int8_t *w, int out_dim, int len)
{
    if (w == NULL) return;
    int total = out_dim * len;
    for (int i = 0; i < total; i += 4)
        GEMV_WRITE_W(pack4_i8(&w[i]));
}

void gemv_load_b(const int32_t *b, int out_dim)
{
    if (b == NULL) return;
    for (int i = 0; i < out_dim; i++)
        GEMV_WRITE_B(b[i]);
}

void gemv_start(int len, int out_dim, int enable_bias)
{
    uint32_t config = 0;
    if (len == 64)     config |= GEMV_CTRL_LEN_64;
    if (out_dim == 64) config |= GEMV_CTRL_OUT_DIM_64;
    if (enable_bias)   config |= GEMV_CTRL_ENABLE_BIAS;
    /* Write config bits first so ctrl.storage latches them before START fires.
     * The LiteX wrapper reads len_64/out_dim_64/bias_en from ctrl.storage. */
    GEMV_WRITE_CTRL(config);
    GEMV_WRITE_CTRL(config | GEMV_CTRL_START);
}

void gemv_wait_done(void)
{
    /* 2M iterations at ~10 ns/iter ≈ 20 ms safety timeout — far longer than
     * any valid GEMV run (which is now microseconds). */
    volatile uint32_t limit = 2000000u;
    while (limit-- > 0) {
        if (GEMV_READ_STATUS() & GEMV_STATUS_DONE)
            return;
    }
}

void gemv_read_y(int32_t *y, int out_dim)
{
    if (y == NULL) return;
    for (int i = 0; i < out_dim; i++) {
        y[i] = (int32_t)GEMV_READ_Y();
        GEMV_WRITE_Y_NEXT();  /* advance Y read pointer for next element */
    }
}
