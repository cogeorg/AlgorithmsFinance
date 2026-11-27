# HardiKhushi — Search methods

The take-home project is [Assignment 1: limit order book](Assignment1/README.md).
Its tests, original/revised engines, raw results, report, dashboard and AI records
are inside Assignment1/. The earlier search lab below is preserved.

Self-contained *Algorithms in Finance* project comparing manual linear search,
manual binary search, and standard-library hash-set membership. Everything is
inside `Submissions/HardiKhushi/`; course folders and other submissions are not
modified. Python 3.10+ is required, with no third-party packages.

## Current experiment

The saved experiment compares **original and revised manual versions** on
36 workloads: n = 1,000 / 10,000 / 100,000; q = 1 / 100; all-present /
all-absent / mixed queries; unique / repeated input IDs. Six method/version
variants per workload yield 216 configurations. Each has five timing repeats
per phase and five separate memory repeats. See `results/environment.json`
for the actual saved run's settings and code identity, and `results/SUMMARY.md`
for findings. Alternate command-line settings change these counts.

The original library-based project and its preliminary measurements are
preserved in `archive/pre_revision/`. They are not included as a manual
algorithm version in the new comparison. `REVISIONS.md` explains the history,
changes, costs, and limits. `PROGRESS.md` records verification and remaining work.

## View the dashboard

Open `dashboard.html` in a modern browser. It works offline, with no server,
package installation, or internet access. JavaScript must be enabled.

Choose query scenario, query count, duplicate policy, timing component, and
linear/logarithmic vertical scale. Each chart shows all three methods, with
original versions dashed and revisions solid. The table shows preparation,
query-batch, total time, and current/peak traced allocation. Summary cards
compare revised methods at the largest selected input size. They always refer
to total time and full-call peak memory, independently of the time-chart filter.
CSV downloads provide raw repeats; environment details include source hashes.
Changing filters only reads embedded saved data and never runs benchmarks.

## Files

| File | Role |
| --- | --- |
| `README.md` | Entry point, commands, interfaces, and measurement definitions |
| `AGENTS.md` | Working rules, including approval before commands |
| `.gitattributes` | Preserves file bytes/source hashes and recognizes CSV CRLF endings |
| `PROGRESS.md` | Work history, decisions, approvals, outcomes, and remaining work |
| `AI_USAGE.md` | AI contributions, corrections, and limitations |
| `REVISIONS.md` | Preserved versions and reasons for each change |
| `data_generator.py` | Seeded IDs, queries, known answers, and workload settings |
| `search_original.py` | First manual version, retained for comparison |
| `search.py` | Revised manual procedures, public methods, and version registry |
| `test_search.py` | Same correctness requirements for all six variants |
| `test_data_generator.py` | Workload, known-answer, and reproducibility checks |
| `benchmark.py` | Timing/memory matrix, raw samples, summaries, and provenance |
| `verify_results.py` | Recomputes summaries from raw samples and checks provenance/links |
| `dashboard.py` | Validates and embeds saved results into the HTML template |
| `dashboard_template.html` | Editable dashboard structure, styles, and filter logic |
| `dashboard.html` | Generated, self-contained dashboard to open in a browser |
| `results/timing.csv`, `results/memory.csv` | Per-configuration timing and memory summaries |
| `results/timing_raw.csv`, `results/memory_raw.csv` | All raw repeat values, joined by case ID |
| `results/environment.json` | Run settings, protocol, environment, and source hashes |
| `results/SUMMARY.md`, `results/README.md` | Measured findings, field definitions, and provenance |
| `results/qa/` | Browser-check outcomes identified by measurement run ID |
| `results/history/` | Automatically preserved earlier saved results |
| `archive/pre_revision/` | Hash-verified snapshot before this revision batch |

## Commands from the repository root

These instructions are not permission for an agent to run commands. The user
must approve each new batch; the current batch explicitly authorizes the
expanded comparison, revisions, measurements, and dashboard.

Run correctness tests (currently 17 test methods; search cases cover both versions):

```bash
python3 -m unittest discover -s Submissions/HardiKhushi -v
```

Run the full experiment and rebuild the dashboard:

```bash
python3 Submissions/HardiKhushi/benchmark.py
```

Run a smaller experiment with the same measurement protocol:

```bash
python3 Submissions/HardiKhushi/benchmark.py --sizes 1000 10000 --queries 100 --scenarios mixed --duplicate-policies unique --repeats 5 --seed 42
```

Each benchmark run archives existing root result files under `results/history/`
before replacing them. All outputs use paths relative to the scripts, regardless
of the working directory. Rebuild only the dashboard, without new measurements:

```bash
python3 Submissions/HardiKhushi/dashboard.py
```

Verify saved sample counts, statistics, source/archive hashes, and dashboard links:

```bash
python3 Submissions/HardiKhushi/verify_results.py
```

The current dashboard was checked in headless Chrome at 1,440-pixel desktop and
500-pixel narrow widths: all 72 filter combinations passed in each layout,
including displayed values against saved data and absence of page overflow.
This is not a claim of testing every browser or screen size. Temporary browser
profiles and screenshots live in ignored `.preview/`, outside saved measurements.

Preview a small synthetic workload (prints JSON and writes no files):

```bash
python3 Submissions/HardiKhushi/data_generator.py --n 10 --queries 6 --seed 42
```

## Synthetic data and search contract

`generate_workload(n, q, *, seed=42, scenario="mixed", duplicate_policy="unique")`
returns a workload with IDs, ordered queries, known answers, and settings.
It imports no search/measurement code. `unique` IDs are a shuffle of 0 through
n-1. `repeated` IDs cycle through ceil(n/2) distinct IDs before shuffling. Query
sampling allows repetitions. Present and absent values come from disjoint
ranges, so expected answers are known without calling a search implementation.

Mixed batches contain ceil(q/2) hits, then query order is shuffled. Thus q=1
mixed has one hit; use the all-absent scenario to test a miss. A local
`random.Random(seed + n)` reproduces inputs without changing global randomness.
Settings record seed/effective seed, generator version, actual hit rate, and
ID/query duplicate policies. The same workload objects are shared across every
method and version. Empty input with nonempty present queries is impossible
and is rejected by the generator; empty inputs are covered by correctness tests.

All methods return one Boolean per query in its original position, preserve
both inputs, and handle duplicates, negative IDs, and unsorted arrays. Their
preparation/query state is reusable without mutation. Tests cover these cases,
randomized independent answers, and all scenario/duplicate-policy combinations.
Passing tests provide evidence, not proof of correctness.

## Timing definitions

- Input generation, correctness checks, printing, dashboard work, memory tracing,
  and profiling are excluded from timing. `perf_counter_ns` measures elapsed
  time, reported in milliseconds per complete preparation/query-batch/total call.
- A correctness preflight warms each configuration; per-phase calibration
  selects a batch count targeting 5 ms, capped at 65,536 executions. Five timed
  batches follow. Each raw elapsed value is divided by its execution count;
  summaries report median/min/max of those five per-execution values.
- **Preparation:** creates fresh state on each execution, including sorting or
  set construction. Revised linear preparation just references the existing IDs.
  Within a batch, replacement also includes release of the previous state.
- **Query batch:** prepares fresh state before each repeat, outside the clock;
  queries reuse that state within the repeat. The result includes all q answers,
  not a single query unless q=1.
- **Total:** creates fresh state and answers every query on each execution.
  It is independently measured and need not equal the sum of phase medians.
- Timing batches include normal loop/call and allocation/lifecycle overhead.
  No timer-overhead subtraction or confidence intervals are claimed.

## Memory definitions and provenance

Memory is measured in five separate fresh `tracemalloc` sessions, after inputs
already exist. Each session prepares state and answers one full query batch.
Current and peak bytes are read with prepared state and output still alive.
This includes new sorted lists/hash tables, defensive copies, temporary Python
allocations, and results; it excludes pre-existing input storage. Referencing
an existing input in revised linear search does not allocate another input list.

Tracing is not process RSS, does not capture every native allocation, and does
not directly equal theoretical auxiliary space. The dashboard converts bytes
to KiB (1,024 bytes). Version, workload settings, run/case IDs, raw repeats,
Python/machine details, and source hashes make results auditable even while the
submission is uncommitted. The source hash covers search, original search,
generator, and benchmark; dashboard/documentation changes do not alter it.

This is one seed on one machine. Original and revised versions run sequentially;
cache warmth, allocator state, and system scheduling can affect ratios. No
universal fastest method is claimed. The checkpoint's clean staged export passed
all tests, saved-results verification, and a deterministic dashboard rebuild.
The checkpoint is published at
<https://github.com/khushihardi/AlgorithmsFinance/tree/submission/hardi-khushi/Submissions/HardiKhushi>.
Direct writes to the course repository were denied, so `origin` remains the
course repository and `fork` points to this student-owned fork. The local
`submission/hardi-khushi` branch tracks `fork/submission/hardi-khushi`.
The published branch includes checkpoint `3ba5b42`; see progress entry 7 for
publication details. A pull request is still needed for course integration.
A full benchmark rerun from a fresh clone and the Phase 2 audit remain separate
steps. Docker is optional.
