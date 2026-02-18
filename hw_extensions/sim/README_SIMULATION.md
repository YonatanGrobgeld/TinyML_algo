
# Vivado Simulation Instructions

These steps explain how to run the verification simulations using Xilinx Vivado's simulator (`xsim`) in batch mode.

## Prerequisites
- **Vivado** must be installed and in your `PATH`.
- Typically, you need to source the settings file before running these commands:
  ```bash
  source /tools/Xilinx/Vivado/202x.x/settings64.sh
  ```

## Running Simulations (Batch Mode)

We use the provided `Makefile` to automate the process.

### 1. Matrix-Vector Multiplication (GEMV)
Run the following command to compile and simulate the GEMV core:

```bash
make gemv SIM=xsim
```

**What this does:**
1. `xvlog -sv ...`: Compiles the Verilog/SystemVerilog sources.
2. `xelab ...`: Elaborates the design and creates a simulation snapshot (`tb_gemv_sim`).
3. `xsim ... -runall`: Runs the simulation in CLI (batch) mode until `$finish`.

### 2. Lookup Table (LUT/Softmax)
Run the following command to compile and simulate the LUT core:

```bash
make lut SIM=xsim
```

### 3. Cleaning Up
To remove generated logs, waveforms, and temporary directories:

```bash
make clean
```

## Viewing Waveforms (Optional)
If you want to view the waveforms later:
1. The simulation generates a `.vcd` file (e.g., `tb_gemv.vcd`).
2. You can open this with valid waveform viewers or convert it to WDB for Vivado.
   *Note: The current Makefile produces VCDs for compatibility. To produce WDBs for Vivado GUI, you'd typically run `xsim` with `-gui` or inspect the default `xsim.wdb` if generated.*

## Running on Windows (PowerShell)

If you are using Windows PowerShell and cannot use `make`, use the provided `simulate.ps1` script.

### Usage
1. Open PowerShell in this directory.
2. Ensure Vivado tools are in your PATH (or run `settings64.bat` first).

**Run GEMV Simulation:**
```powershell
.\simulate.ps1 -Target gemv
```

**Run LUT Simulation:**
```powershell
.\simulate.ps1 -Target lut
```

**Clean Artifacts:**
```powershell
.\simulate.ps1 -Clean
```

### Troubleshooting: "Script cannot be loaded"
If you see a security error about disabled scripts, run one of the following:

**Option A (Run just this time):**
```powershell
powershell -ExecutionPolicy Bypass -File .\simulate.ps1 -Target gemv
```

**Option B (Allow scripts for your user):**
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Then try running `.\simulate.ps1` again.
