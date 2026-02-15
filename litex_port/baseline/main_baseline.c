// Baseline TinyFormer: no hardware accelerators (plain VexRiscv).
// Same demo flow as all other modes; UART banner identifies this build.
// Build with no USE_DOT8_HW, USE_EXP_LUT_HW, or USE_GEMV_HW.

#include "demo_runner.h"

int main(void)
{
    demo_print_banner("MODE: BASELINE\r\n");
    demo_run();

    while (1) {
        /* Idle */
    }
    return 0;
}
