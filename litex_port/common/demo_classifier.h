/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Header declaring the classifier weights (cls_W[6][32], cls_b[6]) and the
 *  number of classes.
 *  BIG PICTURE: Included by the demo runner.
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
