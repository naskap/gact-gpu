import cocotb
from cocotb.triggers import RisingEdge
from .helpers.setup import setup
from .helpers.memory import Memory
from .helpers.format import format_cycle
from .helpers.logger import logger
from .helpers.assembler import assemble

@cocotb.test()
async def test_one_thread(dut):
    """
    This program runs the parallel part of d_soft (the bin overlap calculations)
    defined in d_soft/gpu_d_soft.py on one thread as a baseline.

    !!***** Change the data address on line 33 for bin configuration *****!!

    Important note:
    You must search and change the following variables in the src folder:
    parameter THREADS_PER_BLOCK = 1
    parameter NUM_CORES = 4,
    """
    # Program Memory
    program_memory = Memory(dut=dut, addr_bits=8, data_bits=16, channels=1, name="program")

    program = assemble("""
CONST R0, #4                   ; k = 4
CONST R1, #8                   ; h = 8
CONST R2, #0
SUB   R2, R2, R0               ; last_hit_pos = -4
CONST R3, #0                   ; bp_count = 0

                                            
CONST R4, #1                  ; R4 = 1 CHANGE ME to 1,3,5,7 for bin0,bin1,bin2,bin3
CONST R5, #1                   ; R5 = 1   
LDR R7, R4                     ; R7 = mem[R4]
SUB R7, R7, R5                 ; R7 = size - 1
ADD R4, R5, R4                 ; R4 = 1 + R4
LDR R8, R4                     ; R8 = bin base addr
                                                                                                                                                           
                                                                     
; i = 0                       
CONST R11, #0                  ; i = 0

LOOP_START:
  CMP R7, R11              ; cmp = i - size
  BRz LOOP_END                 ; if i > size, break
  CMP R7, R11              ; cmp = i - size
  BRn LOOP_END                 ; if i > size, break                     
  CONST R9, #1             ;1
                       
  ; i_val = bin_one[i]   ; j_val = bin_one[i + 1]
  ADD R10, R8, R11             ; R10 = address = 6 + i 
  LDR R12, R10                 ; R12 = i_val
  ADD R10, R10, R9              ; R10++
  LDR R4, R10                  ; R4 = j_val

  ; overlap = max(0, last_hit_pos + k - j_val)
  ADD R5, R2, R0            ; R5 =    last_hit_pos + k
  SUB R5, R5, R4            ; R5 = R5 - j_val
  CONST R6, #0              ; R6 = 0
  CMP R5, R6                ; cmp = R5 - R6 
  BRp SKIP_OVERLAP                                                       
  ADD R5, R6, R6            ; R5 = 0
                       
SKIP_OVERLAP:
  ; last_hit_pos = j_val
  ADD R2, R6, R4

  ; bp_count = bp_count + k - overlap  
  ADD R3, R3, R0   ; R3 = R3 + k                                                                            
  SUB R3, R3, R5   ; R3 = R3 - overlap


  ; R5 = (h + k - overlap) 
  SUB R5, R6, R5   ; R5 = -R5
  ADD R5, R5, R1   ; R5 = -overlap + h
  ADD R5, R5, R0   ; R5 = R5 + k   

  ; (h + k - overlap > bp_count)
  ;  (h + k - overlap <= bp_count) => SKIP_MEM_SET              
  CMP R5, R3       ; R5 - R3 (h + k - overlap) - bp_count  < 0 
  BRn SKIP_MEM_SET
  CMP R5, R3       ; R5 - R3 (h + k - overlap) - bp_count  == 0 
  BRz SKIP_MEM_SET    
                    
                       
  ;  (bp_count >= h) 
  ;  (bp_count < h)       => SKIP_MEM_SET                    
  CMP R3, R1     ; bp_count - h
  BRn SKIP_MEM_SET 

  ; Store result in mem[50 + 2 * %blockIdx  , 51 + 2 * %blockIdx]                     
  CONST R0, #50
  CONST R1, #51                          
  STR R0, R12 ; mem[] = i_val  
  STR R1, R4 ; mem[41] = j_val 
  RET                                                                                                                                                          
              
                                                                                                     
SKIP_MEM_SET:
                                                                                                                                     
  ; loop update stuff                    
  CONST R9, #1             ;1
  ADD R11, R9, R11         ; i++
  ADD R11, R9, R11         ; i++                    
  CMP R9, R9               ; cmp = 0
  BRz LOOP_START           ;  

LOOP_END:
  RET
""")

    # Data Memory
    data_memory = Memory(dut=dut, addr_bits=8, data_bits=8, channels=4, name="data")
    data = [
        4, # number of bins
        10, # Size of bin 1
        9, # Start address of bin 1
        10, # Size of bin 2
        19, # Start address of bin 2
        10, # Size of bin 3
        29, # Start address of bin 3
        2, # Size of bin 4
        39, # Start address of bin 4
        # start of bin data
        0, 0, 1, 1, 2, 2, 3, 3, 4, 4, # 0: [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)], 
        16, 0, 17, 1, 18, 2, 19, 3, 20, 4, # 1: [(16, 0), (17, 1), (18, 2), (19, 3), (20, 4)], # 6
        33, 0, 34, 1, 35, 2, 36, 3, 37, 4, # 2: [(33, 0), (34, 1), (35, 2), (36, 3), (37, 4)], # 11
        61, 2, # 4: [(61, 2)], # 16
    ]
    # %blockIdx 0 1 2 3 4
    # address of size = 1 + 2(%blockIdx)
    # address of start address = address of size + 1
    # size[1] = 1
    # start_address[1] = mem[2]
    # size[2] = 3
    # start_address[2] = mem[4]
    # size[3] = 5
    # start_address[3] = mem[5]
    # size[4] = 7
    # start_address[4] = mem[6]
    # size[5] = 9
    # start_address[5] = mem[7]

    # Device Control
    threads = 1

    await setup(
        dut=dut,
        program_memory=program_memory,
        program=program,
        data_memory=data_memory,
        data=data,
        threads=threads
    )

    data_memory.display(256) 

    cycles = 0
    while dut.done.value != 1:
        data_memory.run()
        program_memory.run()

        await cocotb.triggers.ReadOnly()
        format_cycle(dut, cycles)
        
        await RisingEdge(dut.clk)
        cycles += 1

    logger.info(f"Completed in {cycles} cycles")
    data_memory.display(256)
    expected_results = [(4,4), (20,4), (37,4)]
    print(f"mem at 50 is {data_memory.memory[50]}")
    print(f"mem at 51 is {data_memory.memory[51]}")
    # print(f"mem at 52 is {data_memory.memory[52]}")
    # print(f"mem at 53 is {data_memory.memory[53]}")
    # print(f"mem at 54 is {data_memory.memory[54]}")
    # print(f"mem at 55 is {data_memory.memory[55]}")
    i = 50
    # for expected in expected_results:
    #     result_one = data_memory.memory[i]
    #     result_two = data_memory.memory[i + 1]
    #     assert result_one == expected[0], f"Result mismatch at index {i}: expected {expected[0]}, got {result_one}"
    #     assert result_two == expected[1], f"Result mismatch at index {i + 1}: expected {expected[1]}, got {result_two}"
    #     i += 2

