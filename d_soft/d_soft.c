#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_SEEDS 1024    // max number of unique seeds per reference
#define MAX_POS   1024    // max positions per seed

typedef struct {
    char seed[5];          // k=4 + null terminator
    int positions[MAX_POS];
    int count;
} SeedEntry;

typedef struct {
    char *reference;
    SeedEntry seeds[MAX_SEEDS];
    int seed_count;
} ReferenceTable;

// Construct_Seed_Pointer_Table
ReferenceTable Construct_Seed_Pointer_Table(char *references[], int num_refs, int k) {
    /*
    Build a seed pointer table mapping each k-length substring (seed)
    in each reference to the list of positions where it occurs.
    Used by SeedLookup for fast sequence alignment.

    Parameters:
        references (list of str): Reference sequences
        k (int): Seed length

    Returns:
        dict: {reference: {seed: [positions]}}
    */

    ReferenceTable table;
    table.reference = references[0]; // only storing first reference for simplicity
    table.seed_count = 0;

    for (int i = 0; i <= strlen(table.reference) - k; i++) {
        char key[5];
        strncpy(key, &table.reference[i], k);
        key[k] = '\0';

        // check if seed exists
        int found = 0;
        for (int s = 0; s < table.seed_count; s++) {
            if (strcmp(table.seeds[s].seed, key) == 0) {
                table.seeds[s].positions[table.seeds[s].count++] = i;
                found = 1;
                break;
            }
        }

        if (!found) {
            strcpy(table.seeds[table.seed_count].seed, key);
            table.seeds[table.seed_count].positions[0] = i;
            table.seeds[table.seed_count].count = 1;
            table.seed_count++;
        }
    }

    // print seeds and positions
    for (int s = 0; s < table.seed_count; s++) {
        printf("seed: %s -> positions: ", table.seeds[s].seed);
        for (int p = 0; p < table.seeds[s].count; p++) {
            printf("%d ", table.seeds[s].positions[p]);
        }
        printf("\n");
    }

    return table;
}

// SeedLookup
int* SeedLookup(ReferenceTable *table, char *seed, int *out_count) {
    return_val: NULL;
    for (int s = 0; s < table->seed_count; s++) {
        if (strcmp(table->seeds[s].seed, seed) == 0) {
            *out_count = table->seeds[s].count;
            return table->seeds[s].positions;
        }
    }
    *out_count = 0;
    return NULL;
}

// d_soft
void d_soft(ReferenceTable *table, char *query, int Nb, int k, int b, int h) {
    // candidate_pos ← [] ;
    int candidate_pos[1024][2];
    int candidate_count = 0;

    // last_hit_pos ← [−k for i in range(NB)] ;
    int last_hit_pos[Nb];
    for (int i = 0; i < Nb; i++) last_hit_pos[i] = -k;

    // bp_count ← [0 for i in range(NB)] ;
    int bp_count[Nb];
    for (int i = 0; i < Nb; i++) bp_count[i] = 0;

    // for j in start : stride : end do
    int start = 0;
    int end = strlen(query) - k + 1;
    int stride = 1;
    printf("start %d : end %d\n", start, end);

    for (int j = start; j < end; j += stride) {
        // seed ← Q[j : j + k];
        char seed[5];
        strncpy(seed, &query[j], k);
        seed[k] = '\0';

        // hits ← SeedLookup(R,seed) ;
        int hit_count;
        int *hits = SeedLookup(table, seed, &hit_count);
        printf("hits are ");
        for (int hi = 0; hi < hit_count; hi++) {
            printf("%d ", hits[hi]);
        }
        printf("for seed %s and j %d\n", seed, j);

        // for i in hits do
        for (int hi = 0; hi < hit_count; hi++) {
            int i_ref = hits[hi];
            if (i_ref >= j) {
                // bin ← ⌈(i − j)/B⌉ ;
                int bin = (i_ref - j) / b;
                if (bin >= Nb) bin = Nb - 1;
                if (bin < 0) bin = 0;
                printf("bin is %d for i %d and j %d\n", bin, i_ref, j);

                // overlap ← max(0,last_hit_pos[bin] + k − j);
                int overlap = last_hit_pos[bin] + k - j;
                if (overlap < 0) overlap = 0;

                // last_hit_pos[bin] ← j;
                last_hit_pos[bin] = j;

                // bp_count[bin] ← bp_count[bin] + k − overlap ;
                bp_count[bin] += k - overlap;

                // if (h + k − overlap > bp_count[bin] ≥ h) then
                if ((bp_count[bin] >= h) && (bp_count[bin] < h + k - overlap)) {
                    // candidate_pos.append(< i, j >) ;
                    candidate_pos[candidate_count][0] = i_ref;
                    candidate_pos[candidate_count][1] = j;
                    candidate_count++;
                }
            }
        }
    }

    printf("found %d candidates\n", candidate_count);
    for (int c = 0; c < candidate_count; c++) {
        printf("candidate: (%d, %d)\n", candidate_pos[c][0], candidate_pos[c][1]);
    }
}

int main() {
    char *query = "ATGCTGGG";
    char *reference1 = "ATGCTGGGACGTAGCTATGCTGGGTTACGATCGATGCTGGGCCGTAAGCTTAGGCTAGCTAGCTGACATGGG";
    char *reference2 = "CGTAGCTATGCTGGGTTAGCGATATGCTGGGCCGTAATGCTGGGAGCTTACGATCGTAGCTAGCTACATGCT";

    int k = 4;    // seed length
    int b = 12;   // bin width
    int h = 8;    // threshold
    int Nb = strlen(reference1)/b; // number of bins

    char *references[] = {reference1, reference2};
    ReferenceTable table = Construct_Seed_Pointer_Table(references, 2, k);

    d_soft(&table, query, Nb, k, b, h);

    return 0;
}
