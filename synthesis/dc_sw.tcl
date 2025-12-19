# ===============================
# dc_gact.tcl
# Optimized for hierarchical SV
# ===============================

# ---------- User config ----------
set DESIGN_NAME SmithWatermanArray
set REPORT_DIR ./reports_gact
set WORK_DIR   ./work_gact

# ---------- Technology library ----------
set TARGET_LIB "./stdcells.db"
set LINK_LIB   "* $TARGET_LIB"

# ---------- Setup ----------
file mkdir $REPORT_DIR
file mkdir $WORK_DIR

# Define the WORK library explicitly
define_design_lib WORK -path $WORK_DIR

set_app_var target_library $TARGET_LIB
set_app_var link_library   $LINK_LIB
set_app_var search_path    [list . ./gact]

set hdlin_sv_enable_vpp true
set verilogout_no_tri true

# ---------- Read RTL (The Fix) ----------
# We use 'analyze' to parse files into the WORK library first.
# This ensures sub-modules are available during elaboration.
puts "INFO: Analyzing RTL files..."

# Capture both .v and .sv files
set rtl_files [glob -nocomplain ./gact/*.{v,sv}]

if {[llength $rtl_files] == 0} {
    puts "ERROR: No RTL files found in ./gact/"
    exit
}

foreach f [lsort $rtl_files] {
    puts "  Analyzing: $f"
    analyze -format sverilog $f
}

# ---------- Elaborate ----------
# This builds the hierarchy and resolves the sub-module references.
elaborate $DESIGN_NAME
current_design $DESIGN_NAME

# Check for unresolved references immediately
link

# Check if any black boxes remain before spending time on compilation
set check_links [check_design]
if {[regexp "unresolved" $check_links]} {
    puts "WARNING: There are still unresolved references (black boxes)!"
}

# ---------- Constraints ----------
create_clock -name clk -period 1.0 [get_ports clk]
set_clock_uncertainty 0.1 [get_clocks clk]

set_input_delay  0.1 -clock clk [all_inputs]
set_output_delay 0.1 -clock clk [all_outputs]

set_max_transition 0.15 [current_design]
set_max_fanout 10 [current_design]

# ---------- Compile ----------
# compile_ultra is best for high-performance arithmetic like SW Arrays
compile_ultra

# ---------- Reports ----------
report_area   -hierarchy > $REPORT_DIR/area.rpt
report_power  -hierarchy > $REPORT_DIR/power.rpt
report_timing            > $REPORT_DIR/timing.rpt
report_reference         > $REPORT_DIR/references.rpt

# ---------- Save ----------
write -format ddc -hierarchy -output $REPORT_DIR/${DESIGN_NAME}.ddc

puts "INFO: Synthesis Complete. Check $REPORT_DIR/area.rpt for results."
quit
