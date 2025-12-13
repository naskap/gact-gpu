import cocotb
from cocotb.triggers import RisingEdge
from .helpers.setup import setup
from .helpers.memory import Memory
from .helpers.format import format_cycle
from .helpers.logger import logger
from .helpers.assembler import assemble
def smith_waterman(ref, query):

    #    A    C   G   T
    score_matrix = [
        [ 1, -1, -1, -1],   # A
        [-1,  1, -1, -1],   # C
        [-1, -1,  1, -1],   # G
        [-1, -1, -1,  1],   # T
    ]

    nucleotide_to_idx = {ord(char) : i for i, char in enumerate(['A','C','G','T'])}


    gap_open = -1
    gap_extend = -1

    n, m = len(ref), len(query)

    # DP matrices:
    H = [[0]*(m+1) for _ in range(n+1)] # Best score
    E = [[0]*(m+1) for _ in range(n+1)] # Best score assuming the last square was a horizontal gap (insertion)
    F = [[0]*(m+1) for _ in range(n+1)] # Best score assuming the last square was a vertical gap (deletion)
    # Track max for traceback
    max_score = 0
    max_pos = (0, 0)

    for i in range(1, n+1):
        for j in range(1, m+1):
        
            match = score_matrix[nucleotide_to_idx[ord(ref[i-1])]][nucleotide_to_idx[ord(query[j-1])]]
            E[i][j] = max(H[i][j-1] + gap_open,
                          E[i][j-1] + gap_extend)

            F[i][j] = max(H[i-1][j] + gap_open,
                          F[i-1][j] + gap_extend)


            diag = H[i-1][j-1] + match
            H[i][j] = max(0, diag, E[i][j], F[i][j])

            if H[i][j] > max_score:
                max_score = H[i][j]
                max_pos = (i, j)

    # Traceback
    i, j = max_pos

    tb_reversed = []
    HORIZONTAL = 1
    VERTICAL = 2
    MATCH = 3

    while i > 0 and j > 0 and H[i][j] > 0:
        score = H[i][j]
        diag = H[i-1][j-1]
        up   = H[i-1][j]
        left = H[i][j-1]

        match = score_matrix[nucleotide_to_idx[ord(ref[i-1])]][nucleotide_to_idx[ord(query[j-1])]]

        if score == diag + match:
            tb_reversed.append(MATCH)
            i -= 1
            j -= 1
        elif score == left + gap_extend or score == left + gap_open:
            tb_reversed.append(HORIZONTAL)
            j -= 1
        elif score == up + gap_extend or score == up + gap_open:
            tb_reversed.append(VERTICAL)
            i -= 1
        else:
            break


    return {
        "score": max_score,
        "ref_pos" : max_pos[0] - 1,
        "query_pos" : max_pos[1] - 1,
        "tb": list(tb_reversed)
    }

@cocotb.test()
async def test_both(dut):
    """
    This program runs the parallel part of d_soft (the bin overlap calculations)
    defined in d_soft/gpu_d_soft.py on 4 different GPU cores for data that 
    easily fits in the data memory size and data bit size. 
    The second program utilizes the candidate indicies found by the prior program
    and brings the reference and query bits into the memory.
    The third program runs GACT on the three candidates. 
    
    The filtering and alignment pipeline is broken up into three programs
    because TinyGPU only allows one program to run at once. Thus, to get the 
    exact cycle counts, we run:
    d_soft -> output_1 
    output_1 -> mem_movement -> output_2 
    output_2 -> GACT
    And add the cycle counts together

    The d_soft step takes: 3106 cycles
    The mem step takes: 4215 cycles
    The GACT step takes: 543 cycles
    Total cycles: 7,864

    Important notes:
    Set the mode variable below to run the different steps
    You must search and change the following variables in the src folder:
    parameter THREADS_PER_BLOCK = 1
    parameter NUM_CORES = 4,
    """
    # mode changes which test you are running
    mode = 1
    print(f"mode is {mode}")
    # mode 1 = d_soft step
    # mode 2 = memory step
    # mode 3 = GACT step

    # Program Memory
    program_memory = Memory(dut=dut, addr_bits=8, data_bits=16, channels=1, name="program")
    # this program performs the parallel part of d_soft
    program_1 = assemble("""
CONST R0, #4                   ; k = 4
CONST R1, #8                   ; h = 8
CONST R2, #0
SUB   R2, R2, R0               ; last_hit_pos = -4
CONST R3, #0                   ; bp_count = 0

                                            
CONST R4, #2                   ; R4 = 2
MUL R4, R4, %blockIdx          ; R4 = 2*(%blockIdx)
CONST R5, #1                   ; R5 = 1   
ADD R4, R5, R4                 ; R4 = 1 + R4
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
  LDR R12, R10                 ; R12 = i_val addr is R10
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
  CONST R2, #2                    
  MUL R2, R2, %blockIdx    ; R2 = 2* blockIdx
  ADD R0, R0, R2           ; R0 = R0 + R2
  ADD R1, R1, R2           ; R1 = R1 + R2                               
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
    
    # this program copies the memory into GACT's expected format
    """
    Original Format: 
    - reference and query indicies are stored at index 50
    - the reference genome is stored at 150
    - the query genome is stored at 230
    - the GACT expected memory format starts at 60, then 90, then 120
    """
    program_2 = assemble("""
    CONST R0, #150      ; 150 mem_addr of ref
    CONST R1 #230       ; 230 mem_addr of query
    CONST R2, #50       ; 50 mem_addr of index_ref
    
    CONST R3, #2       ; R3 = 2
    MUL R3, R3, %blockIdx    ; R3 = 2 * blockIdx
    ADD R3, R3, R2        ; mem_addr of index_ref = 50 + block index*2

    LDR R2, R3         ; R2 = read index_ref
    ADD R2, R2, R0    ; R2 = read index_ref + base addr
    CONST R9, #1       ; R9 = 1
    ADD R3, R3, R9     ; R3++
    LDR R3, R3         ;read index_query
    ADD R3, R3, R1    ; R3 = read index_query + base addr
                         
    CONST R4, #8       ; 8 is length of ref
    CONST R5, #60      ; 60 is data_addr_r1 of r1
    CONST R6, #30       ; R6 = 30
    MUL R6, R6, %blockIdx ; R6 = 30*block index
    ADD R5, R5, R6    ; R5 = data_addr of r1 = 60 + 30*block index
    ADD R10, R5, R4    ; R10 = data_add of q1 = 60 + 30*block index + ref length
    CONST R6, #0     ; R6 = i

LOOP1_START:
    CMP R4, R6     ; length of ref - i < 0 
    BRn LOOP1_END 
    CMP R4, R6     ; length of ref - i = 0 
    BRz LOOP1_END 

    ; mem[R5] = mem[R2 + i]
    ADD R7, R2, R6 ; R7 = R2 + i
    LDR R0, R7    ; R0 = mem[R2 + i]
    STR R5, R0     ; mem[R5] = mem[R2+i]

    ADD R6, R6, R9 ; i++
    ADD R5, R5, R9 ; R5++

    CMP R9, R9               ; cmp = 0
    BRz LOOP1_START           ; 

LOOP1_END:
    CONST R6, #0        ; i = 0     
    CONST R8, #4          ; length of query
                                                       
LOOP2_START:  
    CMP R8, R6     ; length of ref - i < 0 
    BRn LOOP2_END 
    CMP R8, R6     ; length of ref - i = 0 
    BRz LOOP2_END 
                                
    ; mem[R10] = mem[R3 + i]
    ADD R7, R3, R6 ; R7 = R3 + i
    LDR R0, R7    ; R0 = mem[R3 + i]
    STR R10, R0     ; mem[R10] = mem[R3+i]

    ADD R6, R6, R9 ; i++
    ADD R10, R10, R9 ; R10++

    CMP R9, R9               ; cmp = 0
    BRz LOOP2_START           ;                                                                                          
LOOP2_END:
    RET
    """)

    # data_1 construction
    addr_bits = 8
    data_memory = Memory(dut=dut, addr_bits=8, data_bits=16, channels=4, name="data")
    length = 2 ** addr_bits
    data_1 = [0] * length
    data_bin = [
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
    data_1[:len(data_bin)] = data_bin
    
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

    # GACT constants
    num_blocks       = 2
    ref_length       = 8
    query_length     = 4
    threads_per_warp = 4
    result_length    = ref_length + query_length + 3 # Format of result: score, ref pos, query pos, traceback  


    # GACT
    program_3 = assemble(f"""
CFG_REF_LEN #{ref_length}          
CFG_QUERY_LEN #{query_length}

CONST R1, #{ref_length + query_length + result_length}   ; elmts_per_alignment      
; reference address = %blockIdx * 30 + 60 !!! must fix this!! 
CONST R0, #60 ; R0 = 60
CONST R5, #30 ; R1 = 30
MUL, R5, R5,  %blockIdx ; 30*blockIdx
ADD R1, R5, R0      ; reference address = 30*blockIdx + 60
CFG_REF_ADDR R1

CONST R2, #{ref_length}
ADD   R1, R1, R2                           ; query address = reference address + reference size
CFG_QUERY_ADDR R1

CONST R2, #{query_length}
ADD R1, R1, R2                           ; dir_address = query address + query length
CFG_DIR_ADDR R1

START_SW
RET                                                   ; end of kernel
""")
    
    entire_ref = "ATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATG"
    query = "ATGCTGGG"
    ref_length = 8

    # the candiates are (4,4), (20, 4) and (37, 4)
    query_list = list(query[4:])
    ref_list = list(entire_ref)
    entire_query_list = list(query)
    ref_1 = list(entire_ref[4:12])

    # data 2 construction
    data_2 = [0] * length
    data_2[50] = 4
    data_2[51] = 4
    data_2[52] = 20
    data_2[53] = 4
    data_2[54] = 37
    data_2[55] = 4
    # append the reference to the data starting at index 150
    i = 150
    for item in ref_list:
        data_2[i] = ord(item)
        i += 1
    # append the query to the data memory starting at index 230
    i = 230
    for item in entire_query_list:
        data_2[i] = ord(item)
        i += 1
    print(data_2)
    data_2_int = []
    for item in data_2:
        data_2_int.append(int(item))

    # get the expected sw results
    expected = []
    expected.append(smith_waterman(ref_1, query_list))
    ref_2 = list(entire_ref[20:28])
    expected.append(smith_waterman(ref_2, query_list))
    ref_3 = list(entire_ref[37:45])
    expected.append(smith_waterman(ref_3, query_list))
    # ref_1_ord = [ord(item) for item in ref_1]
    # ref_2_ord = [ord(item) for item in ref_2]
    # ref_3_ord = [ord(item) for item in ref_3]
    query = [ord(item) for item in query_list]
    # print(f"expected results for {ref_1_ord} and {query} are {expected[0]}")
    # print(f"expected results for {ref_2_ord} and {query_list}  are {expected[1]}")
    # print(f"expected results for {ref_3_ord} and {query_list}  are {expected[2]}")
    # construct data 3
    data_3_original = expected_results_2 = [[84, 71, 71, 71, 65, 67, 71, 84, 84, 71, 71, 71], [84, 71, 71, 71, 84, 84, 65, 67,  84, 71, 71, 71], [84, 71, 71, 71, 67, 67, 71, 84,  84, 71, 71, 71]]
    index = 60
    data_3 = [0] * length
    for item in data_3_original:
        for letter in item:
            data_3[index] = letter
            index += 1
        index += 18

    # Device Control with a mode mux!
    threads = 1
    if mode == 1:
        await setup(
            dut=dut,
            program_memory=program_memory,
            program=program_1,
            data_memory=data_memory,
            data=data_1,
            threads=threads
        )
    if mode == 2:
        await setup(
            dut=dut,
            program_memory=program_memory,
            program=program_2,
            data_memory=data_memory,
            data=data_2_int,
            threads=threads
        )
    if mode == 3:
        await setup(
            dut=dut,
            program_memory=program_memory,
            program=program_3,
            data_memory=data_memory,
            data=data_3,
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
    # expected results depend on the mode
    if mode == 1:
        # the results should be at 50-55
        expected_results_1 = [(4,4), (20,4), (37,4)]
        print(f"mem at 50 is {data_memory.memory[50]}")
        print(f"mem at 51 is {data_memory.memory[51]}")
        print(f"mem at 52 is {data_memory.memory[52]}")
        print(f"mem at 53 is {data_memory.memory[53]}")
        print(f"mem at 54 is {data_memory.memory[54]}")
        print(f"mem at 55 is {data_memory.memory[55]}")
        i = 50
        for expected in expected_results_1:
            result_one = data_memory.memory[i]
            result_two = data_memory.memory[i + 1]
            assert result_one == expected[0], f"Result mismatch at index {i}: expected {expected[0]}, got {result_one}"
            assert result_two == expected[1], f"Result mismatch at index {i + 1}: expected {expected[1]}, got {result_two}"
            i += 2
    if mode == 2:
        # the results should be at 60, 90, and 120
        expected_results_2 = [[84, 71, 71, 71, 65, 67, 71, 84, 84, 71, 71, 71], [84, 71, 71, 71, 84, 84, 65, 67,  84, 71, 71, 71], [84, 71, 71, 71, 67, 67, 71, 84,  84, 71, 71, 71]]
        index = 60
        for item in expected_results_2:
            for letter in item:
                result = data_memory.memory[index]
                assert result == letter, f"Result mismatch at index {index}: expected {letter}, got {result}"
                index += 1
            index += 18
    if mode == 3:
        # the results should be at 72, 102, and 132
        expected_results_3 = []
        for dict_item in expected:
            list_d = []
            for _, value in dict_item.items():
                if isinstance(value, list):
                    for item in value:
                        list_d.append(item)
                else:
                    list_d.append(value)
            expected_results_3.append(list_d)
            print(expected_results_3)
        index = 72
        for item in expected_results_3:
            for score in item:
                print(index)
                result = data_memory.memory[index]
                assert result == score, f"Result mismatch at index {index}: expected {score}, got {result}"
                index += 1
            index += 23
        

