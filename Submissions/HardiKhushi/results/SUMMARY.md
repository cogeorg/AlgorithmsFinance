# Measured findings

Run `20261120T145013469725Z`; source SHA-256 `c2b486377bb6f569785d1167e9a3bb05f80b5920706ac19837d7c0e71d00ef01`.

36 workloads, 216 method/version configurations. 5 repeats per timing phase and memory case.

## Revision comparison across saved workloads

Ratios are original median total time / revised median total time. Values above 1 favor the revision. Each workload has equal weight in the median ratio; this is not a confidence interval or a universal speedup.

| Method | Lower revised total median | Median time ratio | Lower revised peak memory |
| --- | --- | --- | --- |
| linear | 34/36 | 1.718x | 36/36 |
| binary | 36/36 | 1.053x | 36/36 |
| set | 36/36 | 1.282x | 36/36 |

## Largest input example: n=100,000, q=100, unique IDs

Time is milliseconds per complete batch, including preparation. Memory is median peak newly traced allocation in KiB, with prepared state and output alive and existing inputs excluded.

| Queries | Method | Original total ms | Revised total ms | Original peak KiB | Revised peak KiB |
| --- | --- | --- | --- | --- | --- |
| all-present | linear | 47.31767 | 23.84804 | 782.09 | 0.84 |
| all-present | binary | 8.14046 | 8.01879 | 1952.96 | 1171.71 |
| all-present | set | 0.88713 | 0.69323 | 6925.46 | 6144.21 |
| all-absent | linear | 47.72613 | 47.45954 | 782.09 | 0.84 |
| all-absent | binary | 8.14588 | 8.00904 | 1952.96 | 1171.71 |
| all-absent | set | 0.90112 | 0.69024 | 6925.46 | 6144.21 |
| mixed | linear | 47.33438 | 36.53125 | 782.09 | 0.84 |
| mixed | binary | 8.24183 | 7.98204 | 1952.96 | 1171.71 |
| mixed | set | 0.88764 | 0.67702 | 6925.46 | 6144.21 |

## Interpretation and limits

Linear search's early exit reduces work on hits; misses still require a full scan. Removing defensive copies reduces newly allocated memory. Binary search retains its sorting cost; set lookups retain the hash-table memory cost. Compare total time when preparation cannot be reused.

Every regression remains in the saved results. A smaller median on a single machine is descriptive evidence, not proof of an improvement on all data. One seed was used, versions ran sequentially, and scheduling, cache warmth, allocator state, and batching overhead can affect ratios.

Preparation, query-only, and total timings are independent measurements; their medians need not add up. Query-only timing reuses prepared state within a timed repeat. Memory tracing is separate and is not process RSS.

See `timing_raw.csv`, `memory_raw.csv`, and `environment.json` for the raw repeats, batching divisors, actual hit rates, settings, and code identity. The dashboard and this report are generated from the saved CSVs; no measurements run when viewing or filtering them.
