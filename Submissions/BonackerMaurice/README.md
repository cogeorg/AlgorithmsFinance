# Search methods for integer IDs: Phase 1 lab (BonackerMaurice)

This project implements LinearSearch, BinarySearch on a sorted copy, and
hash-set membership under one specification. It includes tests written first,
a seeded synthetic-data generator, timing and memory measurements, and a
Streamlit dashboard for reviewers.

**Commit to be audited:** `3e0a768` (all code, results and the simplified
dashboard; later commits only edit docs). The benchmark run was measured at `8e8109a`. Later commits add results and docs, simplify the dashboard
(`dashboard/` and its smoke test only) and add the large-n script (`explore/`). The measured code (`search_algos/`,
`datagen/`, `benchmarks/`) is identical, which the source fingerprint
`2621865bef6c…` in the dashboard verifies.

**Committed results:** `02_results/20261120-142828_8e8109a/`. The run had a
clean tree, status `complete`, the source unchanged during the run, and 674
tests passed.

## Run it

Use Python 3.13. Run every command from **`01_code/`**:

```bash
cd Submissions/BonackerMaurice/01_code
python -m pip install -r requirements.txt
python -m pytest                           # expected: 674 passed
python -m tests.mutation_check             # expected: 10/10 mutants killed
python -m benchmarks.run                   # tests, timing, memory -> ../02_results/<run_id>/ (about 1-2 min)
python -m streamlit run dashboard/app.py   # http://localhost:8501
```

Optional commands:

```bash
python -m benchmarks.run --quick                                # small grid, about 15 s (gitignored)
python -m datagen.generator --n 1000 --q 100 --scenario mixed   # inspect one dataset
python -m datagen.generator --n 1000 --q 100 --scenario mixed --out data.json
python -m explore.large_n                                       # n up to 10M, about 9 min (see Exploration)
python -m explore.large_n 50000,500000,5000000                  # any array lengths
```

Use `python -m streamlit`, not `streamlit`: on Windows, application-control
policies can block the `streamlit.exe` launcher. No file needs editing to run
the tests, the benchmarks or the dashboard.

## Folder layout

```
00_docs/      DEVLOG.md (process log), REVISIONS.md (v1 -> v2), AI_USAGE.md
01_code/      requirements.txt, pytest.ini, and the Python packages:
  search_algos/   linear.py, binary.py, hashset.py, validation.py, registry.py
  datagen/        generator.py
  benchmarks/     config.py, timing.py, memory.py, environment.py, run.py
  dashboard/      app.py, data.py
  explore/        large_n.py (large-n exploration, not part of the slide grid)
  tests/          test_search.py, test_generator.py, test_benchmarks.py, test_dashboard.py, mutation_check.py
02_results/   saved benchmark runs, one folder per run
AGENTS.md     working instructions for AI agents and collaborators
```

The folders are numbered after the course convention. The Python packages
inside `01_code/` keep plain names, because module names cannot start with a
digit.

## Specification

```python
from search_algos import get_method
get_method("linear")([7, 11, 7], [11, 9, 7])   # [True, False, True]
get_method("binary", "v1")(ids, queries)       # any registered version
```

The contract:

- The input is a sequence of Python `int` IDs (`list`, `tuple` or `range`) plus
  a sequence of `int` queries.
- The output is a new `list` with one `bool` per query, in query order.
- Neither input is modified.
- Invalid input raises `TypeError` identically for every method. Invalid input
  means:
  - not a sequence, or a `str` or `bytes` value
  - `bool` elements, floats and other non-`int` values
  - NumPy integers (pass `array.tolist()` instead)

  Validation is O(n + q). It runs in `Method.__call__` only and is **not**
  part of the timings.

| Method | Version | Preparation | Query (each) | Notes |
|---|---|---|---|---|
| LinearSearch | v1 (original) | `list(ids)` copy, O(n) | O(n) | index-based `while` loop |
| LinearSearch | **v2 (current)** | none, O(1) | O(n) | direct `for` iteration |
| BinarySearch | v1 (original) | `sorted(ids)`, O(n log n) | O(log n) | recursive, early exit |
| BinarySearch | **v2 (current)** | `sorted(ids)`, O(n log n) | O(log n) | iterative lower bound |
| Hash set | **v1 (only)** | `set(ids)`, O(n) expected | O(1) expected | `q in s` |

Both search procedures are implemented by hand. `sorted()` and `set()` are the
allowed library parts. Tests enforce this: an AST check bans `in`, `bisect`,
`.index` and `.count` in the search code, and comparison counting checks that
binary search makes at most O(log n) comparisons per query.

## Revisions

**LinearSearch:** v2 removes an unnecessary defensive copy and replaces the
index loop with direct iteration.

**BinarySearch:** v2 replaces recursion with an iterative lower-bound loop.

Both versions are kept and measured. The details and the numbers are in
[00_docs/REVISIONS.md](00_docs/REVISIONS.md).

## Results at a glance

Run `20261120-142828_8e8109a`, on Windows 11 with Python 3.13.15. Values are
medians of 5 repeats. The full data, environment and spread are in the
dashboard.

| n = 100,000, q = 100, mixed | prepare | query batch | total |
|---|---|---|---|
| LinearSearch v2 | 0.1 µs | 147.8 ms | 157.4 ms |
| BinarySearch v2 | 17.5 ms | 154 µs | 19.3 ms |
| Hash set | 8.5 ms | 2.4 µs | 7.0 ms |

Fitted log–log slopes of the median against n, for q = 100 mixed:

| | prepare | query batch | Expected |
|---|---|---|---|
| Linear v1 / v2 | 1.12 / 0.01 | 1.03 / 0.96 | copy ≈ 1, no work ≈ 0; scan ≈ 1 |
| Binary v1 / v2 | 1.29 / 1.31 | 0.12 / 0.10 | n log n ≈ 1.1; log n ≈ 0.1 |
| Hash | 1.30 | 0.03 | ≈ 1; ≈ 0 |

Reading these results:

- **Linear search vs the others:** for a single batch of 100 queries, linear
  search costs more than binary search plus its sort, which costs more than the
  hash set plus its construction.
- **Prepare slopes above 1:** sorting and set construction come out at about
  1.3 instead of 1–1.1. At n = 100,000 the structures (about 0.8–4 MiB) outgrow
  the CPU caches, so each element costs more at large n.
- **Measurement noise:** binary v1 and v2 share identical `prepare` code, but
  their measured ratio still ranges 0.78–1.27. Differences below about 25%
  between single measurements, such as hash `total` coming out below hash
  `prepare`, are therefore within noise. Compare ratios that hold consistently
  across datasets instead.

## Exploration: up to 10 million IDs

The slide grid stops at n = 100,000. To check that the results hold for much
longer lists, `python -m explore.large_n` reruns the same timing pipeline
(unchanged `benchmarks.timing`, same measured code: source fingerprint
`2621865bef6c…`) on a larger grid:

- n = 100,000, 1,000,000 and 10,000,000
- q = 10, scenarios `all_absent` and `mixed`
- 3 repeats; no memory phase

The run is `02_results/20261120-144435_2611dd1_large_quick/`. It took 9 minutes
and is selectable in the dashboard. Medians per call, `all_absent` (linear
search's worst case):

| | n = 100k | n = 1M | n = 10M | slope |
|---|---|---|---|---|
| LinearSearch v2, batch of 10 | 20.5 ms | 201 ms | 2.54 s | 1.05 |
| BinarySearch v2, prepare (sort) | 20.5 ms | 280 ms | 4.40 s | 1.17 |
| BinarySearch v2, batch of 10 | 14.6 µs | 19.1 µs | 34.9 µs | 0.19 |
| Hash set, prepare (build) | 7.6 ms | 110 ms | 2.55 s | 1.26 |
| Hash set, batch of 10 | 305 ns | 325 ns | 664 ns | 0.17 |

What it shows:

- **Linear search stays linear.** 100× more data takes 124× longer, about 25 ns
  per element checked.
- **With few queries, preparing does not pay off.** At n = 10M with 10 queries,
  `total` (prepare plus the batch) is 2.56 s for linear, 2.52 s for hash and
  4.56 s for binary. Sorting costs about as much as 17 linear scans, building the
  set about 10, so binary search wins from roughly 18 queries and the hash set
  from roughly 11.
- **Lookups slow down once the data leaves the CPU cache.** From 1M to 10M,
  binary and hash query batches take 1.8–2.0× longer, while log₂ n predicts only about
  1.2× for binary search. At 10M the sorted list and the set (hundreds of MB) no
  longer fit in cache, so lookups wait for main memory.
- **The revisions hold:** linear v2 is 2.15–2.62× faster than v1 and binary v2
  1.17–1.44× faster, in all 6 datasets.

This is one machine and 3 repeats, so treat it as a robustness check, not as
part of the graded grid.

## Tests

```bash
python -m pytest                  # 674 passed (each run stores tests.txt and tests.xml)
python -m tests.mutation_check    # 10/10 mutants killed: the suite detects wrong behaviour
```

The suite covers:

- the slide example
- empty arrays and queries
- one entry
- duplicates
- unsorted and descending input
- present and absent queries and boundaries
- repeated queries
- negative and huge IDs
- output order and exact `bool` type
- unchanged input
- seeded random cases against an independent reference
- inputs of 100,000 entries
- invalid input
- "by hand" rules (AST check and comparison counts)
- generator properties, including golden checksums
- the measurement protocol (each segment times exactly what it claims)
- provenance
- a dashboard smoke test

The tests were run against stubs before the implementation; see
[00_docs/DEVLOG.md](00_docs/DEVLOG.md).

## Synthetic data (`01_code/datagen/generator.py`)

The generator is separate from the algorithms and from the measurement code.

| Setting | Value |
|---|---|
| Array length n | 1,000; 10,000; 100,000 |
| Query count q | 1; 100 |
| Scenarios (target hit rate) | `all_present` (1.0), `all_absent` (0.0), `mixed` (0.5). q = 1 `mixed` is not measured: one query cannot be half present |
| Duplicate policy | `allow`: IDs drawn with replacement from `[0, 2n)` (`unique` available) |
| Seed | 2026 (string-seeded `random.Random`) |

- The array depends only on (seed, n, policy), so every q and scenario for the
  same n uses the identical array.
- **Hit placement:** present queries sit at stratified *first-occurrence*
  positions, which is where a linear scan stops, spread evenly over the array.
  The average scan length for a hit is about n/2 for every n and q, and is
  saved as `mean_first_hit_frac`. A single random hit position would make q = 1
  linear timings depend on chance.
- Absent queries are drawn uniformly from the ID range minus the array. The
  query order is shuffled.
- The SHA-256 checksums of every array and query list are saved in
  `datasets.csv`. A golden-checksum test detects whether a Python version
  generates different data.

## Measurement definitions

All timings use `time.perf_counter()` and are stored in **seconds per call**.

| Segment | What one call is |
|---|---|
| `prepare` | `prepare(ids)`: copy, sort, set construction, or nothing; includes freeing the result |
| `query` | one **complete batch** of q queries on a state prepared freshly for each repeat (not timed); a warm-cache, steady-state figure |
| `total` | `prepare(ids)` plus the complete batch, timed together (measured, not summed; total ≠ prepare + query) |

- **Per-query** values are derived (batch / q) and labelled as derived.
- **Calibration** also serves as the warm-up. It picks
  `calls_per_measurement` (plus a 25% margin) so that one measurement lasts at
  least 10 ms. Short calls are looped, and the elapsed time is divided by the
  number of calls.
- **5 repeats** per (dataset, method, version, segment), with the method order
  rotated each repeat. The **median** is reported and every raw repeat is kept.
- **gc** is disabled inside timed loops (as `timeit` does). `gc.collect()` runs
  between measurements.
- **Excluded from timing:** data generation, validation, tests, preflight
  correctness checks, printing, memory tracing and the dashboard.
- **Harness overhead:** `noop_call_s` and `noop_lambda_call_s` in `run.json`
  are tens of nanoseconds. They are not subtracted. The dashboard marks
  medians within 10× of them as overhead-dominated.
- **Memory** is measured with `tracemalloc` in a separate process after
  timing, with a fresh tracing run per (dataset, method):
  - *Included:* the prepared structure, the output list, transient buffers in
    the peaks, and about 100 bytes of harness objects (`memory_baseline` in
    `run.json`).
  - *Excluded:* the input array and queries (built before tracing started) and
    native allocations that tracemalloc cannot see.

The definitions are also saved verbatim in every `02_results/<run_id>/run.json`.

## Results (`02_results/<run_id>/`)

| File | Content |
|---|---|
| `run.json` | status, grid, methods, current versions, definitions, test summary, harness overhead, memory baseline, `source_unchanged` |
| `environment.json` | Python, OS, CPU, RAM, timer resolution, package versions, git commit/branch/dirty, source fingerprint |
| `tests.txt`, `tests.xml` | test output from the same run |
| `datasets.csv` | every dataset's settings, realized hit rate, `mean_first_hit_frac` and checksums |
| `timings_raw.csv` | every repeat: segment, `calls_per_measurement`, `elapsed_s` |
| `timings_summary.csv` | median, min and max per (dataset, method, version, segment) |
| `memory.csv` | tracemalloc bytes per (dataset, method, version) |

`run_id` = `<UTC timestamp>_<git short sha>[_dirty][_quick]`.

- A run without `_dirty` was made from committed code, so its sha identifies the
  measured code.
- `source.sha256` in `environment.json` identifies the measured code without
  git.

Timings depend on the machine, so compare ratios and slopes rather than
absolute values across machines.

## Dashboard (`01_code/dashboard/`)

`python -m streamlit run dashboard/app.py` reads saved results only and never
runs a benchmark. It has four tabs:

- **Overview:** the measured commit, the test result, the key results table
  (n = 100,000, q = 100, mixed), the v1 → v2 speed-ups with the noise band, and
  the reproduce commands. Warnings appear only when something is wrong.
- **Runtime:** time against n on log–log axes (prepare, query batch and total),
  filtered by q and scenario in the sidebar, with a toggle to compare v1 and v2
  and the fitted slopes next to their expected values.
- **Spot check:** type your own IDs and queries and compare every method side by
  side.
- **Details for auditors:** everything else, one section at a time:
  - provenance and environment, including the source-fingerprint check
  - the per-test results and the mutation check
  - definitions, settings and the datasets with checksums
  - every v1/v2 ratio and the same-code control (binary v1 and v2 share
    `prepare`, so their ratio shows the noise level)
  - local slopes for every q and scenario
  - the tracemalloc memory table
  - the raw repeats, and downloads of every file

## Dependencies

- Python 3.13.15.
- The algorithms, generator and benchmarks use the standard library only.
- `01_code/requirements.txt` pins pytest 9.1.1 and, for the dashboard only,
  streamlit 1.67.0, altair 6.3.0 and pandas 3.0.6.

## Known limitations

- Passing tests are evidence, not proof of correctness.
- Timings depend on the machine and its load. Absolute values do not transfer
  between machines.
- At q = 1, query-batch times for binary search and the hash set are close to
  the harness overhead. The dashboard flags these values.
- Query-batch timings are warm-cache figures: the same structure is queried
  repeatedly. Cold-cache costs are higher.
- IDs are dense small integers (< 2^30). This is a best case for hashing (no
  collisions) and for CPython's integer comparisons. Large or sparse IDs would
  be slower.
- tracemalloc misses native allocations and does not equal auxiliary space. See
  the included and excluded lists above.
