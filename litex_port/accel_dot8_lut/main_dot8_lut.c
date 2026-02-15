// TinyFormer with DOT8 + Exp LUT hardware.
// Build with -DUSE_DOT8_HW -DUSE_EXP_LUT_HW; link corresponding drivers.

#include "demo_runner.h"

int main(void)
{
    demo_print_banner("MODE: DOT8 + LUT\r\n");
    demo_run();

    while (1) {
        /* Idle */
    }
    return 0;
}
