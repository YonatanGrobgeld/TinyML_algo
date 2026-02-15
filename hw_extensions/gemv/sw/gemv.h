/*
 * GEMV accelerator — C driver API (skeleton).
 *
 * Defining USE_GEMV_HW (in the firmware that uses this driver) requires the SoC to include
 * the corresponding HW block; otherwise keep the macro off and do not call GEMV MMIO.
 *
 * Use with LiteX-generated CSR accessors when integrated (e.g. gemv_ctrl_read(),
 * gemv_x_in_write(), etc.), or with a base address and the macros below.
 *
 * Polling only; no interrupts.
 */

#ifndef GEMV_H
#define GEMV_H

#include <stdint.h>

/* Optional: set base address when not using LiteX generated/csr.h */
#ifndef GEMV_BASE
/* #define GEMV_BASE  0x00000000 */
#endif

/* Register offsets (bytes) — must match gemv_spec.md and LiteX wrapper */
#define GEMV_CTRL    0x00
#define GEMV_X_IN    0x04
#define GEMV_W_IN    0x08
#define GEMV_B_IN    0x0C
#define GEMV_Y_OUT   0x10
#define GEMV_STATUS  0x14
#define GEMV_Y_NEXT  0x18   /* write any value to advance Y read pointer (pulse) */

/* CTRL bits: START and CLEAR_DONE are pulses (one write triggers a one-cycle pulse in hardware).
 * busy/done are read from STATUS, not CTRL. */
#define GEMV_CTRL_START       (1u << 0)
/* #define GEMV_CTRL_BUSY    (1u << 1)  — use GEMV_STATUS_BUSY */
/* #define GEMV_CTRL_DONE    (1u << 2)  — use GEMV_STATUS_DONE */
#define GEMV_CTRL_CLEAR_DONE  (1u << 3)
#define GEMV_CTRL_LEN_64      (1u << 4)
#define GEMV_CTRL_OUT_DIM_64  (1u << 5)
#define GEMV_CTRL_ENABLE_BIAS (1u << 6)

/* STATUS register: [0]=busy, [1]=done (only source for status bits) */
#define GEMV_STATUS_DONE      (1u << 1)
#define GEMV_STATUS_BUSY      (1u << 0)

/* Dimensions: 0 = 32, 1 = 64 */
#define GEMV_LEN_32      0
#define GEMV_LEN_64     1
#define GEMV_OUT_DIM_32 0
#define GEMV_OUT_DIM_64 1

#ifdef __cplusplus
extern "C" {
#endif

/* Initialize driver (set base address if using GEMV_BASE). No-op when using LiteX CSRs. */
void gemv_init(uintptr_t base_addr);

/* Load vector X (int8), len = 32 or 64. */
void gemv_load_x(const int8_t *x, int len);

/* Load matrix W (int8, row-major), out_dim rows × len cols. */
void gemv_load_w(const int8_t *w, int out_dim, int len);

/* Optional: load bias (int32), out_dim elements. Call only if enable_bias will be 1. */
void gemv_load_b(const int32_t *b, int out_dim);

/* Start GEMV: len and out_dim must be 32 or 64; enable_bias 0 or 1. */
void gemv_start(int len, int out_dim, int enable_bias);

/* Block until done. */
void gemv_wait_done(void);

/* Read result Y (int32) into buffer; out_dim = 32 or 64. */
void gemv_read_y(int32_t *y, int out_dim);

/* Clear done flag and reset Y read pointer (call before next run). */
void gemv_clear_done(void);

#ifdef __cplusplus
}
#endif

#endif /* GEMV_H */
