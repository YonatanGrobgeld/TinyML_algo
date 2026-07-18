#!/usr/bin/env python3
"""
MOVED — on-FPGA measurement now lives in the litex-nexys4ddr repo.

The real, working measurement scripts (with automatic LiteX SFL firmware
upload over UART) are:

    litex-nexys4ddr/scripts/run_baseline_and_measure.py
    litex-nexys4ddr/scripts/run_accel_all_and_measure.py

End-to-end flow (program bitstream -> upload firmware -> read hardware CYCLES
-> speedup = baseline / accel):

    litex-nexys4ddr/docs/MEASURE_ON_FPGA.md

Why here it's only a stub: measurement drives the LiteX BIOS/board over serial,
so it lives with the SoC/board (litex-nexys4ddr). This file is kept as a
redirect; the previous copy was an older version without SFL auto-upload.
"""
import sys

if __name__ == "__main__":
    print(__doc__)
    sys.exit(1)
