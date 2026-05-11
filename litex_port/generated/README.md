# LiteX-generated headers (checked in)

These files are copied from a **Digilent Nexys4 DDR + VexRiscv** LiteX software build so that `make` in `litex_port/` can resolve `#include <generated/csr.h>` without running `./setup_build.sh` first.

- **Source of truth:** your LiteX project’s `build/software/include/generated/` after `build_soc.py` (or equivalent).
- **UART / timer / SDRAM CSRs** in `csr.h` match the checked-in Nexys4DDR gateware build used when these files were refreshed.
- **Accelerator MMIO:** `exp_lut` and `gemv` drivers default to raw MMIO bases in the `Makefile` (`EXP_LUT_MMIO_BASE`, `GEMV_MMIO_BASE`). After you add peripherals to the SoC, confirm bases in `build/csr.csv` and override on the command line if they differ.

To refresh from your machine:

```bash
cp /path/to/litex/build/software/include/generated/{csr.h,soc.h,mem.h,git.h,sdram_phy.h,output_format.ld,regions.ld} litex_port/generated/
```
