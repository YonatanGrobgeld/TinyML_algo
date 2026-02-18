# Vivado 2025.2 xsim script for GEMV core testbench.

# Compile DUT (gemv_core) first
xvlog -sv hw_extensions/gemv/rtl/gemv_core.v

# Compile testbench
xvlog -sv hw_extensions/sim/tb_gemv.sv

# Elaborate
xelab tb_gemv -s tb_gemv_sim

# Create batch Tcl for xsim run and VCD dumping
set fp [open xsim_gemv_do.tcl "w"]
puts $fp "open_vcd tb_gemv.vcd"
puts $fp "log_vcd [get_objects -r tb_gemv/*]"
puts $fp "run all"
puts $fp "close_vcd"
puts $fp "quit"
close $fp

# Run simulation with batch script
xsim tb_gemv_sim -tclbatch xsim_gemv_do.tcl
