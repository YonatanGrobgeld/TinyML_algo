# Vivado 2025.2 xsim script for LUT testbench.

# Compile DUT (exp_lut) first
xvlog -sv hw_extensions/exp_lut/exp_lut.v

# Compile testbench
xvlog -sv hw_extensions/sim/tb_lut.sv

# Elaborate
xelab tb_lut -s tb_lut_sim

# Create batch Tcl for xsim run and VCD dumping
set fp [open xsim_lut_do.tcl "w"]
puts $fp "open_vcd tb_lut.vcd"
puts $fp "log_vcd [get_objects -r tb_lut/*]"
puts $fp "run all"
puts $fp "close_vcd"
puts $fp "quit"
close $fp

# Run simulation with batch script
xsim tb_lut_sim -tclbatch xsim_lut_do.tcl
