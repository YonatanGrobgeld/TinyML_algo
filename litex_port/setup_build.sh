#!/bin/bash
set -e

# Define source paths
LITEX_PROJECT_ROOT="/home/yonatang/litex-project"
LITEX_BUILD_INCLUDE="$LITEX_PROJECT_ROOT/build/software/include"
LITEX_SOC_INCLUDE="$LITEX_PROJECT_ROOT/third_party/litex/litex/litex/soc/software/include"
VEXRISCV_DIR="$LITEX_PROJECT_ROOT/third_party/litex/litex/litex/soc/cores/cpu/vexriscv"

# Create local directories
mkdir -p generated
mkdir -p include/hw

# Copy generated headers and linker scripts
echo "Copying generated files from $LITEX_BUILD_INCLUDE/generated..."
cp "$LITEX_BUILD_INCLUDE/generated/"* generated/

# Copy generic headers
echo "Copying generic headers..."
cp "$LITEX_SOC_INCLUDE/irq.h" include/
cp "$LITEX_SOC_INCLUDE/hw/common.h" include/hw/

# Copy CPU-specific headers (replacing generic system.h wrapper)
echo "Copying CPU headers..."
cp "$VEXRISCV_DIR/system.h" include/
cp "$VEXRISCV_DIR/csr-defs.h" include/

# Copy startup code
echo "Copying crt0.S..."
cp "$VEXRISCV_DIR/crt0.S" .

echo "Setup complete. You can now build the firmware using 'make'."
