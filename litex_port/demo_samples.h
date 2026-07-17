/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  NOTE: this is the OLDER flat-layout copy; the canonical version used by the documented builds lives in litex_port/common/.
 *  Header for the older demo-samples copy.
 *  BIG PICTURE: See common/demo_samples.h.
 * ==========================================================================
 */

#ifndef DEMO_SAMPLES_H
#define DEMO_SAMPLES_H

#include <stdint.h>

#define DEMO_NUM_SAMPLES 10
#define DEMO_S 16
#define DEMO_D 32

extern const int8_t  demo_inputs[DEMO_NUM_SAMPLES][DEMO_S][DEMO_D];
extern const uint8_t demo_labels[DEMO_NUM_SAMPLES];

#endif // DEMO_SAMPLES_H
