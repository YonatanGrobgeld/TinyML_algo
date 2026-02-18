# Simple simulation Makefile for standalone SV testbenches.
#
# Supports:
#   - SIM=iverilog  (default; requires iverilog + vvp)
#   - SIM=xsim      (requires Vivado xsim: xvlog/xelab/xsim)
#
# Outputs:
#   - tb_gemv.vcd
#   - tb_lut.vcd

SIM ?= iverilog

ROOT := ../..
GEMV_RTL := $(ROOT)/hw_extensions/gemv/rtl/gemv_core.v
LUT_RTL  := $(ROOT)/hw_extensions/exp_lut/exp_lut.v

TB_GEMV := tb_gemv.sv
TB_LUT  := tb_lut.sv

.PHONY: all gemv lut clean

all: gemv lut

gemv:
ifeq ($(SIM),xsim)
	xvlog -sv $(TB_GEMV) $(GEMV_RTL)
	xelab -debug typical tb_gemv -s tb_gemv_sim
	xsim tb_gemv_sim -runall
else
	iverilog -g2012 -o tb_gemv.out $(TB_GEMV) $(GEMV_RTL)
	vvp tb_gemv.out
endif

lut:
ifeq ($(SIM),xsim)
	xvlog -sv $(TB_LUT) $(LUT_RTL)
	xelab -debug typical tb_lut -s tb_lut_sim
	xsim tb_lut_sim -runall
else
	iverilog -g2012 -o tb_lut.out $(TB_LUT) $(LUT_RTL)
	vvp tb_lut.out
endif

clean:
	rm -f *.out *.vcd *.wdb *.log xsim.dir/* *.jou *.pb

