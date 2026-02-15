// TinyFormer with all accelerators: DOT8 + LUT + GEMV.
// Build with -DUSE_DOT8_HW -DUSE_EXP_LUT_HW -DUSE_GEMV_HW; link all drivers.

#include "demo_runner.h"

int main(void)
{
    demo_print_banner("MODE: DOT8 + LUT + GEMV\r\n");
    demo_run();

    while (1) {
        /* Idle */
    }
    return 0;
}
