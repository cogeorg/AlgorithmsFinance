# Revision: original (v1) vs. revised (v2)

Code: [`membership/original.py`](../membership/original.py) (v1, unchanged since Step 5)
and [`membership/revised.py`](../membership/revised.py) (v2). Both stay in the
repository side by side (LAB_SPEC.md R5).

## 1. What changed

| Method | v1 (original) | v2 (revised) | Changed? |
|---|---|---|---|
| linear | scan per query, early exit | same function, re-exported | no (decision Q4) |
| hash | `set(ids)`, `x in s` | same function, re-exported | no (decision Q4) |
| binary, prepare | `sorted(ids)` copy | `sorted(ids)` copy | no |
| binary, query | recursive, slices the list at each step | iterative lower-bound search on index bounds, inlined in the query loop | **yes** |

Changes to binary search query, in detail:

1. **Removed the unnecessary copies.** v1 calls itself on `arr[:mid]` or `arr[mid+1:]`.
   Every slice copies up to half of the current list, about n/2 + n/4 + ... < n
   elements per query. v2 keeps two indices `lo`, `hi` into the one sorted copy and
   copies nothing.
2. **Recursion replaced by a loop.** No function call per step and no recursion depth
   (v1 needs about log2(n) + 1 nested calls).
3. **No function call per query.** The search loop is written directly inside the loop
   over the queries.
4. **Lower-bound form.** One `<` comparison per step, then one `==` at the end, instead
   of up to two comparisons (`==`, then `<`) per step.

Copy that was **not** removed: the sorted copy in `binary_prepare`. It is required.
Sorting in place (`ids.sort()`) would change the caller's array and break F4.

## 2. Why

- v1's slicing makes one query cost O(n) time and O(n) temporary memory, although the
  comparisons are only O(log n). Binary search loses its point: with slicing, a query
  costs about as much as a linear scan, plus the sorting.
- Recursion costs a Python function call per step and depends on the recursion limit.
  For our n this is not a correctness problem (depth 18 at n = 100,000), only a speed one.
- Laurin's goal (decision Q3): the fastest correct binary search. Two iterative
  candidates were written and both tested; the faster one was chosen by measurement.

## 3. Correctness evidence

- Both v2 candidates (`binary_query_classic`, `binary_query_lower_bound`) and the
  registered v2 pass the full shared test suite. Nothing was weakened.
- New tests added in Step 6 (R4), run for **every** method and version:
  - `test_step6_boundary_cases`: query above a duplicated maximum (lower bound ends at
    `lo == n` and must not read `state[n]`), below a duplicated minimum (classic ends with
    `hi == -1`), inside and next to a run of duplicates, a single element, lengths 16 and 15.
  - `test_exhaustive_small_arrays`: every array of length 0..5 over {0, 1, 2}
    (364 arrays) with queries -1..3, checked against a `set` oracle.
- Result: 578 passed, 0 failed (Step 6). Passing tests are evidence, not proof (R7).

Invariant of the chosen v2 (lower bound): `state[:lo]` < x and `state[hi:]` >= x.
Start `lo = 0`, `hi = n`. Each step keeps the invariant and shrinks `hi - lo`.
At the end `lo == hi` is the first index with a value >= x, so x is present
if and only if `lo < n and state[lo] == x`.

## 4. Choosing between the two v2 candidates

Script: `python -m bench.binary_variants`.
Raw data: `results/raw/binary_variants_20261120T143025Z.csv`, environment in
`..._env.json` (seed 20261120, duplicate policy "allow", q = 100, 5 repeats after
a warm-up, k calls per timed block recorded, fresh sorted copy per repeat).
Note: run on an uncommitted working tree (`git_dirty = true`).

Median query-batch time, divided by q = 100 to give **microseconds per query**:

| n | hit rate | v1 recursive + slicing | v2 classic | v2 lower bound |
|---:|---:|---:|---:|---:|
| 1,000 | 1.0 | 4.89 | 1.93 | **1.38** |
| 1,000 | 0.0 | 5.04 | 1.79 | **1.36** |
| 1,000 | 0.5 | 5.08 | 1.46 | **1.42** |
| 10,000 | 1.0 | 28.83 | 1.98 | **1.91** |
| 10,000 | 0.0 | 30.25 | 2.12 | **1.86** |
| 10,000 | 0.5 | 30.32 | 2.09 | **1.75** |
| 100,000 | 1.0 | 759.72 | 2.60 | **2.46** |
| 100,000 | 0.0 | 452.54 | 2.94 | **2.33** |
| 100,000 | 0.5 | 438.29 | 2.62 | **2.52** |

Interpretation:
- **Lower bound has the lower median in all 9 cells.** The gap is clear for absent and
  mixed queries (about 5-20%). For all-present queries the raw repeats overlap
  (for example n = 1,000: classic 1.30-2.78 us, lower bound 1.32-1.76 us), so there it is
  roughly a tie: classic can stop early on a hit, but pays two comparisons per step.
- **Decision:** `binary_query = binary_query_lower_bound`. The classic variant stays in
  the code and in the tests for comparison.

## 5. Measured effect of the revision (v1 vs. v2), first measurement

- v1 grows roughly linearly with n per query (about 5 → 30 → 450-760 us), as predicted
  by the O(n) copying. v2 grows only slightly (about 1.4 → 1.8 → 2.4 us), as predicted
  by O(log n): log2(1,000) ≈ 10, log2(100,000) ≈ 17.
- Speed-up of the query batch at n = 100,000: about **170-310x**.
- Preparation (`sorted`) is identical in v1 and v2, so the total-time gain is smaller
  when sorting dominates (q = 1). This is measured in Step 7.
- Open observation: v1 at n = 100,000 with hit rate 1.0 (760 us) is slower than with
  0.0 (450 us), although hits can stop early. Resolved in Step 7, see section 6.

## 6. Measured effect in the full benchmark (Step 7)

Script: `python -m bench.timing`. **Official run:** `results/raw/timing_20261120T144207Z*`,
commit `42ecde7`, `git_dirty = false`. (An earlier development run,
`timing_20261120T143759Z*`, was made on an uncommitted tree, `git_dirty = true`; it is kept
for transparency and gives the same picture.) Medians of 5 repeats, unit: seconds,
"query batch" = all q queries together. Preparation is the same `sorted(ids)` in both versions.

| n | q | hit | v1 prep | v1 query batch | v1 total | v2 prep | v2 query batch | v2 total |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 100 | 0.5 | 4.3e-5 | 5.2e-4 | 5.3e-4 | 4.6e-5 | 1.6e-4 | 2.2e-4 |
| 10,000 | 100 | 0.5 | 1.9e-3 | 2.9e-3 | 5.6e-3 | 2.1e-3 | 2.1e-4 | 2.2e-3 |
| 100,000 | 100 | 0.5 | 2.8e-2 | 4.9e-2 | 7.6e-2 | 2.9e-2 | 2.5e-4 | 2.8e-2 |
| 100,000 | 1 | 0.5 | 2.7e-2 | 6.0e-4 | 2.6e-2 | 2.8e-2 | 2.2e-6 | 2.8e-2 |

- **Query batch:** v2 is about 3x (n = 1,000) to about 190x (n = 100,000) faster.
  This matches O(n) per query for v1 (copying) against O(log n) for v2.
- **Total:** with q = 100 the gain is about 2.4-2.7x, because sorting is not changed by
  the revision and is most of v2's total time. With q = 1 the revision makes no
  measurable difference in total time: one query is tiny next to the O(n log n) sort
  (the q = 1 totals of v1 and v2 differ in both directions, within noise).
- **Correctness:** unchanged; the benchmark checks every result against a `set` oracle.

### Noise level: an A/A comparison for free

Linear search and hash set are *the same code* in v1 and v2 (decision Q4), so any
difference between their two measurements is pure noise. In this run they differ by
typically 5-15%, in single cells up to about 25%. Differences of that size between
different methods should not be interpreted.

### The v1 hit-vs-miss puzzle (section 5), resolved

v1 at n = 100,000, q = 100 showed a higher median for hit rate 1.0 than for 0.0 in all
three runs (Step 6, development run, official run), with large scatter (official run,
hit rate 1.0: 0.051-0.132 s). A focused experiment with 30 interleaved repeats of the
same query batches (not saved as a result file; method: GC off, `perf_counter`)
gave medians of 47.4 ms (hits) vs. 49.6 ms (misses), equal minima (40.2 vs. 40.5 ms)
and outliers around 100 ms in both groups. So there is **no real difference**: with 5
repeats, a few slow outliers can move the median. In theory, v1 hits and misses copy
almost the same amount: the first slices (n/2 + n/4 + ...) dominate, and a hit stops
on average only 2.4 recursion levels earlier (14.3 vs. 16.7), where the slices are
tiny. Lesson: look at the raw repeats before explaining a difference between medians.

## 7. Memory effect of the revision (Step 8)

Script: `python -m bench.memory` (tracemalloc, separate from timing). Input is never
counted; "prepare" counts the prepared structure, "query" the output plus temporaries,
"total" both. Values in KiB (1 KiB = 1,024 bytes), n = 100,000, q = 100, hit rate 0.5.
tracemalloc values are deterministic here (0 bytes spread between 3 repeats).
Official result file: `results/memory/memory_20261120T144911Z*` (commit `8b10cd7`,
`git_dirty = false`).

| phase | measure | binary v1 | binary v2 | linear | hash |
|---|---|---:|---:|---:|---:|
| prepare | current | 781.2 | 781.2 | 0.0 | 4,096.2 |
| prepare | peak | 1,171.8 | 1,171.8 | 0.0 | 6,144.3 |
| query | peak | **782.3** | **1.1** | 0.9 | 0.9 |
| total | peak | **1,563.5** | **1,171.8** | 0.9 | 6,144.3 |

- **Query peak: v1 782 KiB vs. v2 1.1 KiB.** v1's slices along one recursion path are all
  alive at the same time: n/2 + n/4 + ... ≈ n references × 8 bytes ≈ 781 KiB, i.e. O(n)
  extra memory per query. v2 needs O(1) besides the output list (100 × 8 bytes + 56 ≈ 0.9 KiB).
- **Total peak: −25%** (1,563 → 1,172 KiB). What remains is the sort itself.
- **Prepare is unchanged** by the revision: the sorted copy is 8n bytes + 56 (781 KiB);
  its peak of 1.5× comes from the temporary merge buffer of Python's sort (Timsort, up to
  n/2 references).
- For comparison: the hash set needs about 5x the sorted list (4 MiB for about 79,000
  distinct IDs: a hash table of 2^18 slots × 16 bytes) and peaks at 6 MiB while it resizes
  (old and new table alive together). Linear search needs no extra memory at all.
