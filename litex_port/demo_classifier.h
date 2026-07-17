/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  NOTE: this is the OLDER flat-layout copy; the canonical version used by the documented builds lives in litex_port/common/.
 *  Header for the older classifier copy.
 *  BIG PICTURE: See common/demo_classifier.h.
 * ==========================================================================
 */

#ifndef DEMO_CLASSIFIER_H
#define DEMO_CLASSIFIER_H

#include <stdint.h>

#define DEMO_NUM_CLASSES 6
#define DEMO_D 32

extern const int8_t cls_W[DEMO_NUM_CLASSES][DEMO_D];
extern const int8_t cls_b[DEMO_NUM_CLASSES];

#endif // DEMO_CLASSIFIER_H
