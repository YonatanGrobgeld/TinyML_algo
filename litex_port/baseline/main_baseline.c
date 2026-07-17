/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Entry point of the BASELINE build (NO accelerators - pure software, the 759 ms mode).
 *  Prints 'MODE: BASELINE', then waits for the letter 's' on the serial port; on each 's'
 *  it runs the 10-sample demo while timing it with the on-chip timer0 (a hardware
 *  stopwatch), then prints CYCLES= and TIME_US=. This is the reference all speedups
 *  are measured against. Built WITHOUT any USE_*_HW macros.
 *  BIG PICTURE: One of 6 tiny mode mains; all share the same demo_runner/tinyformer code.
 * ==========================================================================
 */

// Baseline TinyFormer: no hardware accelerators (plain VexRiscv).
// Same demo flow as all other modes; UART banner identifies this build.
// Build with no USE_DOT8_HW, USE_EXP_LUT_HW, or USE_GEMV_HW.

#include "demo_runner.h"
#include "uart_litex.h"
#include <generated/csr.h>

// Helper to print uint32_t as decimal
static void uart_write_uint32(uint32_t value) {
  char buf[11];
  int i = 10;
  buf[i--] = '\0';
  if (value == 0) {
    buf[i] = '0';
    uart_write_string(&buf[i]);
    return;
  }
  while (value > 0 && i >= 0) {
    buf[i--] = (char)('0' + (value % 10u));
    value /= 10u;
  }
  uart_write_string(&buf[i + 1]);
}

int main(void) {
  demo_print_banner("MODE: BASELINE\r\n");

  // Loop forever to allow multiple runs without reset
  while (1) {
    // Wait for start command
    uart_write_string("Ready\r\n");
    char c = uart_read_char();
    if (c == 's') {
      // Measure runtime using LiteX TIMER0
      // TIMER0 counts down from load value at system clock rate
      uint32_t sys_clk_freq = CONFIG_CLOCK_FREQUENCY; // From generated/soc.h

      // Set timer to maximum value for countdown
      /* SIMPLE WORDS - the stopwatch: load the hardware timer with the max
       * value, let it count DOWN at 100 MHz, read it before and after the
       * demo; the difference = exact clock cycles used. Trusted over PC
       * wall-clock because the serial link can drop bytes. */
      timer0_en_write(0);
      timer0_load_write(0xFFFFFFFF);
      timer0_reload_write(0xFFFFFFFF);
      timer0_en_write(1);
      timer0_update_value_write(1);
      uint32_t t_start = timer0_value_read();

      // Run the baseline algorithm
      demo_run();

      // Read end time
      timer0_update_value_write(1);
      uint32_t t_end = timer0_value_read();
      timer0_en_write(0);

      // Calculate elapsed cycles (timer counts DOWN)
      uint32_t cycles = t_start - t_end;

      // Convert to microseconds (avoid 64-bit division)
      // At 100MHz: cycles_per_us = 100, so time_us = cycles / 100
      uint32_t cycles_per_us = sys_clk_freq / 1000000;
      uint32_t time_us = cycles / cycles_per_us;

      // Print timing info
      uart_write_string("CYCLES=");
      uart_write_uint32(cycles);
      uart_write_string("\r\n");

      uart_write_string("TIME_US=");
      uart_write_uint32(time_us);
      uart_write_string("\r\n");

      uart_write_string("Done\r\n");
    }
  }

  while (1) {
    /* Idle */
  }
  return 0;
}
