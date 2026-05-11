# Building TinyML Firmware for Litex Nexys4DDR

This directory contains the firmware source code for the TinyFormer model on RISC-V.
The environment has been set up to build within this repository: **`litex_port/generated/`** includes a copy of LiteX `csr.h` (and related headers) so a plain `make` can find `#include <generated/csr.h>`.

## setup (optional)

If your SoC differs from the checked-in CSR map, either refresh `litex_port/generated/` from your LiteX build output, or run:

```bash
./setup_build.sh
```

(point `LITEX_BUILD_INCLUDE` in that script at your build tree).

## Building

You can build the firmware using `make`. The default target is `baseline`.

```bash
make
```

This produces `firmware.elf` and `firmware.bin`.

## Build Targets

The Makefile supports multiple build targets for different hardware configurations:

- `baseline` (Default): Pure software implementation.
- `accel_dot8`: Uses DOT8 custom instruction.
- `accel_lut`: Uses Exponential LUT peripheral.
- `accel_gemv`: Uses GEMV peripheral.
- `accel_dot8_lut`: Uses DOT8 and LUT.
- `accel_all`: Uses all accelerators (DOT8 + LUT + GEMV).

To build a specific target:

```bash
make TARGET=accel_all
```

## Clean

To clean build artifacts:

```bash
make clean
```
