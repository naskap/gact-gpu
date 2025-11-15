# D-Soft Implementation Today

Today we implemented the **d-soft** algorithm in three stages:

1. **Python** – wrote the initial version for correctness and easy debugging.
2. **C** – translated Python code for faster execution and static memory use.
3. **Assembly** – used the -S option to compile the c into assembly. Discovered that pure assembly is actually pretty crazy to write.

The algorithm identifies candidate positions in a reference sequence for a query based on seed hits and bin-level counting.  

Right now, we are thinking of having the SeedPosition table automatically generated in a separate memory by a python helper function. 

We are thinking of hardcoding k as 3 or 4. 
Defining some params:
AAA = 0
AAG = 1
....
TTT = 63
For each reference, we would store the candidate positions in memory as a 2d array in verilog: 
SeedPointerTable = 
[
    [0, 34, 56], # AAA has hits in reference positions 0, 34, 56
    [21, 4, 59], # AAG has hits in reference positions 21, 4, 59
    [17, 28],
    ....
]

This would simplify the lookup of the data as SeedPointerTable[seed] where seed is a combination of bases such as ATG. Each thread within a core would have a different reference. 

Right now, the inner loop looks like: 

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


We think the best thread level parallelism would be to loop by bin, but ngl its hard. We are going to implement bin-level parallelism in Python and then try to map it onto hw. 