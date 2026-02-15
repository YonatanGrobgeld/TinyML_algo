# GEMV peripheral — LiteX CSR wrapper.
#
# Integrates gemv_core (Verilog) into a LiteX SoC via the CSR bus.
# START and CLEAR_DONE are one-cycle pulses (derived from CTRL write + dat_w bits).
# Y read pointer is advanced by writing to Y_NEXT (pulse), not by Y_OUT read-enable.
#
# Usage (in your SoC target):
#   self.submodules.gemv = GEMVPeripheral()
#   self.add_csr("gemv")
#   self.add_source("path/to/rtl/gemv_core.v")

from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus


class GEMVPeripheral(Module, AutoCSR):
    """LiteX peripheral for GEMV core. CTRL, X_IN, W_IN, B_IN, Y_OUT, Y_NEXT, STATUS."""

    def __init__(self):
        # --- CTRL: [0]=start (pulse on write with bit0), [3]=clear_done (pulse on write with bit3),
        #           [4]=len_64, [5]=out_dim_64, [6]=enable_bias (stored config)
        self.ctrl = CSRStorage(7, name="ctrl")
        self.status = CSRStatus(2, name="status")  # [0]=busy, [1]=done — combinational from core

        # --- Stream registers ---
        self.x_in = CSRStorage(8, name="x_in", description="Write next int8 X value")
        self.w_in = CSRStorage(8, name="w_in", description="Write next int8 W value (row-major)")
        self.b_in = CSRStorage(32, name="b_in", description="Write next int32 bias value (optional)")

        # --- Y: read Y_OUT returns current y_rd_data; write Y_NEXT pulses y_rd_en to advance ---
        self.y_out = CSRStatus(32, name="y_out", description="Read int32 Y at current index")
        self.y_next = CSRStorage(1, name="y_next", description="Write any value to advance Y read pointer (pulse)")

        # --- Core signals ---
        self.x_wr_en   = Signal()
        self.x_wr_data = Signal(8)
        self.w_wr_en   = Signal()
        self.w_wr_data = Signal(8)
        self.b_wr_en   = Signal()
        self.b_wr_data = Signal(32)
        self.start     = Signal()
        self.len_64    = Signal()
        self.out_dim_64 = Signal()
        self.bias_en   = Signal()
        self.clear_done = Signal()
        self.busy      = Signal()
        self.done      = Signal()
        self.y_rd_en   = Signal()
        self.y_rd_data = Signal(32)

        # --- Stream writes: .re strobe (portable/idiomatic) and .dat_w ---
        self.comb += [
            self.x_wr_en.eq(self.x_in.re),
            self.x_wr_data.eq(self.x_in.dat_w[:8]),
            self.w_wr_en.eq(self.w_in.re),
            self.w_wr_data.eq(self.w_in.dat_w[:8]),
            self.b_wr_en.eq(self.b_in.re),
            self.b_wr_data.eq(self.b_in.dat_w),
        ]
        # --- START and CLEAR_DONE: one-cycle pulses when CTRL is written with corresponding bit set ---
        self.comb += [
            self.start.eq(self.ctrl.re & self.ctrl.dat_w[0]),
            self.clear_done.eq(self.ctrl.re & self.ctrl.dat_w[3]),
        ]
        # --- Config: stored levels (from ctrl.storage, updated on write) ---
        self.comb += [
            self.len_64.eq(self.ctrl.storage[4]),
            self.out_dim_64.eq(self.ctrl.storage[5]),
            self.bias_en.eq(self.ctrl.storage[6]),
        ]
        # --- STATUS: combinational from core (no sync) ---
        self.comb += [
            self.status.status.eq(Cat(self.busy, self.done)),
        ]
        # --- Y: y_out returns y_rd_data; y_rd_en = pulse when Y_NEXT is written (optionally gated by dat_w[0]) ---
        self.comb += [
            self.y_out.status.eq(self.y_rd_data),
            self.y_rd_en.eq(self.y_next.re & self.y_next.dat_w[0]),
        ]

        # --- Instantiate Verilog GEMV core ---
        self.specials += Instance(
            "gemv_core",
            # Parameters if needed
            # p_MAX_LEN=64, p_MAX_OUT=64, p_W_ADDR_BITS=12,
            i_clk=ClockSignal(),
            i_reset=ResetSignal(),
            i_x_wr_en=self.x_wr_en,
            i_x_wr_data=self.x_wr_data,
            i_w_wr_en=self.w_wr_en,
            i_w_wr_data=self.w_wr_data,
            i_b_wr_en=self.b_wr_en,
            i_b_wr_data=self.b_wr_data,
            i_start=self.start,
            i_len_64=self.len_64,
            i_out_dim_64=self.out_dim_64,
            i_bias_en=self.bias_en,
            o_busy=self.busy,
            o_done=self.done,
            i_clear_done=self.clear_done,
            i_y_rd_en=self.y_rd_en,
            o_y_rd_data=self.y_rd_data,
        )

