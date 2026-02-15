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
