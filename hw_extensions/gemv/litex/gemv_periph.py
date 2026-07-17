#!/usr/bin/env python3
# ==========================================================================
#  WHAT THIS FILE DOES (in simple words):
#  The GLUE that puts gemv_core.v on the SoC bus: creates the 7 registers the CPU sees
#  (CTRL, X_IN, W_IN, B_IN, Y_OUT, STATUS, Y_NEXT), turns CTRL writes with the start/
#  clear_done bits into exact one-cycle pulses, and wires each register to the matching
#  port of the Verilog core. LiteX auto-generates the C accessor functions from this.
#  BIG PICTURE: Defines the register map that gemv.c (the driver) talks to.
# ==========================================================================

import os
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from migen import *

_RTL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "..", "..", "hw", "rtl", "gemv_core.v")


class GEMVPeriph(Module, AutoCSR):
    """GEMV (Y = W*X + b) peripheral backed by gemv_core.v.

    CSR register names match the GEMV_USE_LITEX_CSR driver macros in gemv.c:
      ctrl   → gemv_ctrl_write/read      (CTRL bits: [0]=START [3]=CLEAR_DONE
                                           [4]=LEN_64 [5]=OUT_DIM_64 [6]=BIAS_EN)
      x_in   → gemv_x_in_write           (32-bit: 4 packed int8 lanes per write)
      w_in   → gemv_w_in_write           (32-bit: 4 packed int8 lanes per write)
      b_in   → gemv_b_in_write           (int32, one per output dimension)
      y_out  → gemv_y_out_read           (int32 result, pointer advanced by y_next)
      status → gemv_status_read          ([0]=busy [1]=done)
      y_next → gemv_y_next_write         (write any value → advance Y read pointer)

    V2 optimisations (vs v1):
      - x_in and w_in are now 32-bit (was 8-bit), accept 4 packed lanes per write.
        Cuts CPU↔GEMV MMIO traffic by 4x for X and W loading.
      - gemv_core.v internally does a 4-lane MAC per cycle (was 1 lane).
        Cuts compute time by 4x.
    """

    def __init__(self, platform=None, sys_clk_freq=None):
        if platform is not None:
            platform.add_source(_RTL_FILE)

        # --- CSR registers ---
        self.ctrl   = CSRStorage(8,  name="ctrl")
        self.x_in   = CSRStorage(32, name="x_in")
        self.w_in   = CSRStorage(32, name="w_in")
        self.b_in   = CSRStorage(32, name="b_in")
        self.y_out  = CSRStatus(32,  name="y_out")
        self.status = CSRStatus(8,   name="status")
        self.y_next = CSRStorage(8,  name="y_next")

        # --- Internal signals wired to gemv_core ports ---
        busy      = Signal()
        done      = Signal()
        y_rd_data = Signal(32)

        # Pulse signals: go high for exactly one clock cycle on CSR write
        start      = Signal()
        clear_done = Signal()

        self.comb += [
            # START and CLEAR_DONE are one-cycle pulses triggered by ctrl write
            start.eq(self.ctrl.re & self.ctrl.storage[0]),
            clear_done.eq(self.ctrl.re & self.ctrl.storage[3]),
            # Status readback
            self.status.status[0].eq(busy),
            self.status.status[1].eq(done),
            # Y result readback
            self.y_out.status.eq(y_rd_data),
        ]

        self.specials += Instance("gemv_core",
            p_MAX_LEN=64,
            p_MAX_OUT=64,
            p_W_ADDR_BITS=10,    # 1024 words (64*64/4) for the new packed memory
            i_clk=ClockSignal(),
            i_reset=ResetSignal(),
            # Streaming write ports — write-enable is the CSR write-strobe (.re)
            i_x_wr_en=self.x_in.re,
            i_x_wr_data=self.x_in.storage,
            i_w_wr_en=self.w_in.re,
            i_w_wr_data=self.w_in.storage,
            i_b_wr_en=self.b_in.re,
            i_b_wr_data=self.b_in.storage,
            # Control (config bits latched in ctrl.storage; pulses from .re)
            i_start=start,
            i_len_64=self.ctrl.storage[4],
            i_out_dim_64=self.ctrl.storage[5],
            i_bias_en=self.ctrl.storage[6],
            # Status outputs
            o_busy=busy,
            o_done=done,
            i_clear_done=clear_done,
            # Y read: writing y_next advances the internal read pointer
            i_y_rd_en=self.y_next.re,
            o_y_rd_data=y_rd_data,
        )
