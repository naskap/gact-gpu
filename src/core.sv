`default_nettype none
`timescale 1ns/1ns

// COMPUTE CORE
// > Handles processing 1 block at a time
// > The core also has it's own scheduler to manage control flow
// > Each core contains 1 fetcher & decoder, and register files, ALUs, LSUs, PC for each thread
module core #(
    parameter DATA_MEM_ADDR_BITS = 8,
    parameter DATA_MEM_DATA_BITS = 8,
    parameter PROGRAM_MEM_ADDR_BITS = 8,
    parameter PROGRAM_MEM_DATA_BITS = 16,
    parameter THREADS_PER_BLOCK = 4
) (
    input wire clk,
    input wire reset,

    // Kernel Execution
    input wire start,
    output wire done,

    // Block Metadata
    input wire [7:0] block_id,
    input wire [$clog2(THREADS_PER_BLOCK):0] thread_count,

    // Program Memory
    output reg program_mem_read_valid,
    output reg [PROGRAM_MEM_ADDR_BITS-1:0] program_mem_read_address,
    input reg program_mem_read_ready,
    input reg [PROGRAM_MEM_DATA_BITS-1:0] program_mem_read_data,

    // Data Memory
    output reg [THREADS_PER_BLOCK-1:0] data_mem_read_valid,
    output reg [DATA_MEM_ADDR_BITS-1:0] data_mem_read_address [THREADS_PER_BLOCK-1:0],
    input reg [THREADS_PER_BLOCK-1:0] data_mem_read_ready,
    input reg [DATA_MEM_DATA_BITS-1:0] data_mem_read_data [THREADS_PER_BLOCK-1:0],
    output reg [THREADS_PER_BLOCK-1:0] data_mem_write_valid,
    output reg [DATA_MEM_ADDR_BITS-1:0] data_mem_write_address [THREADS_PER_BLOCK-1:0],
    output reg [DATA_MEM_DATA_BITS-1:0] data_mem_write_data [THREADS_PER_BLOCK-1:0],
    input reg [THREADS_PER_BLOCK-1:0] data_mem_write_ready
);
    // State
    reg [2:0] core_state;
    reg [2:0] fetcher_state;
    reg [15:0] instruction;

    // Intermediate Signals
    reg [7:0] current_pc;
    wire [7:0] next_pc[THREADS_PER_BLOCK-1:0];
    reg [7:0] rs[THREADS_PER_BLOCK-1:0];
    reg [7:0] rt[THREADS_PER_BLOCK-1:0];
    reg [1:0] lsu_state[THREADS_PER_BLOCK-1:0];
    reg [7:0] lsu_out[THREADS_PER_BLOCK-1:0];
    wire [7:0] alu_out[THREADS_PER_BLOCK-1:0];
    
    // Decoded Instruction Signals
    reg [3:0] decoded_rd_address;
    reg [3:0] decoded_rs_address;
    reg [3:0] decoded_rt_address;
    reg [2:0] decoded_nzp;
    reg [7:0] decoded_immediate;

    // Decoded Control Signals
    reg decoded_reg_write_enable;           // Enable writing to a register
    reg decoded_mem_read_enable;            // Enable reading from memory
    reg decoded_mem_write_enable;           // Enable writing to memory
    reg decoded_nzp_write_enable;           // Enable writing to NZP register
    reg [1:0] decoded_reg_input_mux;        // Select input to register
    reg [1:0] decoded_alu_arithmetic_mux;   // Select arithmetic operation
    reg [2:0] decoded_gact_config_state;
    wire decoded_gact_config_mux;
    reg decoded_alu_output_mux;             // Select operation in ALU
    reg decoded_pc_mux;                     // Select source of next PC
    reg decoded_ret;

    // 
    wire [THREADS_PER_BLOCK-1:0] lsu_read_valid;
    wire [THREADS_PER_BLOCK-1:0] lsu_write_valid;
    wire [DATA_MEM_ADDR_BITS-1:0] lsu_read_addr [THREADS_PER_BLOCK-1:0];
    wire [DATA_MEM_ADDR_BITS-1:0] lsu_write_addr [THREADS_PER_BLOCK-1:0];
    wire [THREADS_PER_BLOCK-1:0] lsu_read_ready = gact_ready ? data_mem_read_ready : '0;
    wire [THREADS_PER_BLOCK-1:0] lsu_write_ready = gact_ready ? data_mem_write_ready : '0;
    wire [DATA_MEM_ADDR_BITS-1:0] lsu_write_data [THREADS_PER_BLOCK-1:0];

    
    wire gact_dmem_read_valid;
    assign data_mem_read_valid = gact_ready ? lsu_read_valid : gact_dmem_read_valid;
    assign data_mem_read_address = gact_ready ? lsu_read_addr : gact_dmem_addr;
    assign data_mem_write_valid = gact_ready ? lsu_write_valid : dir_valid;
    assign data_mem_write_data = gact_ready ? lsu_write_data : dir;
    assign data_mem_write_address = gact_ready ? lsu_write_addr : gact_dmem_addr;


    // Fetcher
    fetcher #(
        .PROGRAM_MEM_ADDR_BITS(PROGRAM_MEM_ADDR_BITS),
        .PROGRAM_MEM_DATA_BITS(PROGRAM_MEM_DATA_BITS)
    ) fetcher_instance (
        .clk(clk),
        .reset(reset),
        .core_state(core_state),
        .current_pc(current_pc),
        .mem_read_valid(program_mem_read_valid),
        .mem_read_address(program_mem_read_address),
        .mem_read_ready(program_mem_read_ready),
        .mem_read_data(program_mem_read_data),
        .fetcher_state(fetcher_state),
        .instruction(instruction) 
    );

    // Decoder
    decoder decoder_instance (
        .clk(clk),
        .reset(reset),
        .core_state(core_state),
        .instruction(instruction),
        .decoded_rd_address(decoded_rd_address),
        .decoded_rs_address(decoded_rs_address),
        .decoded_rt_address(decoded_rt_address),
        .decoded_nzp(decoded_nzp),
        .decoded_immediate(decoded_immediate),
        .decoded_gact_config_state(decoded_gact_config_state),
        .decoded_gact_config_mux(decoded_gact_config_mux),
        .decoded_reg_write_enable(decoded_reg_write_enable),
        .decoded_mem_read_enable(decoded_mem_read_enable),
        .decoded_mem_write_enable(decoded_mem_write_enable),
        .decoded_nzp_write_enable(decoded_nzp_write_enable),
        .decoded_reg_input_mux(decoded_reg_input_mux),
        .decoded_alu_arithmetic_mux(decoded_alu_arithmetic_mux),
        .decoded_alu_output_mux(decoded_alu_output_mux),
        .decoded_pc_mux(decoded_pc_mux),
        .decoded_ret(decoded_ret)
    );

    // Scheduler
    scheduler #(
        .THREADS_PER_BLOCK(THREADS_PER_BLOCK),
    ) scheduler_instance (
        .clk(clk),
        .reset(reset),
        .start(start),
        .fetcher_state(fetcher_state),
        .core_state(core_state),
        .decoded_mem_read_enable(decoded_mem_read_enable),
        .decoded_mem_write_enable(decoded_mem_write_enable),
        .decoded_ret(decoded_ret),
        .lsu_state(lsu_state),
        .gact_ready(gact_ready),
        .current_pc(current_pc),
        .next_pc(next_pc),
        .done(done)
    );


    wire        clear_done      = 1'b1;
    wire [7:0]  align_fields    = 8'(1<<5);

    // Triangular score matrix with mismatch = -1, match = 1
    wire signed [9:0] params [0:11];
    assign params[11] = 1;
    assign params[10] = -1;
    assign params[9]  = -1;
    assign params[8]  = -1;
    assign params[7]  = 1;
    assign params[6]  = -1;
    assign params[5]  = -1;
    assign params[4]  = 1;
    assign params[3]  = -1;
    assign params[2]  = 1;
    assign params[1]  = -1;
    assign params[0]  = -1;

    wire [119:0] in_params = {params[11], params[10], params[9], params[8],
                              params[7],  params[6],  params[5], params[4],
                              params[3],  params[2],  params[1], params[0]};

    
    localparam PE_WIDTH = 10;
    localparam BLOCK_WIDTH = 3;
    localparam MAX_TILE_SIZE = 64;
    localparam NUM_PE = 4;
    localparam REF_FILENAME = "";
    localparam QUERY_FILENAME = "";
    localparam NUM_DIR_BLOCK = 32;
    localparam DIR_BRAM_ADDR_WIDTH = 5;
    localparam REQUEST_ID_WIDTH   = 16;

    // Other GACTTop inputs (match widths from module parameters)
    wire [$clog2(MAX_TILE_SIZE):0] max_tb_steps = 10'd400;
    wire [$clog2(MAX_TILE_SIZE)-BLOCK_WIDTH-1:0] query_addr_in = '0;
    wire [8*(2**BLOCK_WIDTH)-1:0] query_in = '0;
    wire query_wr_en = 1'b0;
    wire [$clog2(MAX_TILE_SIZE)-BLOCK_WIDTH-1:0] ref_addr_in = '0;
    wire [8*(2**BLOCK_WIDTH)-1:0] ref_in = '0;
    wire ref_wr_en = 1'b0;
    wire [REQUEST_ID_WIDTH-1:0] req_id_in = '0;
    wire [PE_WIDTH-1:0] score_threshold = '0;
    wire [DIR_BRAM_ADDR_WIDTH-1:0] dir_rd_addr = '0;
    wire [1:0] addr_cfg_type = '0;
    wire [DIR_BRAM_ADDR_WIDTH-1:0] addr_cfg = '0;

    wire [7:0] gact_cfg = decoded_gact_config_mux ? rt[0] : decoded_immediate;

    reg set_params;

    wire gact_dmem_read_ready = gact_ready ? 0 : data_mem_read_ready;
    wire gact_dmem_read_valid;
    wire [7:0] gact_dmem_addr; // Serves as both read and write addr
    wire [7:0] dmem_data = data_mem_read_data;

    // Outputs from GACTTop
    wire [1:0] dir;
    wire dir_valid;
    wire [2*NUM_DIR_BLOCK-1:0] dir_data_out;
    wire [DIR_BRAM_ADDR_WIDTH-1:0] dir_total_count;
    wire gact_done; // keep separate from core's done
    wire [$clog2(MAX_TILE_SIZE)-1:0] num_query_bases;
    wire [$clog2(MAX_TILE_SIZE)-1:0] num_ref_bases;
    wire [2*$clog2(MAX_TILE_SIZE)-1:0] num_tb_steps;
    wire [$clog2(MAX_TILE_SIZE)-1:0] query_max_pos;
    wire gact_ready;
    wire [$clog2(MAX_TILE_SIZE)-1:0] ref_max_pos;
    wire [REQUEST_ID_WIDTH-1:0] req_id_out;
    wire [PE_WIDTH-1:0] tile_score;

    reg gact_start;
    reg gact_started;
    always @(posedge clk) begin
        set_params <= reset; // Trails reset by 1
        if(instruction[15:8] == 8'b10100101 && gact_started == 1'b0) begin
            gact_start <= 1'b1;
            gact_started <= 1'b1;
        end
        else if (instruction[15:8] == 8'b10100101 && gact_started == 1'b1)begin
            gact_start <= 1'b0;
        end
        else begin
            gact_start <= 1'b0;
            gact_started <= 1'b0;
        end
    end

    GACTTop #(
      .PE_WIDTH(PE_WIDTH), // Bitwidth of scores
      .BLOCK_WIDTH(BLOCK_WIDTH), // address bits for BRAM
      .MAX_TILE_SIZE(MAX_TILE_SIZE), // 64x64 is the max size -- determines internal BRAM
      .NUM_PE(NUM_PE), 
      .REQUEST_ID_WIDTH(16), // I think this is just for bookkeeping
      .NUM_DIR_BLOCK(4) // So that dir_data_in is 8 bits
    ) gact_instance (
      .clk(clk),
      .rst(reset),
      .align_fields(align_fields),

      .clear_done(clear_done),
      .in_params(in_params),
      .max_tb_steps(max_tb_steps),
      .query_addr_in(3'b0),
      .query_in(query_in),
      .query_wr_en(query_wr_en),
      .ref_addr_in(3'b0),
      .ref_in(ref_in),
      .ref_wr_en(ref_wr_en),
      .req_id_in(req_id_in),
      .score_threshold(score_threshold),
      .set_params(set_params),
      .start(gact_start),

      .dir(dir),
      .dir_valid(dir_valid),

      .done(gact_done),
      .num_query_bases(num_query_bases),
      .num_ref_bases(num_ref_bases),
      .num_tb_steps(num_tb_steps),
      .query_max_pos(query_max_pos),
      .ready(gact_ready),
      .ref_max_pos(ref_max_pos),
      .req_id_out(req_id_out),
      .tile_score(tile_score), 
      .cfg_type(decoded_gact_config_state),
      .cfg(gact_cfg),
      .dmem_read_ready(gact_dmem_read_ready),
      .dmem_read_valid(gact_dmem_read_valid),
      .dmem_addr(gact_dmem_addr),
      .dmem_data(dmem_data),
      .dmem_write_ready(data_mem_write_ready)
    );

    // Dedicated ALU, LSU, registers, & PC unit for each thread this core has capacity for
    genvar i;
    generate
        for (i = 0; i < THREADS_PER_BLOCK; i = i + 1) begin : threads
            // ALU
            alu alu_instance (
                .clk(clk),
                .reset(reset),
                .enable(i < thread_count),
                .core_state(core_state),
                .decoded_alu_arithmetic_mux(decoded_alu_arithmetic_mux),
                .decoded_alu_output_mux(decoded_alu_output_mux),
                .rs(rs[i]),
                .rt(rt[i]),
                .alu_out(alu_out[i])
            );

            // LSU
            lsu lsu_instance (
                .clk(clk),
                .reset(reset),
                .enable(i < thread_count),
                .core_state(core_state),
                .decoded_mem_read_enable(decoded_mem_read_enable),
                .decoded_mem_write_enable(decoded_mem_write_enable),
                .mem_read_valid(lsu_read_valid[i]),
                .mem_read_address(lsu_read_addr[i]),
                .mem_read_ready(lsu_read_ready[i]),
                .mem_read_data(data_mem_read_data[i]),
                .mem_write_valid(lsu_write_valid[i]),
                .mem_write_address(lsu_write_addr[i]),
                .mem_write_data(lsu_write_data[i]),
                .mem_write_ready(data_mem_write_ready[i]),
                .rs(rs[i]),
                .rt(rt[i]),
                .lsu_state(lsu_state[i]),
                .lsu_out(lsu_out[i])
            );

            // Register File
            registers #(
                .THREADS_PER_BLOCK(THREADS_PER_BLOCK),
                .THREAD_ID(i),
                .DATA_BITS(DATA_MEM_DATA_BITS),
            ) register_instance (
                .clk(clk),
                .reset(reset),
                .enable(i < thread_count),
                .block_id(block_id),
                .core_state(core_state),
                .decoded_reg_write_enable(decoded_reg_write_enable),
                .decoded_reg_input_mux(decoded_reg_input_mux),
                .decoded_rd_address(decoded_rd_address),
                .decoded_rs_address(decoded_rs_address),
                .decoded_rt_address(decoded_rt_address),
                .decoded_immediate(decoded_immediate),
                .alu_out(alu_out[i]),
                .lsu_out(lsu_out[i]),
                .rs(rs[i]),
                .rt(rt[i])
            );

            // Program Counter
            pc #(
                .DATA_MEM_DATA_BITS(DATA_MEM_DATA_BITS),
                .PROGRAM_MEM_ADDR_BITS(PROGRAM_MEM_ADDR_BITS)
            ) pc_instance (
                .clk(clk),
                .reset(reset),
                .enable(i < thread_count),
                .core_state(core_state),
                .decoded_nzp(decoded_nzp),
                .decoded_immediate(decoded_immediate),
                .decoded_nzp_write_enable(decoded_nzp_write_enable),
                .decoded_pc_mux(decoded_pc_mux),
                .alu_out(alu_out[i]),
                .current_pc(current_pc),
                .next_pc(next_pc[i])
            );
        end
    endgenerate
endmodule
