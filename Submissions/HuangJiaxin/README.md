# Membership queries: LinearSearch, BinarySearch, hash set

Huang Jiaxin, Algorithms in Finance, Class 2 coding lab, Phase 1.

## Specification

* **Input:** `ids`, a list of integer trade IDs (any order, duplicates allowed, may be
  empty), and `queries`, a list of integer IDs in a fixed order (may be empty).
* **Output:** a list of Booleans, one per query, in the same order as `queries`.
  Answer *j* is `True` exactly when `queries[j]` occurs in `ids`.
* The given `ids` list is never modified.

| Method | Preparation | Query step | Expected cost (n entries, q queries) |
|---|---|---|---|
| `linear_v1` (original) | none | own LinearSearch, while loop with index | prepare 0, Θ(n) per query worst case |
| `linear_v2` (revised) | none | own LinearSearch, for loop over values | same Θ(n), smaller constant |
| `binary_v1` (original) | `sorted()` copy | own recursive BinarySearch with list slices | Θ(n log n) prepare, Θ(n) per query (slices copy) |
| `binary_v2` (revised) | `sorted()` copy | own iterative BinarySearch with index bounds | Θ(n log n) prepare, Θ(log n) per query |
| `hash` | `set()` | built-in set membership | Θ(n) expected prepare, Θ(1) expected per query |
| `bisect_ref` | `sorted()` copy | standard library `bisect_left` | **reference only, not my implementation** |

Both search procedures are written by hand in Python; only sorting, the set and the
`bisect_ref` baseline use library code, as allowed. All six methods pass the same tests.

## Files

| File | Content |
|---|---|
| `membership.py` | All methods, original and revised versions, preparation/query split |
| `data.py` | Synthetic data generator (separate from algorithms and measurement) |
| `test_membership.py` | Tests, written first; every method runs the same tests |
| `benchmark.py` | Timing grid; writes `results/timing_raw.csv`, `timing_summary.csv`, `environment.json` |
| `breakeven.py` | Break-even analysis; writes `results/breakeven_curve.csv`, `breakeven_points.csv`, `breakeven_raw.csv`, `breakeven_environment.json` |
| `memory.py` | tracemalloc measurement; writes `results/memory.csv`, `memory_environment.json` |
| `dashboard.py` | Streamlit dashboard; reads only the saved results |
| `requirements.txt` | Pinned dependency versions |
| `Dockerfile`, `.dockerignore` | Optional Docker packaging |
| `TRACE.md` | Hand traces of BinarySearch and LinearSearch on small examples |
| `evidence/` | Saved test output before (Step 3) and after (Step 4) the implementation |

## How to run (without Docker)

Python 3.11 or newer. From this folder:

```bash
pip install -r requirements.txt
python -m pytest -q          # expected: 146 passed
python benchmark.py          # about 20 s; for a trial use --quick --out /tmp/trial
python breakeven.py          # about 20 s
python memory.py             # a few seconds
streamlit run dashboard.py   # opens http://localhost:8501
```

## How to run (with Docker)

The image uses `python:3.12-slim`, which exists for Intel/AMD and Apple Silicon.
Run from this folder (`Submissions/HuangJiaxin/`).

```bash
docker build -t huangjiaxin-membership .

# tests (expected: 146 passed)
docker run --rm huangjiaxin-membership python -m pytest -q

# measurements; results are written to ./results on the host through the volume
docker run --rm -e CODE_COMMIT=$(git rev-parse HEAD) -v "$(pwd)/results:/app/results" huangjiaxin-membership python benchmark.py
docker run --rm -e CODE_COMMIT=$(git rev-parse HEAD) -v "$(pwd)/results:/app/results" huangjiaxin-membership python breakeven.py
docker run --rm -e CODE_COMMIT=$(git rev-parse HEAD) -v "$(pwd)/results:/app/results" huangjiaxin-membership python memory.py

# dashboard on http://localhost:8501 (default command of the image)
docker run --rm -p 8501:8501 -v "$(pwd)/results:/app/results" huangjiaxin-membership
```

`CODE_COMMIT` records the code version in `results/environment.json`, because the
container has no `.git` folder. On Windows PowerShell replace `$(pwd)` with `${PWD}`. Timings inside a container
depend on the host machine and any container resource limits.

## Tests

Written before the implementation. They cover the slide example
(`[7, 11, 7]`, queries `[11, 9, 7]` give `[True, False, True]`), empty array, empty
queries, both empty, one entry, duplicates, unsorted input, first and last positions,
queries smaller or larger than every entry, negative IDs, repeated queries and output
order, unchanged input, repeated calls, synthetic data with and without duplicates at
hit rates 0, 0.5 and 1, and 300 random small cases. Every answer is compared with an
independent reference (`x in ids`).

Before writing the methods, the tests were run against a stub that returns `False` for
every query; 72 of the 122 tests failed, which shows they detect wrong behavior.
The saved run in `evidence/step3_tests_before_implementation.txt` shows that the test
file cannot even be collected before `membership.py` exists; after the implementation all
122 tests pass (`evidence/step4_tests_after_implementation.txt`). After the Phase 2 audit,
24 tests were added for the data generator (146 in total, see below).
Passing tests are evidence, not a proof of correctness.

## Synthetic data

* IDs: `n` distinct even integers in random order (`duplicates="none"`); the tests also
  use `duplicates="allowed"`.
* Present queries: `floor(q * hit_rate + 0.5)` copies of IDs (rounding half up, so
  q = 1 with hit rate 0.5 has one present query). Absent queries are random integers that
  are checked to be missing from the IDs, so the hit rate is exact for any integer IDs.
* Invalid arguments (hit rate outside 0 to 1, negative q) raise `ValueError`.
* Seed `20261120`; all settings are saved in `results/environment.json`.
* Timing grid: n ∈ {1,000, 10,000, 100,000}, q ∈ {1, 100}, hit rate ∈ {1.0, 0.0, 0.5}.
  Every method and version receives identical inputs.

## Measurement definitions

* Clock: `time.perf_counter()`. Values are **seconds per complete batch**, not per query.
* `prepare_s`: building the sorted copy or set (zero work for linear).
  `query_s`: the full batch of q queries. `total_s = prepare_s + query_s`.
* One untimed warm-up, then 5 repeats; the median is reported, raw repeats are saved.
* A fresh sorted copy or set is built in every repeat, so preparation is never free.
* Blocks shorter than 2 ms are run several times in a row and divided by that count
  (columns `inner_prepare`, `inner_query`).
* Garbage collection runs before each timed block and is switched off during it.
* After every repeat, outside the clock, the answers are compared with the expected list.
* Excluded from timing: data generation, tests, answer checks, printing, dashboard.
* `benchmark.py --out DIR` writes elsewhere, so a trial run does not overwrite `results/`.
* Every result file has metadata with Python version, machine and code commit:
  `environment.json`, `breakeven_environment.json`, `memory_environment.json`.
* Memory is measured in a separate run with `tracemalloc`: peak traced bytes for
  preparation plus the query batch, output kept alive. It includes the prepared
  structure, temporary slices and the output list, and excludes the given input.
  It sees Python allocations only, so it is not exactly auxiliary space.

## Revisions

**Revision 1, BinarySearch.** The original (`binary_v1`) was recursive and passed list
slices such as `sorted_ids[m + 1:]` to the next call. Each slice is a new copy, so one
query copies about n/2 + n/4 + ... ≈ n entries: Θ(n) per query instead of Θ(log n), plus
extra memory. The revised version (`binary_v2`) is iterative and keeps two indices
`lo` and `hi`; it never copies. Invariant: before each loop check, if x occurs it lies
in `sorted_ids[lo..hi]`. Measured (n = 100,000, q = 100, hit rate 0.5): query batch
about 24 ms original vs 0.14 ms revised, roughly 170 times faster. The gap grows with n,
as predicted.

**Revision 2, LinearSearch.** The original (`linear_v1`) follows the slides' pseudocode
with an explicit index `i`. The revised version (`linear_v2`) iterates over the values
with a `for` loop. The asymptotic cost is the same Θ(n) per query; the revision only
removes Python-level index bookkeeping. Measured (n = 100,000, q = 100, hit rate 0.5):
about 220 ms vs 65 ms, roughly 3.4 times faster. This shows that constant factors
matter in practice even when the Θ class does not change.

**Library reference.** My `binary_v2` is about 6 times slower than `bisect_ref` for the
same Θ(log n) idea, because `bisect` runs in C while my loop runs in Python.

## Break-even analysis

LinearSearch has no preparation; the other methods pay once and then answer cheaply.
`breakeven.py` measures the total time for q ∈ {1, 3, 10, 30, 100, 300, 1000}
(hit rate 0.5) and estimates the break-even query count

q\* = preparation time ÷ (linear time per query − method time per query).

| n | `binary_v2` q\* | `hash` q\* |
|---|---|---|
| 1,000 | about 7.6 | about 1.7 |
| 10,000 | about 13.9 | about 3.6 |
| 100,000 | about 20.0 | about 4.7 |

Interpretation: on my machine, building a set pays off after only a few queries; sorting
plus binary search needs about 8 to 20 queries, more for larger n. For a single query and
n ≥ 10,000, plain LinearSearch is fastest (n = 100,000: about 0.6 ms vs 3.1 ms for building
a set). At n = 1,000 the two are close (about 0.009 ms vs 0.011 ms in my run).

## Results summary (my machine, see `results/environment.json`)

Measured on my MacBook Air (Apple Silicon) inside Docker from a fresh checkout of
the repository: Python 3.12.16, Linux aarch64 container, 20 November 2026, code at
commit `4cb994b`, after the fixes from the Phase 2 audit (recorded in
`results/environment.json`, `breakeven_environment.json` and `memory_environment.json`).

* **q = 1:** for n ≥ 10,000, `linear_v2` has the smallest total time; preparation does
  not pay off. At n = 1,000 LinearSearch and the hash set are close (see the spread tables in
  the dashboard), so the winner there depends on the machine and on noise.
* **q = 100:** `hash` has the smallest total time, `binary_v2` is second, LinearSearch
  is slowest because it rescans the array for every query.
* Preparation dominates the total for `binary_v2` and `hash`; query time for `hash` is
  almost flat in n, `binary_v2` grows slowly, LinearSearch grows linearly.
* Memory: `hash` has the largest peak (a set is bigger than a sorted list);
  `binary_v1` is above `binary_v2` because of the slices.
* The more queries, the more it pays to prepare once.

Timings depend on the machine; rerun the scripts to reproduce on yours.

## Changes after the Phase 2 audit

Bastian Bundschuh audited commit `47ec3ae` (report:
`Submissions/BundschuhBastian/audit_HuangJiaxin/AUDIT_REPORT.md`). All five reported bugs
were confirmed and fixed; the measurements were then rerun.

| Audit finding | Cause | Fix |
|---|---|---|
| Bug 1: for q = 1, "mixed" was the same batch as "all absent" | `round(0.5) == 0` (Python rounds halves to even) | `present_count` rounds half up; tests for q = 1, 2, 3 |
| Bug 2: "for a single query, LinearSearch is fastest" did not hold at n = 1,000 | scan and set construction take about the same time there | claim restricted to n ≥ 10,000; spread of the repeats shown in the dashboard; garbage collection disabled during timed blocks |
| Bug 3: invalid hit rates returned more than q queries | no input check | `ValueError` for hit rate outside 0 to 1 and for q < 0 |
| Bug 4: "absent" queries could be present for odd IDs; crash for negative IDs | absence relied on all IDs being even | absent queries are checked against the IDs; works for any integers |
| Bug 5: dashboard traceback when a results file is missing | no file check | message naming the missing file and the script that creates it |

Also addressed from the audit's shortcomings: answers are checked after every timed
repeat; break-even raw repeats are saved; every result file has its own environment and
commit metadata; `--out` keeps trial runs away from `results/`; calibration of the number
of calls per block uses the fastest of three warm calls instead of one cold call. The
memory measurement stays a single run, because the allocations are deterministic (the
auditor's rerun gave byte-identical results).

## Workflow

The work follows the five steps from Class 1, one commit each: (1) set up the
repository, (2) synthetic data, (3) tests first, (4) implementation and hand traces,
(5) measurements, dashboard and documentation. See `git log`.

## Commit to be audited

See the pull request description. The measurements in `results/` were produced
with the code at commit `4cb994b`.

## Use of AI

I used Claude (Anthropic) as an AI assistant during this lab.

* **Accepted:** the project structure and first drafts of all Python files
  (algorithms, tests, data generator, benchmark, memory, break-even analysis,
  dashboard), the Dockerfile and the README text. Commits are marked with a
  Co-Authored-By line.
* **Checked and corrected by me:** I traced BinarySearch and LinearSearch by hand
  (`TRACE.md`) and checked the results against the code. In Trace 2 I first wrote
  `hi = 4` at the matching step and corrected it to `return True` after reviewing
  the three cases of the comparison. I ran the tests, benchmarks and the Docker image
  on my own MacBook Air and replaced the assistant's measurements with my own.
* **Rejected or changed:** Of five extensions the assistant suggested, I chose
  three (Docker, a second revision, the break-even analysis) and left out
  theory reference lines and multiple-seed runs, to keep the project small
  enough to review. I asked to restructure the upload into one commit per step
  of the Class 1 workflow instead of a single upload. I asked for the hand
  traces to be in English, as the course is taught in English, and I corrected
  an authorship line in TRACE.md that overstated how much I had traced alone.
* **After the Phase 2 audit:** the fixes for the five bugs Bastian reported were drafted
  with Claude; I reran the tests and all measurements on my own machine.
* **What I can explain myself:** why slicing makes `binary_v1` cost Θ(n) per
  query; why preparation only pays off after several queries; the three cases of
  each binary-search step (smaller: move lo, larger: move hi, equal: return True),
  which I got wrong once in Trace 2; why LinearSearch never reads position 2 when
  it finds 11 at position 1, and why an absent query is its worst case; why the
  final loop check `i < n` is not counted as a data comparison; and why the
  break-even query count for sorting grows with n while it stays small for the
  hash set.
