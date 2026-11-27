# Membership Search Implementation and Performance Report

**Student:** Liu Haina  
**Course:** Algorithms in Finance  
**Experiment date:** 20 November 2026  
**Scope:** Phase 1 implementation, correctness checks, revision, and performance evaluation

The three methods solve the same integer membership problem while preserving the input array and query order. In this experiment, the revised hash-set method had the lowest total time in 9 of 9 tested configurations with 100 queries. For one query, linear search had the lowest total in 5 of 6 configurations and avoided preparation. The revision removed unnecessary sorting and set construction for empty query batches; nonempty-workload comparisons are evaluated below.

## Task and implementations

Each public function accepts an integer ID list and an ordered query list, returning one Python Boolean per query. For example, IDs `[7, 11, 7]` and queries `[11, 9, 7]` must produce `[True, False, True]` without changing the ID list.

Linear search explicitly scans the array until it finds the current query or exhausts the array. Binary search creates a sorted copy with `sorted(array)` and uses a handwritten iterative search. Hash-set membership constructs a standard-library `set` and evaluates membership for each query. Both search procedures are implemented directly in Python.

For nonempty inputs, the expected resource tradeoffs are:

| Method | Preparation | Complete query batch | Additional prepared storage |
| --- | --- | --- | --- |
| Linear search | O(1) | O(nq) worst case | O(1) |
| Binary search | O(n log n) worst case | O(q log n) | O(n) |
| Hash set | Expected O(n) | Expected O(q) | O(u), for u distinct IDs |

All methods also allocate the required O(q) output. Hash-set bounds assume well-distributed hashes and are not worst-case guarantees. The storage column excludes required output and given input; the traced-memory measurements below have a different, explicitly stated scope.

## Correctness evidence

The tests were written before implementation using Python's `unittest`. The initial run recorded 39 failing subtests because all three functions were missing. After implementation, the same 13 test methods passed for each version, with each test applied to all three methods. The expected results were not weakened.

The suite checks empty arrays and queries, a single entry, duplicates, unsorted inputs, first and last matches, gaps and absent values, negative and large integers, Boolean output types, query order, unchanged input, and repeated calls without stale state. The staged versions and both pre-refactoring snapshots pass the same suite. Separately, all 18 saved input cases were checked against independently computed set-membership answers for both versions and three methods, giving 108 successful end-to-end validations. The benchmark also checks stage results before timing. These checks provide evidence rather than a proof of correctness.

Evidence files are `test_baseline.txt`, `test_implementation.txt`, `test_revision.txt`, `test_stages.txt`, and `data_validation.txt`.

## Synthetic inputs and experiment design

The generator uses base seed 42 and Python's `random.Random`. The same saved array and ordered query values are supplied to every method and version. Array entries are drawn uniformly with replacement from `range(n//2)`, producing the following saved arrays:

| Array length n | Distinct IDs | Duplicate entries beyond first occurrences |
| --- | --- | --- |
| 1,000 | 431 | 569 |
| 10,000 | 4,308 | 5,692 |
| 100,000 | 43,230 | 56,770 |

The required feasible workload consists of n in {1,000, 10,000, 100,000}, q in {1, 100}, and all-present, all-absent, or mixed queries. Mixed batches contain exactly 50 hits and 50 misses. A single query cannot contain both a hit and a miss, so the three q = 1 mixed combinations are explicitly recorded as infeasible rather than reported as mixed observations. This leaves 15 main cases. Three supplementary q = 0 cases assess the revision, giving 18 cases and 108 method/version configurations.

Hit queries sample existing array positions with replacement, making frequent IDs more likely to be queried. Misses are sampled from negative integers while arrays contain only nonnegative IDs; query order is shuffled. This guarantees the intended hit rates, but the misses are outside the array's value range and do not represent every possible search difficulty. `data/inputs.json` records the values, seeds, generation policy, actual hit counts, distinct counts, expected answers, and array hashes. Empty batches have an undefined hit rate recorded as null.

## Measurement protocol

The measurement environment was CPython 3.13.0 on `macOS-15.7.3-arm64-arm-64bit-Mach-O`, with 8 logical CPU cores. No container was used. The benchmark measured the staged `search_original.py` and `search.py` sources identified by SHA-256 hashes in `results/metadata.json`. The recorded repository HEAD is `09efedda0e067b50ce3af070a3691c644eb3e9b9`; local measured files may be uncommitted, so that HEAD alone does not identify the full measured implementation.

Timing uses `time.perf_counter()`. Each metric receives an untimed warm-up and calibration, followed by five recorded repeats. Short operations are grouped toward 3 ms, capped at 8,192 calls, and divided by the call count. The reported statistic is the median elapsed seconds per complete query batch, not per individual query. Tables below convert these medians to milliseconds.

Preparation calls the actual `prepare_*` function, including sorting, set construction, or revised early checks. Query-batch timing calls the actual `query_*` function after preparation; each recorded repeat receives fresh state, reused read-only within its group. Total timing independently invokes the public function with fresh preparation on every call. The metrics are separate experiments, so their medians need not add exactly. Configuration order is shuffled with seed 2026, while the five repeats for each metric run consecutively.

Input loading, generation, copying, validation, printing, memory tracing, profiling, and dashboard rendering are excluded from timed regions. Loop and function-call overhead and release of previous grouped results remain included. The final result remains alive until the timer stops. For phase separation, both versions expose preparation/query helpers; pre-refactoring sources remain under `snapshots/`. The extra helper calls can affect very short operations, and the tables describe the staged implementations.

Memory is measured after all timing using a fresh `tracemalloc` run per configuration. Inputs exist before tracing and are excluded. Preparation and query execution are included, with prepared state and output kept alive at reading. Current and peak values represent traced Python allocations, not total process RSS, all native allocations, or auxiliary space alone. Each configuration has one memory observation. KiB means 1,024 bytes.

## Runtime results

### Preparation cost changes the comparison

For the revised implementation with n = 100,000, q = 100, and 50% hits:

| Method | Preparation (ms) | Query batch (ms) | Total (ms) |
| --- | --- | --- | --- |
| Linear search | 0.000053 | 62.773542 | 61.841333 |
| Binary search | 10.521542 | 0.117116 | 9.835375 |
| Hash set | 1.454375 | 0.001686 | 1.486927 |

Hash-set membership has a low query-batch cost, but constructing the set still costs time. Binary search also answers the batch much faster than linear scanning once prepared, but sorting dominates its total for this workload. Excluding preparation would therefore give an incomplete comparison of independent calls.

### Workload size and hit rate

Revised total times for q = 100 and 50% hits are:

| n | Linear search (ms) | Binary search (ms) | Hash set (ms) |
| --- | --- | --- | --- |
| 1,000 | 0.713599 | 0.104204 | 0.008426 |
| 10,000 | 5.961500 | 0.875250 | 0.111876 |
| 100,000 | 61.841333 | 9.835375 | 1.486927 |

Hash sets had the lowest revised total time in 9 of 9 tested q = 100 cases across sizes and hit scenarios. For example, at n = 100,000 with mixed queries, its total was 1.486927 ms, compared with 9.835375 ms for binary search and 61.841333 ms for linear search. These observations apply to the saved workloads and this machine; they do not establish a universal crossover point.

For q = 1, preparation can outweigh a faster membership operation:

| n | Scenario | Linear search (ms) | Binary search (ms) | Hash set (ms) |
| --- | --- | --- | --- | --- |
| 1,000 | all present | 0.006470 | 0.040641 | 0.006833 |
| 1,000 | all absent | 0.010981 | 0.040278 | 0.007025 |
| 10,000 | all present | 0.011927 | 0.807906 | 0.116220 |
| 10,000 | all absent | 0.095010 | 0.849563 | 0.105779 |
| 100,000 | all present | 0.720667 | 9.815625 | 1.453677 |
| 100,000 | all absent | 0.915656 | 9.693750 | 1.446385 |

Linear search had the lowest revised total in 5 of 6 single-query cases. Other winners were n = 1,000, all absent: Hash set. Comparisons depend on preparation cost, query position, and measurement overhead. One sampled query per hit scenario is insufficient to characterize all single-query behavior.

At n = 100,000 and q = 100, revised totals vary with the hit scenario:

| Scenario | Linear search (ms) | Binary search (ms) | Hash set (ms) |
| --- | --- | --- | --- |
| all present | 26.219834 | 9.669291 | 1.532021 |
| mixed | 61.841333 | 9.835375 | 1.486927 |
| all absent | 93.532083 | 9.804334 | 1.534458 |

Linear search can stop early for present IDs, whereas every absent query scans the entire array. Its total therefore rises from the all-present to mixed to all-absent workload. Binary-search and hash-set totals change much less because their preparation costs dominate at this batch size.

## Revision results

The revision adds an empty-input check before preparation. With zero queries, the revised version skips sorting and set construction. With an empty array, it constructs the required all-false output directly. In the measured staged implementation, preparation returns a `None` state for these cases and the query phase constructs the output; the public interface remains unchanged.

For the main example n = 100,000, q = 100, and mixed queries:

| Method | Original total (ms) | Revised total (ms) | Original / Revised |
| --- | --- | --- | --- |
| Linear search | 62.822333 | 61.841333 | 1.016x |
| Binary search | 9.664916 | 9.835375 | 0.983x |
| Hash set | 1.511406 | 1.486927 | 1.016x |

Across the 45 main method/workload comparisons, Original / Revised ranges from 0.853x to 1.150x, with a descriptive median of 1.006x. Values occur on both sides of 1. The search logic for nonempty inputs is unchanged apart from extra checks, so this run does not support a consistent improvement for the required nonempty workloads. The pooled ratio is descriptive, not a statistical significance test.

The targeted supplementary empty-query cases show a different result:

| n | Method | Original total (ms) | Revised total (ms) | Original peak (KiB) | Revised peak (KiB) |
| --- | --- | --- | --- | --- | --- |
| 1,000 | Binary search | 0.037842 | 0.0001216 | 11.842 | 0.176 |
| 1,000 | Hash set | 0.007427 | 0.0001158 | 40.320 | 0.178 |
| 10,000 | Binary search | 0.720120 | 0.0001185 | 117.357 | 0.176 |
| 10,000 | Hash set | 0.106526 | 0.0001191 | 160.320 | 0.178 |
| 100,000 | Binary search | 10.234500 | 0.0001187 | 1171.896 | 0.176 |
| 100,000 | Hash set | 1.469573 | 0.0001150 | 2560.320 | 0.178 |

Here the original binary-search and hash-set versions still prepare unused structures. The revision removes this work and its large allocation peaks. Revised timings are sub-microsecond and strongly affected by wrapper/loop overhead, so the important conclusion is that the O(n log n) sorting or expected O(n) set-building work is avoided, rather than a precise large speedup factor. Original linear search already performs almost no work for zero queries; adding checks does not provide the same benefit. Empty-array behavior is covered by correctness tests but was not separately benchmarked.

## Memory results

For n = 100,000, q = 100, and mixed queries:

| Method | Version | Current traced (KiB) | Peak traced (KiB) |
| --- | --- | --- | --- |
| Linear search | Original | 0.957 | 1.051 |
| Linear search | Revised | 0.957 | 1.051 |
| Binary search | Original | 782.322 | 1171.896 |
| Binary search | Revised | 782.322 | 1171.896 |
| Hash set | Original | 2049.232 | 2560.320 |
| Hash set | Revised | 2049.170 | 2560.320 |

Linear search retains only small new working objects and the required output. Binary search allocates a sorted list of references plus sorting workspace; existing integer objects belong to the pre-existing input and are not newly traced. The set representation has a larger peak for this saved input, containing 43,230 distinct IDs. The original and revised versions retain the same kinds of preparation structures for this nonempty example. The revision's substantial memory benefit occurs when those structures can be skipped, as shown in the empty-query table.

## Reproduction and dashboard

From the repository root, run:

```bash
cd Submissions/LiuHaina
python3 -B run_tests.py
python3 -B validate_data.py
python3 -B dashboard.py
```

Open `dashboard.html` in a browser. It displays the saved measurements with filters, three timing charts, original/revised comparisons, memory tables, raw repeats, downloads, and environment details. It does not rerun algorithms when filters change. `dashboard_validation.txt` records successful checks of 54 filter/unit combinations, CSV downloading, offline behavior, and desktop/mobile layouts.

To regenerate inputs and measurements, then refresh the dashboard and report:

```bash
python3 -B generate_data.py --seed 42 --include-empty-queries
python3 -B validate_data.py
python3 -B benchmark.py
python3 -B dashboard.py
python3 -B build_report.py
```

These commands use Python's standard library; the dashboard uses browser-native HTML, CSS, SVG, and JavaScript. Regeneration overwrites default input/result files. Fixed seeds reproduce saved input values in the recorded environment, while timings naturally vary. `build_report.py` reads saved results, checks consistency and source hashes, and writes this report without benchmarking. Its checked tables are also exported in `results/report_tables.json`.

## Limitations and conclusions

This is one machine, one interpreter, one base seed, and one array per size. Five repeats assess local timing variation, not variation across machines, seeds, or data distributions. Array generation deliberately includes duplicates, hit sampling favors frequent IDs, and negative misses are all below the stored domain. Broader generalization would require additional seeds, duplicate policies, in-range absent values, and query patterns.

Consecutive repeats, background load, garbage collection, and grouped state reuse can affect timings. In particular, the reused preparation in query-only groups does not represent independently preparing each query batch; the independently measured total captures fresh preparation per call. Very short operations are sensitive to harness overhead. Memory has one traced observation per configuration and excludes pre-existing inputs and untracked native allocations. The empty-query cases are supplementary and do not replace the required q = 1 and q = 100 cases.

For these experiments, hash-set membership has the lowest revised total time in 9 of 9 configurations with 100 queries, with a higher traced memory cost in the detailed mixed-query example. Linear search wins 5 of 6 single-query cases and avoids preparation. Binary search provides fast queries after sorting, but sorting a fresh copy on every public call adds substantial cost for the tested batches. The revision preserves tested behavior and removes unnecessary empty-query preparation. Performance conclusions should be read with the version ratios and workload scope above.

## AI assistance and scope

OpenAI Codex drafted the tests, implementations, revision, data generator, measurement scripts, dashboard, documentation, and this report under the user's step-by-step requests. The implementation uses the proposed iterative binary search and empty-input optimization. Validation includes unchanged expected results, independent membership checks, saved raw repeats, source hashes, and browser checks. AI-generated claims were checked against the saved data; no personal accept/correct/reject judgments are attributed to the student. Student review of the code, reasoning, and assistance record remains necessary before submission.

This report covers Phase 1. The independent peer audit and its reproducible bug evidence belong to Phase 2. A final submission commit and audit target have not been created by this report-writing step.

## Evidence files

- `results/timing_raw.csv`, `results/timing_summary.csv`, and `results/memory.csv`: numeric observations behind the tables.
- `results/metadata.json`: environment, timing/memory definitions, seeds, input hash, and measured source hashes.
- `data/inputs.json`: authoritative shared experimental inputs and expected answers.
- `test_search.py` and the saved validation logs: correctness and execution evidence.
- `REVISION.md` and `snapshots/`: revision explanation and preserved earlier sources.
- `dashboard.html`: interactive English presentation of the saved measurements.
