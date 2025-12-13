# ===============================
# dc_tiny.tcl
# Run from project root
# ===============================

# ---------- User config ----------
set DESIGN_NAME gpu

set REPORT_DIR ./reports_tiny
set WORK_DIR   ./work_tiny

# ---------- Technology library ----------
set TARGET_LIB "./stdcells.db"
set LINK_LIB   "* $TARGET_LIB"

# ---------- Setup ----------
file mkdir $REPORT_DIR
file mkdir $WORK_DIR

define_design_lib WORK -path $WORK_DIR

set_app_var target_library $TARGET_LIB
set_app_var link_library   $LINK_LIB
set_app_var search_path    [list . ./tiny]

set hdlin_sv_enable_vpp true
set verilogout_no_tri true

# ---------- Read RTL ----------
puts "INFO: Reading RTL files:"
puts "  tiny/gpu.v"
puts "  tiny/alu.v"

read_file -format sverilog {tiny/gpu.v tiny/alu.v}

# ---------- Elaborate ----------
elaborate $DESIGN_NAME
current_design $DESIGN_NAME
link

# ---------- Constraints ----------
create_clock -name clk -period 1.0 [get_ports clk]
set_clock_uncertainty 0.1 [get_clocks clk]

set_input_delay  0.1 -clock clk [all_inputs]
set_output_delay 0.1 -clock clk [all_outputs]

set_max_transition 0.15 [current_design]
set_max_fanout 10 [current_design]

# ---------- Compile ----------
compile_ultra

# ---------- Reports ----------
report_area   > $REPORT_DIR/area.rpt
report_power  > $REPORT_DIR/power.rpt
report_timing > $REPORT_DIR/timing.rpt

# ---------- Save ----------
write -format ddc -hierarchy -output $REPORT_DIR/${DESIGN_NAME}.ddc

quit
