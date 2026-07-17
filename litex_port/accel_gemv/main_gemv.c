/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Entry point of the GEMV-only build: compiled with -DUSE_GEMV_HW so all matrix-vector
 *  multiplications run on the GEMV peripheral. Prints 'MODE: GEMV'.
 *  BIG PICTURE: Isolates the matrix-engine contribution (matvec was 21% of baseline).
 * ==========================================================================
 */

// TinyFormer with GEMV hardware only.
// Build with -DUSE_GEMV_HW; link with hw_extensions/gemv/sw/gemv.c as needed.

#include "demo_runner.h"

int main(void)
{
    demo_print_banner("MODE: GEMV\r\n");
    demo_run();

    while (1) {
        /* Idle */
    }
    return 0;
}
