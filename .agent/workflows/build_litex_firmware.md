---
description: Build the Litex firmware for Nexys4DDR
---
1. Navigate to the litex_port directory
   cd litex_port

2. Run the setup script to prepare the environment (only needed once)
   ./setup_build.sh

3. Clean previous builds
   make clean

4. Build the firmware (default: baseline)
   // turbo
   make

   # To build with accelerators:
   # make TARGET=accel_all
