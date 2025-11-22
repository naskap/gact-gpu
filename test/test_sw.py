import cocotb
from cocotb.triggers import RisingEdge
from .helpers.setup import setup
from .helpers.memory import Memory
from .helpers.format import format_cycle
from .helpers.logger import logger
from .helpers.assembler import assemble
import random


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
        
            match = score_matrix[nucleotide_to_idx[ref[i-1]]][nucleotide_to_idx[query[j-1]]]
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

        match = score_matrix[nucleotide_to_idx[ref[i-1]]][nucleotide_to_idx[query[j-1]]]

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
async def test_sw(dut):
    # Program Memory
    program_memory = Memory(dut=dut, addr_bits=8, data_bits=16, channels=1, name="program")

    num_blocks       = 2
    ref_length       = 16
    query_length     = 8
    threads_per_warp = 4
    result_length    = ref_length + query_length + 3 # Format of result: score, ref pos, query pos, traceback  


    # Program
    program = assemble(f"""
CFG_REF_LEN #{ref_length}          
CFG_QUERY_LEN #{query_length}

CONST R1, #{ref_length + query_length + result_length}   ; elmts_per_alignment      
MUL   R1, R1, %blockIdx                                      ; reference address = %blockIdx * elmts_per_alignment 
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

    # Data Memory
    data_memory = Memory(dut=dut, addr_bits=8, data_bits=8, channels=4, name="data")

    # Data layout is: reference1, query1, dir1, reference2, query2, dir2, ...
    random.seed(1234321)
    ref   = []
    query = []
    data  = []
    expected_results = []

    nucleotides = ['A', 'C', 'G', 'T']
    get_random_nucleotide = lambda : ord(nucleotides[random.randint(0,3)])
    for j in range(num_blocks):
        ref.append([get_random_nucleotide() for _ in range(ref_length)])
        query.append([elmt for elmt in ref[-1][:query_length]])

        # Random insertion and deletion
        query[-1].pop(random.randint(0,query_length-1))
        query[-1].insert(random.randint(0,query_length-1),get_random_nucleotide())

        # Create dmem packed representation
        data += ref[-1] + query[-1] + [0 for _ in range(result_length)]

        expected_results.append(smith_waterman(ref[-1], query[-1]))

    # Device Control
    threads = num_blocks * threads_per_warp

    await setup(
        dut=dut,
        program_memory=program_memory,
        program=program,
        data_memory=data_memory,
        data=data,
        threads=threads
    )

    data_memory.display((ref_length + query_length + result_length)*num_blocks)

    cycles = 0
    while dut.done.value != 1:
        data_memory.run()
        program_memory.run()

        await cocotb.triggers.ReadOnly()
        format_cycle(dut, cycles)
        
        await RisingEdge(dut.clk)
        cycles += 1

    logger.info(f"Completed in {cycles} cycles")
    data_memory.display((ref_length + query_length + result_length)*num_blocks)

    for block_num in range(num_blocks):
        expected_result = expected_results[block_num]

        start     = block_num*(ref_length + query_length + result_length) + ref_length + query_length
        stop      = start + result_length
        result    = data_memory.memory[start:stop]
        score     = result[0]
        ref_pos   = result[1]
        query_pos = result[2]
        tb        = result[3:]

        assert expected_result["score"] == score, f"observed score = {score} expected {expected_result['score']}"
        assert expected_result["ref_pos"] == ref_pos, f"observed ref pos = {ref_pos} expected {expected_result['ref_pos']}"
        assert expected_result["query_pos"] == query_pos, f"observed query pos = {query_pos} expected {expected_result['query_pos']}"
        assert all([a==b for a,b in zip(tb, expected_result["tb"])]), f"observed tb = {tb} expected {expected_result['tb']}"
        assert tb[len(expected_result["tb"])] == 0, "Elements afterwards should be 0"
