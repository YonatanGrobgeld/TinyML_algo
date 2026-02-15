# Windows Development Instructions for TinyML Firmware

This guide explains how to continue development and run the TinyML firmware on Windows.

## 1. Required Files

You need the entire `litex_port` directory from this repository.
Ensure the following generated files (which were created during setup) are present:

- `litex_port/Makefile`
- `litex_port/linker.ld`
- `litex_port/crt0.S`
- `litex_port/isr.c`
- `litex_port/generated/` (Directory containing `csr.h`, `soc.h`, etc.)
- `litex_port/include/` (Directory containing `system.h`, `hw/common.h`, etc.)
- `litex_port/common/` (Source files)
- `litex_port/baseline/` (Source files)

If you cloned the repository and these files are missing (because they were ignored or not committed), copy them from your Linux setup.

## 2. Install Toolchain (RISC-V GCC)

You need a RISC-V compiler for Windows.

**Option A: xPack RISC-V Embedded GCC (Recommended)**
1.  Download the latest release `.zip` from [xPack RISC-V GCC Releases](https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases).
2.  Extract it to a simple path (e.g., `C:\riscv-gcc`).
3.  Add the `bin` folder (e.g., `C:\riscv-gcc\bin`) to your Windows **PATH** environment variable.
4.  Verify installation in Command Prompt/PowerShell:
    ```cmd
    riscv-none-elf-gcc --version
    ```
    *Note: The Makefile uses `riscv64-unknown-elf-gcc`. If your toolchain uses `riscv-none-elf-`, you may need to edit the `CC` and `OBJCOPY` variables in `litex_port/Makefile`.*

## 3. Install Build Tools (Make)

**Option A: Chocolatey**
1.  Install Chocolatey if needed.
2.  Run: `choco install make`

**Option B: MSYS2 / Git Bash**
1.  If you have Git Bash, you might already have `make` or can assume a Unix-like environment.
2.  Otherwise, install [Make for Windows](http://gnuwin32.sourceforge.net/packages/make.htm).

## 4. Install Litex Term (Python)

To verify the firmware on the FPGA, you need `litex_term`.

1.  Install [Python](https://www.python.org/downloads/).
2.  Install Litex:
    ```cmd
    pip install litex
    ```
    (This usually provides `litex_term`).

## 5. Building the Firmware

1.  Open Command Prompt or PowerShell.
2.  Navigate to the `litex_port` directory.
3.  Run `make`:
    ```cmd
    make
    ```
    *If your GCC is named differently (e.g. `riscv-none-elf-gcc`), run:*
    ```cmd
    make CC=riscv-none-elf-gcc OBJCOPY=riscv-none-elf-objcopy
    ```

This will produce `firmware.elf` and `firmware.bin`.

## 6. Running on Hardware

1.  Connect your Nexys4DDR board.
2.  Identify the COM port (e.g., `COM4`).
3.  Run `litex_term`:
    ```cmd
    litex_term --kernel firmware.bin COM4
    ```

## 7. Troubleshooting

- **Missing headers:** Ensure `generated/` and `include/` directories were copied correctly.
- **`make` not found:** Ensure Make is in your PATH.
- **Compiler errors:** Check if the compiler version supports the `-march=rv32im` flag (most standard RISC-V toolchains do).
