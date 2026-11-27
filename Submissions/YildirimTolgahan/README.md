# Search methods — Tolgahan Yildirim

Phase 1 of the *Algorithms in Finance* coding lab. All files are confined to
`Submissions/YildirimTolgahan/`. No third-party packages or Docker are required.

## Run from a fresh checkout

Reference environment: CPython **3.13.12**, Windows x64. The code uses Python
3.10+ syntax and only its standard library. `requirements.txt` records that
there are no external dependencies to install or pin.

From the repository root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
cd Submissions\YildirimTolgahan
python -B -m unittest discover -v
python -B benchmark.py
python -B benchmark_reuse.py
python -B check_speed.py
python -B dashboard.py
python -B verify_results.py
Start-Process .\results\dashboard.html
```

If the project environment already exists, start with activation. Check
`python --version` before running. On macOS/Linux, use `python3 -m venv .venv`,
`source .venv/bin/activate`, and `cd Submissions/YildirimTolgahan`; open the HTML
with any modern browser. No web server, internet connection, dashboard port or
API key is needed to run this project.

Expected test result: **21 tests, OK**, including shared subtests for every
method/version. The course's `Class1-2` demonstration is a separate project.

For a quick end-to-end run without replacing the submitted measurements:

```powershell
python -B benchmark.py --sizes 100 1000 --query-counts 1 10 --output results/smoke
python -B dashboard.py --results results/smoke/measurements.json --output results/smoke/dashboard.html
```

## Specification and tests first

An integer array and ordered query batch produce a list of actual Python
Booleans in query order. Neither input is changed. Tests cover empty arrays
and queries, singleton inputs, duplicates, unsorted inputs, first/last values,
absent values, repeated calls, negative/large integers and generated examples.
An exhaustive test covers all 121 arrays of length 0 through 4 over {-1,0,1}.
Prepared structures are also reused across repeated lookups and checked for mutation.
The slide example `[7, 11, 7]`, `[11, 9, 7]` gives `[True, False, True]`.

Tests and the synthetic generator were written before implementation.
`results/test_before.txt` records the run against `NotImplementedError`
placeholders. The same search tests remain after implementation; measurement
and HTML-export tests were added afterwards. Passing these tests is evidence,
not a proof of correctness.

Small manual trace: sorted copy `[7, 7, 11]`, query `9`: check index 1 (`7`),
then index 2 (`11`), then the interval is empty → `False`. Query `11` reaches
index 2 → `True`. The caller's original `[7, 11, 7]` remains unchanged.

## Methods and revision

| Method | Original | Revised |
|---|---|---|
| Linear | Copy the input once, then scan for every query | Scan the existing input without a redundant copy |
| Binary | Sort a copy, then recurse over index intervals | Sort a copy, then search iteratively |
| Hash set | Construct a set; Python wrapper call per query | Construct a set; grouped native membership using `map` |

Linear and both binary search procedures are implemented here. Library sorting
and sets are explicitly permitted. No `bisect`, library search procedure or
array-membership shortcut is used for the two search implementations.

For linear search, the processed prefix contains no match; returning early
finds an equal item, and exhausting the array rules one out. For binary search,
any possible match stays in the inclusive interval `[left, right]`; each
failed comparison excludes the middle and an impossible half. The interval
strictly shrinks, including on duplicate values. Set membership has the same
integer equality semantics. No method mutates its input.

The linear revision avoids O(n) preparation time and allocation. Both binary
versions use O(log n) comparisons per query, with O(log n) recursive stack
space originally and O(1) search stack space after revision. Both still pay
for sorting a copy; Python's sorting also has workspace costs. Hash-set
construction uses O(n) expected time and O(u) storage for u distinct IDs;
membership is expected O(1), with collision-dependent worst cases. Every
method additionally builds an O(q) output list. Total costs must include
preparation. These bounds do not predict exact timings or guarantee that a
revision wins every measured case.

The revised hash batch binds the built-in set membership method once and uses
`list(map(prepared.__contains__, queries))`, avoiding a Python wrapper function
per query. It preserves Boolean output and query order. The standard-library
set is allowed by the lab; the linear and binary searches remain our own code.

For multiple batches against unchanged IDs, use an explicit snapshot:

```python
from algorithms import HashIndex

index = HashIndex([7, 11, 7])       # build once
print(index.answer([11, 9, 7]))    # [True, False, True]
print(index.answer([9, 11]))       # [False, True], reuse the index
```

The snapshot owns a copy of the IDs. Later changes to the original list do not
silently change its meaning: construct a new `HashIndex` for updated data.
`benchmark_reuse.py` separately compares five batches with five index builds
against the same five batches with one build. Both measured totals include
index construction and all queries. Raw rounds and source hashes are saved in
`results/reuse.json`; this is separate from the one-batch comparison.

## Fixed workloads and measurement definitions

The default run uses n in {1,000; 10,000; 100,000}, q in {1; 100}, exactly
feasible hit rates, and two duplicate policies. q=1 uses 0% or 100%; q=100
also uses 50%. This gives **30 workloads**, each run with all six method/version
combinations (**180 summary rows**, **900 raw repeats** with three phase
measurements each). Input/query order is identical across methods and versions
within a workload. Method execution order is reproducibly shuffled every round;
each method's position and the order seed are saved.

`data.py` uses its own seeded `random.Random`. Unique inputs are shuffled even
IDs. Duplicate inputs draw n even IDs with replacement from max(1, n//4)
possible values. Absent queries are odd. Present queries sample existing
items with replacement. Query order is shuffled. The hit count rounds
`q * requested_hit_rate` to the nearest integer, with halves rounded up.
The generator supports rounded counts for general callers. The benchmark
excludes settings that cannot realize the requested rate exactly, so a single
query never has a misleading 50% label. Requested and achieved rates, seeds,
duplicate policy and distinct-ID counts are saved and shown in the dashboard.

- Timing uses `timeit` with its `perf_counter` timer and five rounds. Each
  phase/method/round has a separate warm-up/calibration followed by a grouped
  timed sample targeting 3 ms, capped at 20,000 calls. Raw repeats report
  milliseconds per complete invocation, not per query. Each phase saves its
  own call count. Cyclic GC is disabled by `timeit` during timing.
- Preparation (copy/sort/set construction), query batch and end-to-end total
  are measured **independently**; their values and medians need not add up.
  Preparation and total build fresh state every call. Query timing reuses one
  prepared index for that round. Function-call and temporary-result disposal
  overhead are included; per-invocation clock reads have been removed.
- Generation, expected answers, validation, aggregation, memory tracing and
  HTML rendering are outside the timed intervals. Output construction is
  included. No profiler runs during timings.
- All timing rounds for a workload finish before its memory measurements.
- Memory uses a **separate fresh `tracemalloc` run** per row. Input, queries
  and expected answers exist before tracing. Prepared structures and the
  output remain alive through the current/peak reading. Values are traced
  Python bytes; the dashboard converts these to KiB. They exclude pre-existing
  inputs and do not claim to measure all native memory, process RSS or
  mathematical auxiliary space. A single memory reading is not a distribution.
- Metadata includes Python/OS/CPU details, UTC time, settings, Git HEAD and
  working-tree status. SHA-256 hashes identify the actual source files even
  when measurements precede a commit. Timings vary with host load and runtime.

## Files and dashboard

| File | Purpose |
|---|---|
| `algorithms.py` | Original/revised implementations and common batch contract |
| `data.py` | Seeded synthetic data, separate from measurement |
| `test_lab.py` | Contract, generator, measurement and export tests |
| `benchmark.py` | Timing, independent memory measurement, JSON/CSV export |
| `benchmark_reuse.py` | Fair multi-batch comparison: build per batch versus build once |
| `dashboard.py` | Generate an interactive standalone HTML file from saved JSON |
| `dashboard_template.html` | Graph dashboard, explicit unit selector and time-budget panel |
| `check_speed.py` | Check the ten-second per-batch limit against saved and fresh searches |
| `verify_results.py` | Check complete coverage, CSV/JSON agreement, medians, order seeds, source hashes and byte-identical HTML export |
| `results/measurements.json` | Full raw repeats, medians and environment |
| `results/summary.csv`, `results/raw_repeats.csv` | Tables for independent analysis |
| `results/dashboard.html` | Open locally; filter by q, hit rate, duplicate policy and time component |
| `results/test_before.txt`, `results/test_after.txt` | Recorded validation runs |
| `audit/AUDIT.md` | Audit of the supplied Astra ZIP and integration decisions |
| `audit/verify_astra.py` | Reproduce CSV/hash, export and Git-history checks |

The restored graph dashboard shows elapsed time against input length, including
original and revised curves. Filters select query count, hit rate, duplicate
policy, time component, versions, axis scale and seconds/milliseconds.
Seconds are the default: **11 ms = 0.011 s** and 11 microseconds = 0.000011 s.
The table and graph always use the same selected unit; raw files retain their
recorded millisecond units. A visible panel checks the largest saved raw
per-batch total against ten seconds. The dashboard embeds saved
JSON; filtering does not rerun measurements. Rerun `dashboard.py` after updating
measurements. Keep HTML, JSON and CSV together for the download links. The
export fixes UTF-8/LF output for identical bytes across operating systems when
the saved measurement file and template are the same.

## Observations from the saved run

Current observations are recorded in `results/observations.md`, based solely
on the regenerated Windows results. All workloads and repeats remain in the
dashboard and CSV files. Timings describe this machine and experiment;
measurement noise remains, and a revision does not win every case. Removing
the linear copy reduces preparation storage; replacing
recursion removes recursive search frames, but sorting still dominates many
binary-search total timings.

Validation: 21 tests pass under CPython 3.13.12. Chrome checks all 45 supplied
Astra dashboard selections and all 360 selections of the graph dashboard, including correct seconds/milliseconds
conversion and table/data agreement. The report
is `results/dashboard_browser_check.json`. Optional browser QA requires Node
22+ and Chrome, and can be repeated with `node audit/check_dashboards.cjs`;
these tools are not needed to run the Python lab or open its dashboard.
`python -B verify_results.py` repeats the saved-data and byte-rebuild checks;
its report is `results/verification.json`.
Run verification without `-O`/`-OO`: the scripts reject those flags rather than
silently skipping assertions. `.gitattributes` preserves exact file bytes so
Git's automatic newline conversion cannot invalidate recorded source hashes.

The earlier per-call-clock results and their exact Python sources are retained
in `results/legacy_per_call_clock/`. The supplied Astra files, Linux results
and incremental bundle remain under `audit/astra/`. They are separate evidence
sets, not measurements of the revised Windows implementation. Run
`python -B audit/verify_astra.py` to repeat that archive audit.

## AI assistance and audit handoff

Codex generated the implementation, tests, measurement/export code and this
documentation with AI assistance. Accepted suggestions: assertions/unittest
instead of an extra test dependency; an offline dashboard; removing the
linear copy and replacing recursion with iteration. Corrected design choices:
the recursive helper uses explicit arguments to avoid a self-referential
closure, and the dashboard exposes achieved hit rates for q=1. Rejected
assumptions: preparation is free, a revision always wins, traced memory is
process memory, or passing tests proves correctness. This documents the AI
contribution; the submitted work should retain this disclosure.
The supplied Astra variant was reviewed before integration. Its exhaustive
tests, grouped timing approach, randomized rounds, feasible hit-rate selection
and dashboard-template separation informed the changes documented in
`audit/AUDIT.md`. Its quoted timings and Git history are attributed to that
variant, not presented as this working version's results or history.

The submission commit and Pull Request head identify the version for peer
audit; measurement metadata also identifies the exact timed source files.
Phase 2 requires another student's chosen commit. This directory implements
Phase 1 and documents the review of the supplied alternative implementation;
that comparison does not replace the separate Phase 2 peer audit.
The final submission review is documented in `audit/FINAL_REVIEW.md`.
The subsequent hash-batch/index-reuse optimization and simpler dashboard are
documented in `audit/OPTIMIZATION_REVIEW.md`.

## Ten-second target and restored graphs

`python -B check_speed.py` checks all 900 saved total-time samples and five
fresh optimized searches (100,000 IDs, 100 queries, including index creation).
It writes `results/speed_budget.json`; `verify_results.py` verifies that report
against the exact input/source hashes. The target concerns one search batch.
The full benchmark suite deliberately performs many repeated algorithm runs.

The graph layout is restored from the earlier design. This is a presentation
change, so timings were not modified or relabeled. The template actually used
at measurement time is preserved at `audit/template_before_graph_restore.html`;
metadata records that snapshot and the current presentation hashes separately.
See `audit/GRAPH_RESTORE_REVIEW.md`.
