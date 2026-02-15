// TinyFormer with DOT8 hardware accelerator only.
// Build with -DUSE_DOT8_HW; link with hw_extensions/dot8/sw/dot8.c as needed.

#include "demo_runner.h"

int main(void)
{
    demo_print_banner("MODE: DOT8\r\n");
    demo_run();

    while (1) {
        /* Idle */
    }
    return 0;
}
