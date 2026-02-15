/*
 * GEMV accelerator — C driver.
 * Defining USE_GEMV_HW requires the SoC to include the corresponding HW block; otherwise keep macro off.
 *
 * START and CLEAR_DONE are treated as one-cycle pulses by the LiteX wrapper:
 * write CTRL with the corresponding bit set; the wrapper drives start/clear_done
 * for one cycle. Y read pointer is advanced by writing to Y_NEXT (not by reading Y_OUT).
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
#  define GEMV_WRITE_X(v)      gemv_x_in_write((uint32_t)(uint8_t)(v))
#  define GEMV_WRITE_W(v)      gemv_w_in_write((uint32_t)(uint8_t)(v))
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
#  define GEMV_WRITE_X(v)    (GEMV_REG(GEMV_X_IN) = (uint32_t)(uint8_t)(v))
#  define GEMV_WRITE_W(v)    (GEMV_REG(GEMV_W_IN) = (uint32_t)(uint8_t)(v))
#  define GEMV_WRITE_B(v)    (GEMV_REG(GEMV_B_IN) = (uint32_t)(v))
#  define GEMV_READ_Y()      GEMV_REG(GEMV_Y_OUT)
#  define GEMV_WRITE_Y_NEXT() (GEMV_REG(GEMV_Y_NEXT) = 1u)
#endif

static uintptr_t s_gemv_base;

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

void gemv_load_x(const int8_t *x, int len)
{
    if (x == NULL) return;
    for (int i = 0; i < len; i++)
        GEMV_WRITE_X(x[i]);
}

void gemv_load_w(const int8_t *w, int out_dim, int len)
{
    if (w == NULL) return;
    for (int i = 0; i < out_dim * len; i++)
        GEMV_WRITE_W(w[i]);
}

void gemv_load_b(const int32_t *b, int out_dim)
{
    if (b == NULL) return;
    for (int i = 0; i < out_dim; i++)
        GEMV_WRITE_B(b[i]);
}

void gemv_start(int len, int out_dim, int enable_bias)
{
    /* Set config bits and start; one write generates start pulse on LiteX wrapper */
    uint32_t ctrl = GEMV_CTRL_START;
    if (len == 64)     ctrl |= GEMV_CTRL_LEN_64;
    if (out_dim == 64) ctrl |= GEMV_CTRL_OUT_DIM_64;
    if (enable_bias)   ctrl |= GEMV_CTRL_ENABLE_BIAS;
    GEMV_WRITE_CTRL(ctrl);
}

void gemv_wait_done(void)
{
    while (1) {
        uint32_t s = GEMV_READ_STATUS();
        if (s & GEMV_STATUS_DONE) break;
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
