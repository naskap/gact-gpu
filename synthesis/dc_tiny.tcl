# ===============================
# dc_tiny.tcl
# used Google Gemini to help generate scripts and modified it to our needs: https://gemini.google.com/share/313d2433cab2
# Updated to use analyze/elaborate
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

# Define the WORK library explicitly to store analyzed intermediate files
define_design_lib WORK -path $WORK_DIR

set_app_var target_library $TARGET_LIB
set_app_var link_library   $LINK_LIB
set_app_var search_path    [list . ./tiny]

set hdlin_sv_enable_vpp true
set verilogout_no_tri true

# ---------- Read RTL (Analyze Phase) ----------
# 'analyze' checks syntax and stores the design in the WORK library.
# We include all files in the directory to ensure sub-components like 'alu' are seen.
puts "INFO: Analyzing RTL files in ./tiny..."
set rtl_files [glob -nocomplain ./tiny/*.{v,sv}]

foreach f [lsort $rtl_files] {
    puts "  Analyzing: $f"
    analyze -format sverilog $f
}

# ---------- Elaborate ----------
# 'elaborate' assembles the hierarchy starting from the top module.
# It automatically looks in the 'WORK' library for modules analyzed above.
puts "INFO: Elaborating design $DESIGN_NAME..."
elaborate $DESIGN_NAME
current_design $DESIGN_NAME

# 'link' resolves all module references and ensures no black boxes exist.
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
# Added -hierarchy to see the area contribution of the ALU specifically
report_area -hierarchy > $REPORT_DIR/area.rpt
report_power           > $REPORT_DIR/power.rpt
report_timing          > $REPORT_DIR/timing.rpt
report_reference       > $REPORT_DIR/references.rpt

# ---------- Save ----------
write -format ddc -hierarchy -output $REPORT_DIR/${DESIGN_NAME}.ddc

puts "INFO: Synthesis of $DESIGN_NAME complete."
quit
