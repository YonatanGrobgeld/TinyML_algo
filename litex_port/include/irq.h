/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Minimal LiteX-style interrupt helper header (enable/disable/mask). Barely used -
 *  this firmware polls instead of using interrupts.
 *  BIG PICTURE: Plumbing for completeness.
 * ==========================================================================
 */

#pragma once
#include_next<irq.h>

typedef void (*isr_t)(void);

#ifdef __cplusplus
extern "C" {
#endif

extern int irq_attach(unsigned int irq, isr_t isr) __attribute__((weak));
extern int irq_detach(unsigned int irq) __attribute__((weak));

#ifdef __cplusplus
}
#endif
