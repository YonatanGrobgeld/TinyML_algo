
<#
.SYNOPSIS
    Runs Vivado simulations for the TinyML accelerator cores.

.DESCRIPTION
    This script compiles and simulates the Verilog/SystemVerilog files using Xilinx Vivado tools 
    (xvlog, xelab, xsim). It reproduces the functionality of the Makefile for Windows PowerShell users.

.PARAMETER Target
    The simulation target to run. Options: "gemv", "lut", "all". Default is "all".

.PARAMETER Clean
    If set, removes simulation artifacts and exits.

.EXAMPLE
    .\simulate.ps1 -Target gemv
    Runs the GEMV simulation.

.EXAMPLE
    .\simulate.ps1 -Clean
    Cleans up generated files.
#>

param (
    [ValidateSet("gemv", "lut", "all")]
    [string]$Target = "all",

    [switch]$Clean
)

$ErrorActionPreference = "Stop"

function Run-Command {
    param([string]$Command)
    Write-Host ">> Executing: $Command" -ForegroundColor Cyan
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Command failed with exit code $LASTEXITCODE"
    }
}

function Clean-Artifacts {
    Write-Host "Cleaning up simulation artifacts..." -ForegroundColor Yellow
    $extensions = @("*.out", "*.vcd", "*.wdb", "*.log", "*.jou", "*.pb", "*.str")
    $dirs = @("xsim.dir")
    
    foreach ($ext in $extensions) {
        Remove-Item $ext -Force -ErrorAction SilentlyContinue
    }
    foreach ($dir in $dirs) {
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Remove-Item "xsim_*.tcl" -Force -ErrorAction SilentlyContinue
    Write-Host "Clean complete." -ForegroundColor Green
}

function Run-Gemv {
    Write-Host "`n=== Running GEMV Simulation ===" -ForegroundColor Magenta
    # Compile
    Run-Command "xvlog -sv tb_gemv.sv gemv_core.v"
    # Elaborate
    Run-Command "xelab -debug typical tb_gemv -s tb_gemv_sim"
    # Simulate
    Run-Command "xsim tb_gemv_sim -runall"
}

function Run-Lut {
    Write-Host "`n=== Running LUT Simulation ===" -ForegroundColor Magenta
    # Compile
    Run-Command "xvlog -sv tb_lut.sv exp_lut.v"
    # Elaborate
    Run-Command "xelab -debug typical tb_lut -s tb_lut_sim"
    # Simulate
    Run-Command "xsim tb_lut_sim -runall"
}

# --- Main Execution ---

if ($Clean) {
    Clean-Artifacts
    exit
}

# Check for Vivado tools
if (-not (Get-Command "xsim" -ErrorAction SilentlyContinue)) {
    Write-Warning "Vivado tools (xsim, xvlog, xelab) not found in PATH."
    Write-Warning "Please run 'settings64.bat' (from your Vivado install dir) or add them to your PATH."
    exit 1
}

if ($Target -eq "gemv" -or $Target -eq "all") {
    Run-Gemv
}

if ($Target -eq "lut" -or $Target -eq "all") {
    Run-Lut
}

Write-Host "`nSimulation sequence finished." -ForegroundColor Green
