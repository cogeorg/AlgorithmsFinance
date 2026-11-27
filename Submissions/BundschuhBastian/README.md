# Lab: Search methods (Phase 1)

Submission of Bastian Bundschuh for *Algorithms in Finance* (Classes 3-4, coding lab
Phase 1, slides 54-64).

**Task.** Given an integer ID array and an ordered list of queries, return one `bool` per
query (same order): is the query in the array? The input must stay unchanged. Three
methods, all passing the same tests:

| Method | Idea | Library parts used |
|---|---|---|
| `linear_search` | scan the array for every query | none |
| `binary_search_recursive` (v1) and `binary_search_iterative` (v2) | search a sorted copy | `sorted()` only |
| `hash_set_membership` | look every query up in a Python `set` | `set` |

Both search procedures (linear scan, binary search) are written by hand in plain Python.

## Setup

**Python 3.11 or newer is required** (`altair==6.3.0` needs it). Check:

```bash
python3 --version
```

From this folder (`Submissions/BundschuhBastian/`):

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

All results here were made with Python 3.11.0. Python 3.10 is not supported and was not
tested.

## Commands

| Step | Command | Takes (Apple M4) | Writes |
|---|---|---|---|
| Tests | `.venv/bin/python -m pytest -q` | about 13 s | nothing |
| Timing | `.venv/bin/python bench_time.py` | about 40 s | `results/timing_raw.csv`, `timing_summary.csv`, `timing_metadata.json` |
| Check total vs sum | `.venv/bin/python check_total.py` | under 1 s | `results/total_consistency.csv`, a note in `timing_metadata.json` |
| Memory | `.venv/bin/python bench_memory.py` | about 8 s | `results/memory_raw.csv`, `memory_summary.csv`, `memory_metadata.json` |
| Dashboard | `.venv/bin/streamlit run dashboard/app.py` | - | opens a page; only loads `results/` |

Run `check_total.py` again after every run of `bench_time.py` (the timing script rewrites
the metadata file). Run the timing and memory scripts one after the other, not at the same
time, and with no other heavy program running. Re-running them gives new numbers (see
"Limits").

**Expected test result:** `363 passed` (no failures, no skips) when `results/` is present.
Without `results/`, the tests that read saved results are skipped. Breakdown:

| File | Tests | What it checks |
|---|---|---|
| `tests/test_membership.py` | 233 | every method (4 of them): slide example, empty array / queries, one entry, duplicates, unsorted input, first / last positions, every position and gap for n = 1 to 17, output order, input unchanged, repeated calls, random vs. Python's `in`; prepare/answer split; call depth of v1 (grows with log n) and v2 (constant) |
| `tests/test_datagen.py` | 83 | the data generator |
| `tests/test_bench_time.py` | 6 | the timing script (rows, medians, wrong answers are detected) |
| `tests/test_bench_memory.py` | 12 | the memory script (growth of bytes, not exact bytes) |
| `tests/test_check_total.py` | 6 | total vs prepare + query check |
| `tests/test_dashboard.py` | 23 | dashboard data helpers, number formatting, computed sentences, and a headless run of the page for every setting |

The total is what to compare; the per-file counts are the numbers at the time of writing.

## Files

| File | Purpose |
|---|---|
| `membership.py` | the methods; each is `answer(prepare(ids), queries)`; registries `METHODS` and `PHASES` |
| `datagen.py` | synthetic data: `generate(n, q, hit_rate, duplicates, seed)`; no algorithms, no timing |
| `bench_time.py`, `bench_memory.py`, `check_total.py` | measurement and checks |
| `dashboard/app.py`, `dashboard/loaders.py`, `dashboard/report.py` | Streamlit report page; loads saved results only |
| `.streamlit/config.toml` | page theme (light, white, dark blue accent) and minimal toolbar; read when `streamlit run` is started from this folder |
| `results/` | saved measurements (CSV and JSON) |
| `REVISIONS.md` | what changed from v1 to v2 and why |
| `AI_LOG.md` | which AI suggestions were accepted, corrected or rejected, and why |

## Data

`generate(n, q, hit_rate, duplicates, seed)` with its own `random.Random(seed)`:
IDs are drawn from `0 .. 10n + 9`, in random order (not sorted). Hit rates:
`all-present`, `all-absent`, `mixed` (`(q + 1) // 2` queries present). Absent queries lie
below, between and above the IDs. Duplicate policies: `none`, `some`, `many`. The
benchmarks use seed `20260`, duplicates `none`, n in {1000, 10000, 100000}, q in {1, 100}
and all three hit rates. Every method and version gets the identical dataset.

## Measurement definitions

Timing (`bench_time.py`, `time.perf_counter`, seconds):

* **prepare**: `prepare(ids)`: sorting a copy (binary), building the set (hash). Linear
  search has no preparation (its value is call overhead only).
* **query**: `answer(state, queries)`: the whole batch of q queries, state already built.
* **total**: `method(ids, queries)`, timed on its own (**not** the sum of the other two).
* **per batch** = seconds for one execution of the phase with all q queries.
  **per query** = per batch / q (only for `query` and `total`).
* Protocol: calibrate k calls per repeat so that a repeat lasts at least 20 ms (short
  phases are timed as k calls together and divided by k); one untimed warm-up repeat; 5
  timed repeats; **median** reported; a fresh prepared state before every repeat; garbage
  collection run before and disabled during a repeat. Not timed: data generation,
  correctness checks (made after the clock stops), printing, saving. The result of every
  repeat is compared with the expected answers.
* Saved next to the numbers: seed, generator settings, units, Python version, machine
  (CPU model, memory), git commit, clock resolution.

Memory (`bench_memory.py`, `tracemalloc`, bytes), always run separately from timing:

* Fresh trace per method and phase; the **input is built before tracing and is not
  included**; the output stays alive; **current** = bytes still allocated after the call,
  **peak** = largest allocation at any moment.
* `prepare`: current = prepared structure (sorted list / set / nothing). `query`: state
  built before tracing; current = output list. `total`: peak = prepared structure + output
  + temporaries.
* Exact byte counts in `results/memory_*.csv` are from **Python 3.11.0**. `tracemalloc` and
  the interpreter add a small version-dependent constant (for example about 400 bytes more
  on 3.10), so the memory tests check how the numbers grow, not exact values.

### Why `total` is not the same as prepare + query

`total` is measured on its own, not computed as the sum. The three phases run as separate
blocks at different moments, so the numbers can differ. `check_total.py` computes
`ratio = total / (prepare + query)` for each of the 72 configurations from the saved
results. In the saved run it ranges from **0.73 to 1.25**; 42 are within 3 %, 22 below
0.97, 8 above 1.03. The `[min, max]` range of `total` overlaps the summed ranges in 60
configurations and **does not in 12**, so noise inside one block does not explain every
difference. What was measured: `prepare(ids)` does identical work for every q and hit rate,
yet its median differs between those blocks by up to 1.33x (n = 100,000), more than the
spread of the repeats inside one block (spread = max / min of the repeats). A cache effect
between `query` and `total` is possible but was not tested. Building a set while the
previous one is still alive was tested and is not slower (about 6.8 ms either way at
n = 100,000). The dashboard shows measured total, prepare + query and the spread side by
side. The full explanation is in `results/timing_metadata.json`
(`total_vs_prepare_plus_query`).

## Revision v1 to v2

Only binary search was revised (details in `REVISIONS.md`):

* the recursive search became a loop: no helper call per step, O(1) instead of O(log n)
  stack per query;
* with no queries, v2 returns `[]` before sorting.

The sorted copy stays: the input may be unsorted and must not change, so `ids.sort()` is
not allowed. v1 had no other unnecessary copy. Both versions are kept (`binary_v1`,
`binary_v2`) and pass the same tests. Measured over all 18 data configurations: the query phase of v2 takes 0.64 to
0.75 times the time of v1; the total ratio v2 / v1 is 0.82 to 1.06, i.e. no reliable
difference, because sorting dominates it.

## Complexity claims

n = number of IDs, q = number of queries. "Extra memory" is memory besides the input.

| Method | Preparation (time) | Per query (time) | Total (time) | Extra memory |
|---|---|---|---|---|
| linear | none, O(1) | O(n) worst case (query absent), on average O(n) as well | O(n q) | O(q) output only |
| binary v1 | sort a copy: O(n log n) | O(log n) | O(n log n + q log n) | O(n) sorted copy + O(q) output; O(log n) recursion stack per query |
| binary v2 | sort a copy: O(n log n) | O(log n) | O(n log n + q log n) | O(n) sorted copy + O(q) output; O(1) per query |
| hash set | build the set: O(n) on average, O(n^2) worst case | O(1) on average, O(n) worst case | O(n + q) on average | O(n) set table + O(q) output |

Why: sorting by comparisons needs about n log n steps; binary search halves the range every
step, so after about log2(n) + 1 steps it is empty; a set jumps to a table slot by the hash
value and compares only the few entries in that slot, which are many only if many IDs
collide.

Evidence in the saved results (q = 100, all queries absent, query phase, median in ms):

| n | linear | binary v1 | binary v2 | hash |
|---|---|---|---|---|
| 1,000 | 1.03 | 0.102 | 0.075 | 0.0026 |
| 10,000 | 10.8 | 0.144 | 0.105 | 0.0026 |
| 100,000 | 133 | 0.177 | 0.128 | 0.0027 |

Linear grows about 10x when n grows 10x, binary grows slowly (log n), hash is flat. Memory
at n = 100,000: sorted copy 800,056 bytes (8 bytes per ID), set 4,194,520 bytes (hash table
of 262,144 slots x 16 bytes); the peak while sorting is 1.5x the copy and while building the
set 1.5x the table.

## Dashboard

```bash
.venv/bin/streamlit run dashboard/app.py
```

Start it from this folder (the theme in `.streamlit/config.toml` is read from the current
folder). It is one scrolling report page that only loads `results/` and measures nothing;
without the result files it prints the two commands that create them. The controls are
q, hit rate and time per batch / per query. The sentences under "Findings" are computed
from the saved results.

| Part | What it shows |
|---|---|
| Findings | at n = 100,000, q = 100: total time of hash set, binary search (and its sorting share) and linear search; the q = 1 case in which linear search is fastest; memory of the sorted copy and the set |
| Figure 1 | median time of preparation, query batch and total against n, log-log, one curve per method (linear and binary in grey, hash set in dark blue, labels at the line ends), one y scale for the three panels |
| Figure 2 | query batch of binary search, v1 (solid) against v2 (dashed), with the measured v2 / v1 ratio |
| Figure 3 | table: measured total next to preparation + query, their ratio, and the spread (max / min of the repeats) |
| Table 1 | memory: prepared structure and peak during the call, in kB |
| Appendix (collapsed) | protocol, raw timing and memory repeats, environment and metadata |

Units: milliseconds, or microseconds when all values of a figure are below 1 ms; the unit is
written on the axis. In per-query mode preparation stays per batch.

## Limits

* One machine (Apple M4), Python 3.11.0, one seed, duplicates `none`. Other machines give
  other absolute numbers.
* Repeats of the same configuration differ by up to 1.8x (large linear runs); medians rank
  the methods reliably, but do not read small differences (for example v1 vs v2 `total`)
  as real. The methods always run in the same order (not randomised).
* Hit-rate effects: linear search stops at the first match, so `all-present` is about half
  as slow as `all-absent`; the other methods do not depend on the hit rate.
