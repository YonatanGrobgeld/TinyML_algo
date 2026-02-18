// Shared demo flow implementation.
// Uses tinyformer_encode(), demo samples, classifier; prints via uart_litex.

#include "demo_classifier.h"
#include "demo_samples.h"
#include "tinyformer.h"
#include "uart_litex.h"
#include <stdint.h>


#include "uart_litex.h"

void demo_print_banner(const char *line) {
  while (line && *line != '\0') {
    uart_write_char(*line++);
  }
}

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

/* Print 32-bit value as 8 hex digits (for ENC_CKSUM). */
static void uart_write_hex32(uint32_t value) {
  static const char hex[] = "0123456789ABCDEF";
  for (int shift = 28; shift >= 0; shift -= 4) {
    uart_write_char(hex[(value >> shift) & 0xFu]);
  }
}

static int8_t saturate_int32_to_int8(int32_t x) {
  if (x > 127)
    return 127;
  if (x < -128)
    return -128;
  return (int8_t)x;
}

static void mean_pool_tokens(const int8_t tokens[TINYFORMER_S][TINYFORMER_D],
                             int8_t pooled[TINYFORMER_D]) {
  for (int d = 0; d < TINYFORMER_D; ++d) {
    int32_t acc = 0;
    for (int s = 0; s < TINYFORMER_S; ++s) {
      acc += (int32_t)tokens[s][d];
    }
    acc = (acc + (TINYFORMER_S / 2)) / TINYFORMER_S;
    pooled[d] = saturate_int32_to_int8(acc);
  }
}

static void classifier_forward(const int8_t pooled[TINYFORMER_D],
                               int32_t logits[DEMO_NUM_CLASSES]) {
  for (int c = 0; c < DEMO_NUM_CLASSES; ++c) {
    int32_t acc = (int32_t)cls_b[c];
    const int8_t *w_row = &cls_W[c][0];
    for (int d = 0; d < TINYFORMER_D; ++d) {
      acc += (int32_t)w_row[d] * (int32_t)pooled[d];
    }
    logits[c] = acc;
  }
}

void demo_run(void) {
  for (uint32_t i = 0; i < (uint32_t)DEMO_NUM_SAMPLES; ++i) {
    static int8_t encoded[TINYFORMER_S][TINYFORMER_D];
    static int8_t pooled[TINYFORMER_D];
    int32_t logits[DEMO_NUM_CLASSES];

    tinyformer_encode(demo_inputs[i], encoded);

    /* Shared correctness checksum: must match baseline and all accelerated
     * modes. */
    {
      uint32_t cksum = 0;
      for (int s = 0; s < TINYFORMER_S; ++s) {
        for (int d = 0; d < TINYFORMER_D; ++d) {
          cksum += (uint32_t)(uint8_t)encoded[s][d];
        }
      }
      uart_write_string("ENC_CKSUM=0x");
      uart_write_hex32(cksum);
      uart_write_string("\r\n");
    }

    mean_pool_tokens(encoded, pooled);
    classifier_forward(pooled, logits);

    int32_t best_val = logits[0];
    uint32_t best_idx = 0;
    for (uint32_t c = 1; c < (uint32_t)DEMO_NUM_CLASSES; ++c) {
      if (logits[c] > best_val) {
        best_val = logits[c];
        best_idx = c;
      }
    }

    uart_write_string("Sample ");
    uart_write_uint32(i);
    uart_write_string(": pred=");
    uart_write_uint32(best_idx);
    uart_write_string(" exp=");
    uart_write_uint32((uint32_t)demo_labels[i]);
    uart_write_string("\r\n");
  }
}
