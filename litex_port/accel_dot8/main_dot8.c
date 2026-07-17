/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Entry point of the DOT8-only build: same shared demo, but compiled with -DUSE_DOT8_HW
 *  so all inner dot-products use the custom 4-lane CPU instruction. Prints 'MODE: DOT8'.
 *  BIG PICTURE: Lets you measure the DOT8 instruction's contribution in isolation.
 * ==========================================================================
 */

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
