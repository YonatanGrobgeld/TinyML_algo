# Exp LUT — LiteX CSR wrapper.
# Index 0..15 (write); value Q10 16-bit (read). Uses .re for strobes where applicable.

from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus


class ExpLUTPeripheral(Module, AutoCSR):
    """Exposes index (write) and value (read). LUT matches tinyformer.c exp_lut[16]."""

    def __init__(self):
        self.index = CSRStorage(4, name="index", description="LUT index 0..15 (write)")
        self.value = CSRStatus(16, name="value", description="Q10 exp value (read)")

        self.index_we = Signal()
        self.index_data = Signal(4)
        self.value_data = Signal(16)

        self.comb += [
            self.index_we.eq(self.index.re),
            self.index_data.eq(self.index.dat_w[:4]),
        ]
        index_5 = Cat(C(0, 1), self.index.storage)

        self.specials += Instance(
            "exp_lut",
            i_clk=ClockSignal(),
            i_reset=ResetSignal(),
            i_index=index_5,
            o_value=self.value_data,
        )
        self.comb += self.value.status.eq(self.value_data)
