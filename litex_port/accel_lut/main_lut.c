// TinyFormer with Exp LUT hardware only.
// Build with -DUSE_EXP_LUT_HW; link with hw_extensions/exp_lut/sw as needed.

#include "demo_runner.h"

int main(void)
{
    demo_print_banner("MODE: LUT\r\n");
    demo_run();

    while (1) {
        /* Idle */
    }
    return 0;
}
