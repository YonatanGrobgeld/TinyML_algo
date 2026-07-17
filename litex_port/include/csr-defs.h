/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Minimal LiteX-style system header: constants for CSR (control/status register) access
 *  used by generated headers. Vendored so the firmware compiles outside a LiteX tree.
 *  BIG PICTURE: Plumbing so #include <generated/csr.h> works.
 * ==========================================================================
 */

#ifndef CSR_DEFS__H
#define CSR_DEFS__H

#define CSR_MSTATUS_MIE 0x8

#define CSR_IRQ_MASK 0xBC0
#define CSR_IRQ_PENDING 0xFC0

#define CSR_DCACHE_INFO 0xCC0

#endif	/* CSR_DEFS__H */
