# ==========================================================================
#  WHAT THIS FILE DOES (in simple words):
#  Build recipe for the firmware: compiler (riscv gcc), flags (-march=rv32im -mabi=ilp32
#  -O2 -ffreestanding -nostdlib), include paths, which .c files to compile per mode,
#  and how to link them into firmware.elf/.bin.
#  BIG PICTURE: Type 'make' here to produce the firmware image loaded onto the board.
# ==========================================================================

TARGET ?= baseline

# MMIO bases for exp_lut / GEMV when not using LiteX CSR accessor names in generated/csr.h.
# After building the SoC, verify in litex-nexys4ddr/build/csr.csv and override if needed:
#   make TARGET=accel_all EXP_LUT_MMIO_BASE=0xf0002xxx GEMV_MMIO_BASE=0xf0003xxx
EXP_LUT_MMIO_BASE ?= 0xf0002800
GEMV_MMIO_BASE ?= 0xf0003000

# Compiler settings
CC = riscv64-unknown-elf-gcc
OBJCOPY = riscv64-unknown-elf-objcopy

# Build flags
CFLAGS = -march=rv32im -mabi=ilp32 -O2 -g -Wall -Werror
CFLAGS += -ffreestanding -nostdlib
CFLAGS += -I. -Icommon -Iinclude -Igenerated

LDFLAGS = -nostdlib -T linker.ld

# Define sources based on target
COMMON_SRCS = $(wildcard common/*.c)
ISR_SRC = isr.c
CRT0 = crt0.S

ifeq ($(TARGET),baseline)
    MAIN_SRC = baseline/main_baseline.c
    CFLAGS += -DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART
else ifeq ($(TARGET),accel_dot8)
    MAIN_SRC = accel_dot8/main_dot8.c
    CFLAGS += -DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART -DUSE_DOT8_HW -I../hw_extensions/dot8/sw
    EXTRA_SRCS += ../hw_extensions/dot8/sw/dot8.c
else ifeq ($(TARGET),accel_lut)
    MAIN_SRC = accel_lut/main_lut.c
    CFLAGS += -DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART -DUSE_EXP_LUT_HW -DEXP_LUT_USE_LITEX_CSR
    CFLAGS += -I../hw_extensions/exp_lut/sw
    EXTRA_SRCS += ../hw_extensions/exp_lut/sw/exp_lut.c
else ifeq ($(TARGET),accel_gemv)
    MAIN_SRC = accel_gemv/main_gemv.c
    CFLAGS += -DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART -DUSE_GEMV_HW -DGEMV_USE_LITEX_CSR
    CFLAGS += -I../hw_extensions/gemv/sw
    EXTRA_SRCS += ../hw_extensions/gemv/sw/gemv.c
else ifeq ($(TARGET),accel_dot8_lut)
    MAIN_SRC = accel_dot8_lut/main_dot8_lut.c
    CFLAGS += -DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART -DUSE_DOT8_HW -DUSE_EXP_LUT_HW -DEXP_LUT_USE_LITEX_CSR
    CFLAGS += -I../hw_extensions/dot8/sw -I../hw_extensions/exp_lut/sw
    EXTRA_SRCS += ../hw_extensions/dot8/sw/dot8.c ../hw_extensions/exp_lut/sw/exp_lut.c
else ifeq ($(TARGET),accel_all)
    MAIN_SRC = accel_all/main_all.c
    CFLAGS += -DUSE_TRAINED_WEIGHTS=1 -DUSE_LITEX_UART -DUSE_DOT8_HW -DUSE_EXP_LUT_HW -DUSE_GEMV_HW
    CFLAGS += -DEXP_LUT_USE_LITEX_CSR -DGEMV_USE_LITEX_CSR
    CFLAGS += -I../hw_extensions/dot8/sw -I../hw_extensions/exp_lut/sw -I../hw_extensions/gemv/sw
    EXTRA_SRCS += ../hw_extensions/dot8/sw/dot8.c ../hw_extensions/exp_lut/sw/exp_lut.c ../hw_extensions/gemv/sw/gemv.c
endif

# Object files. 
# Note: Since source files are in subdirectories, make sure to handle paths correctly.
# The simple patsubst works if the output .o files are alongside the source files.
# Or we can put them in a build directory. Let's keep it simple for now and put alongside.

SRCS = $(CRT0) $(ISR_SRC) $(COMMON_SRCS) $(MAIN_SRC) $(EXTRA_SRCS)
OBJS = $(SRCS:.c=.o)
OBJS := $(OBJS:.S=.o)

all: firmware.elf

firmware.elf: $(OBJS)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^
	$(OBJCOPY) -O binary $@ firmware.bin

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

%.o: %.S
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f firmware.elf firmware.bin $(OBJS)
	rm -f baseline/*.o accel_all/*.o accel_dot8/*.o accel_dot8_lut/*.o accel_gemv/*.o accel_lut/*.o
	rm -f ../hw_extensions/dot8/sw/*.o ../hw_extensions/exp_lut/sw/*.o ../hw_extensions/gemv/sw/*.o

.PHONY: all clean
