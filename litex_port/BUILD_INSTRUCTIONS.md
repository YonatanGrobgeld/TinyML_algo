# Building TinyML Firmware for Litex Nexys4DDR

This directory contains the firmware source code for the TinyFormer model on RISC-V.
The environment has been set up to build completely within this repository, using artifacts integrated from the Litex project.

## setup

If you haven't already, run the setup script to copy necessary headers and startup code:

```bash
./setup_build.sh
```

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
