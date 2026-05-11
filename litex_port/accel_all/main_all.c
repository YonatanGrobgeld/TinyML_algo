// TinyFormer with all accelerators: DOT8 + LUT + GEMV.
// Build with -DUSE_DOT8_HW -DUSE_EXP_LUT_HW -DUSE_GEMV_HW; link all drivers.

#include "demo_runner.h"
#include "uart_litex.h"
#include <generated/csr.h>

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
  demo_print_banner("MODE: DOT8 + LUT + GEMV\r\n");

  while (1) {
    uart_write_string("Ready\r\n");
    char c = uart_read_char();
    if (c == 's') {
      uint32_t sys_clk_freq = CONFIG_CLOCK_FREQUENCY;

      timer0_en_write(0);
      timer0_load_write(0xFFFFFFFF);
      timer0_reload_write(0xFFFFFFFF);
      timer0_en_write(1);
      timer0_update_value_write(1);
      uint32_t t_start = timer0_value_read();

      demo_run();

      timer0_update_value_write(1);
      uint32_t t_end = timer0_value_read();
      timer0_en_write(0);

      uint32_t cycles = t_start - t_end;
      uint32_t cycles_per_us = sys_clk_freq / 1000000;
      uint32_t time_us = cycles / cycles_per_us;

      uart_write_string("CYCLES=");
      uart_write_uint32(cycles);
      uart_write_string("\r\n");
      uart_write_string("TIME_US=");
      uart_write_uint32(time_us);
      uart_write_string("\r\n");
      uart_write_string("Done\r\n");
    }
  }

  return 0;
}
