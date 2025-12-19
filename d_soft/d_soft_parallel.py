# Used AI to generate the function comment for the Construct_Seed_Pointer_Table for easy reading
# the chat can be found here: https://chatgpt.com/s/t_693de3540fdc819182e56372f1b37196
def Construct_Seed_Pointer_Table(references, k):
    """
    Build a seed pointer table mapping each k-length substring (seed)
    in each reference to the list of positions where it occurs.
    Used by SeedLookup for fast sequence alignment.
    
    Parameters:
        references (list of str): Reference sequences
        k (int): Seed length
    
    Returns:
        dict: {reference: {seed: [positions]}}
    """

    for reference in references:
        seed_pointer_table = {}
        for i in range(0, len(reference) - k + 1):
            key = reference[i: i + k]
            if key in seed_pointer_table:
                seed_pointer_table[key].append(i)
            else:
                seed_pointer_table[key] = [i]

        reference_pointer_table[reference] = seed_pointer_table

    for ref in reference_pointer_table:
        print(ref)
        print(reference_pointer_table[ref])

    return reference_pointer_table

query = 'ATGCTGGG'
# query =   'AAAAAAAA'
# query =   'AATGAAAT'
reference1 = "ATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATGGG"
reference1 = "ATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATG"
# reference1 = "ATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATGATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATGATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATGATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATG"
# reference1 =   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
# reference2 = "CGTAGCTATGCTGGGTTAGCGATATGCTGGGCCGTAATGCTGGGAGCTTACGATCGTAGCTAGCTACATGCT"
# reference3 = "CAAGTGTTGGAAATAGAGTCTTGAAAGAATTTACGATGTTTTAGAACCAA \
# AACTTGCCCCCTTGAAAGCGTCTGCTAGCATATTTCCGTTTGAACCTGTT\
# CATTGTATGTTCTGTTGTAATTGCTGCTTATGTTTTTAGGCATCTTTAGT\
# TTAGATGATCTCCAAAGGCCCTCCCCTCACCTAAATTGACCTTAATTAAC"

k = 4    # seed length
b =  12  # bin width 
h =   8  # threshold
# k = 4    # seed length
# b =  24  # bin width 
# h =   6  # threshold
Nb = len(reference1)//b # number of bins 72/12 = 6
# references = [reference1, reference2]
references = [reference1]
reference_pointer_table = {}
reference_pointer_table = Construct_Seed_Pointer_Table(references, k)

bin_store = {}

def SeedLookup(reference, seed):
    return reference_pointer_table.get(reference, {}).get(seed, [])

def d_soft(reference, query, Nb, k, b):
    """
    This d_soft performs the hit lookup and stores it by bins
    to be used by the TinyGPU.
    """
    # for j in start : stride : end do
    start = 0
    end = len(query) - k + 1
    stride = 1
    print(f"start {start} : end {end}")
    for j in range(start, end, stride):
        # seed ← Q[j : j + k];
        seed = query[ j : j + k]

        # hits ← SeedLookup(R,seed) ;
        hits = SeedLookup(reference, seed)
        print(f"hits are  {hits} for seed {seed} and j {j}")

        # for i in hits do
        for i in hits:
            if (i >= j):
                # bin ← ⌈(i − j)/B⌉ ;
                bin = (i - j) // b
                bin_store.setdefault(bin, []).append((i, j))
                print(f"bin is {bin} for i {i} and j {j}")

    return bin_store

def gpu_stuff(bin_store):
    """
    This function performs the overlap threshold computation
    that will be done on the TinyGPU. 
    """
    # candidate_pos ← [] ;
    candidate_pos = []

    # last_hit_pos ← [−k for i in range(NB)] ;
    last_hit_pos = -k

    # bp_count ← [0 for i in range(NB)] ;
    bp_count = 0

    for item in bin_store: # item is (i, j)
        print(item)
        i = item[0]
        j = item[1]

        # overlap ← max(0,last_hit_pos[bin] + k − j);
        overlap = max(0, last_hit_pos + k - j)
        print(f"overlap {overlap}")
        # last_hit_pos[bin] ← j;
        last_hit_pos = j
        print(f"last_hit_pos {last_hit_pos}")
        # bp_count[bin] ← bp_count[bin] + k − overlap ;
        bp_count = bp_count + k - overlap
        print(f"bp_count {bp_count}")
        # if (h + k − overlap > bp_count[bin] ≥ h) then
        if ((h + k - overlap > bp_count) and (bp_count >= h)):
            # candidate_pos.append(< i, j >) ;
            candidate_pos.append((i, j))
            return candidate_pos

    return candidate_pos

def memory_helper(bin_store):
    """
    This function returns data as expected by the GPU.
    It is a helper function to avoid hand-writing the data memory from scratch.
    """
    size_start_data = []
    data = []
    # first item in list is the number of bins
    dict_size = len(bin_store)
    size_start_data.append(dict_size)
    i = 0
    prev_size = 0
    prev_start = 0
    for key in bin_store:
        # store the size of the list
        size_start_data.append(len(bin_store[key]) * 2)
        if i == 0:
            prev_size = len(bin_store[key]) * 2
            prev_start = 2*dict_size + 1
            size_start_data.append(2*dict_size + 1)
        else:
            next_start = prev_start + prev_size
            size_start_data.append(next_start)
            prev_size = len(bin_store[key]) * 2
            prev_start = next_start
        i += 1
        for list_item in bin_store[key]:
            # store the data values in the bin
            data.append(list_item[0])
            data.append(list_item[1])
    for list_item in data:
        size_start_data.append(list_item)
    print("memory_helper")
    print(size_start_data)



bin_store = d_soft(reference1, query, Nb, k, b)
# bin_store = d_soft(reference3, query, Nb, k, b)
print(f"bin store: {bin_store}")
memory_helper(bin_store)
candidates = []
for bin_num in bin_store:
    candidates.append(gpu_stuff(bin_store[bin_num]))
# candidates.append(gpu_stuff(bin_store[1]))

print(f"found {len(candidates)} candiates")   
print(f"candidates {candidates}")
for candidate_list in candidates:
    for candidate in candidate_list:
        print(f"candidate: {candidate}")


