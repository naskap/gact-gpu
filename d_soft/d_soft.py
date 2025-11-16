
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

# query = 'ATGCTGGG'
query =   'AAAAAAAA'
# reference1 = "ATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATGGG"
reference1 =   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
reference2 = "CGTAGCTATGCTGGGTTAGCGATATGCTGGGCCGTAATGCTGGGAGCTTACGATCGTAGCTAGCTACATGCT"

k = 4    # seed length
b =  12  # bin width 
h =   8  # threshold
Nb = len(reference1)//b # number of bins 72/12 = 6
references = [reference1, reference2]
reference_pointer_table = {}
reference_pointer_table = Construct_Seed_Pointer_Table(references, k)


def SeedLookup(reference, seed):
    return reference_pointer_table.get(reference, {}).get(seed, [])


def d_soft(reference, query, Nb, k, b):
    # candidate_pos ← [] ;
    candidate_pos = []

    # last_hit_pos ← [−k for i in range(NB)] ;
    last_hit_pos = [-k] * Nb

    # bp_count ← [0 for i in range(NB)] ;
    bp_count = [0] * Nb

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
                print(f"bin is {bin} for i {i} and j {j}")

                # overlap ← max(0,last_hit_pos[bin] + k − j);
                overlap = max(0, last_hit_pos[bin] + k - j)

                # last_hit_pos[bin] ← j;
                last_hit_pos[bin] = j

                # bp_count[bin] ← bp_count[bin] + k − overlap ;
                bp_count[bin] = bp_count[bin] + k - overlap

                # if (h + k − overlap > bp_count[bin] ≥ h) then
                if ((h + k - overlap > bp_count[bin]) and (bp_count[bin] >= h)):
                    # candidate_pos.append(< i, j >) ;
                    candidate_pos.append((i, j))

    print(f"found {len(candidate_pos)} candiates")
    for candidate in candidate_pos:
        print(f"candidate: {candidate}")

d_soft(reference1, query, Nb, k, b)