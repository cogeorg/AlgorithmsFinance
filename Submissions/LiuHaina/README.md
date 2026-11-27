# Algorithms in Finance Lab — Liu Haina

## Report language
All submitted reports, dashboard labels, chart annotations, tables, and project
documentation are presented in English.

## Goal and interface
Both `search_original.py` (original) and `search.py` (revised) provide:
- `linear_search(array, queries)`
- `binary_search(array, queries)` (search a sorted copy)
- `hash_set_search(array, queries)` (standard-library set membership)

Each accepts an integer ID list and ordered query list and returns a list
containing one Boolean per query in query order. Leave the input array unchanged.
Use the same interface for original and revised versions.

## Run tests
No third-party dependencies are required; the suite uses Python's `unittest`.
From the repository root:

```bash
cd Submissions/LiuHaina
python3 -B -m unittest -v test_search
```

To run the same suite against both versions:

```bash
python3 -B run_tests.py
```

Use `--version original` or `--version revised` to select one version.

The suite contains 13 test methods, each checking all three algorithms.
It covers empty inputs, a single entry, duplicates, unsorted data, query order,
Boolean output types, present/absent queries, binary-search boundaries, integer
values, unchanged input, and independent repeated calls.

## Test-first baseline
Before implementation, the suite ran and produced 39 subtest failures for
missing functions; the saved output is in `test_baseline.txt`. After implementing
all three methods, the unchanged suite passes: 13 test methods, each checking
three algorithms. See `test_implementation.txt` for the run output, Python
version, and test-file hash. No expected results were weakened. Passing tests
provide evidence of correctness, not a proof.

Linear search and iterative binary search are implemented directly in Python.
Binary search uses `sorted(array)` to preserve the input. Hash-set membership
uses the standard-library `set`. Sorting and set construction currently happen
inside each complete call for nonempty inputs; later benchmarks must account
for these costs.

## Revision
The original is preserved in `search_original.py`. The revised `search.py`
returns early for empty inputs. Both versions pass the unchanged 13-test suite.
See `REVISION.md` for the change, reasoning, and performance limitations, and
`test_revision.txt` for saved validation output. Performance is measured separately as described below.

## Shared synthetic inputs
Run from this submission directory (no third-party packages required):

```bash
python3 -B generate_data.py --seed 42 --include-empty-queries
python3 -B validate_data.py
```

`generate_data.py` saves `data/inputs.json`. It does not import algorithms or
measure time. `validate_data.py` independently checks expected answers using
set membership, regenerates the dataset to check reproducibility, and checks
both algorithm versions on the saved inputs. Its execution log is saved in
`data_validation.txt` for this run.

The file contains three shared arrays (n = 1,000, 10,000, 100,000), 15 feasible
required cases (q = 1 or 100), and three supplementary q = 0 cases. Queries are
all-present, all-absent, or mixed with exactly 50% hits. A single query cannot
contain both a hit and a miss: the three infeasible q = 1 mixed combinations
are explicitly listed in `skipped_cases`, not labelled as mixed measurements.
Supplementary empty-query cases let later measurements inspect the revision;
their hit rate is null because there is no defined fraction for zero queries.

Array IDs are sampled with replacement from range(n//2), allowing duplicates.
Hit queries sample array positions (so frequent IDs are more likely); misses
are negative and guaranteed absent. Queries may repeat, and query order is
shuffled using a dedicated fixed seed. The JSON records seeds, seed rules,
generator settings, actual hit rates, distinct counts, Python version, and array
hashes. Each case references a saved array by ID, avoiding multiple copies of
the same input in the file. The saved values are authoritative for comparisons.

Later measurement scripts must load this file before timing and give all
methods and versions identical input values. Keep JSON loading, generation,
validation, and copying outside timed regions. Include actual algorithm
preparation (sorting/set construction) in preparation and total time.
Timing and memory measurements use these saved inputs as described below.

## Runtime and memory measurements
From this submission directory, run:

```bash
python3 -B benchmark.py
```

This loads `data/inputs.json` before timing and runs all 18 cases against both
versions and all three methods (108 configurations). Results are saved to:

- `results/timing_raw.csv`: five raw repeats for each of three timing metrics.
- `results/timing_summary.csv`: median, minimum, and maximum per-batch seconds.
- `results/memory.csv`: current and peak traced bytes in a separate memory run.
- `results/metadata.json`: run ID, environment, generator settings, input/source
  SHA-256 hashes, checked-out commit, and exact measurement definitions.

`--output-dir PATH` can select a different result directory; the default files
are replaced when the script is rerun. No third-party packages are needed.
Local source hashes identify measured code even before a submission commit.

### Timing definitions
`preparation` calls the actual `prepare_*` functions, including sorting or set
construction and the revised empty-input checks. Linear preparation returns the
input reference. `query_batch` calls the actual `query_*` functions for the
entire ordered query list. `total` independently calls the public end-to-end
function, including fresh preparation for every invocation. Because these are
independent experiments, their medians need not add exactly.

Each metric is warmed up and calibrated, then repeated five times using
`time.perf_counter()`. Very short calls are grouped toward 3 ms (capped at
8,192 calls); group elapsed seconds divided by call count gives seconds per
complete batch. Raw group times and call counts are saved. Query-only state is
fresh for every recorded repeat and reused read-only inside its call group;
preparation and end-to-end groups rebuild state on every invocation.
Loop/function overhead and release of earlier results in a group are included;
the final result stays alive until after timing. Sub-microsecond differences
are sensitive to overhead and should not be treated as reliable speed claims.
Configuration order is shuffled with fixed seed 2026; five repeats of a metric
run consecutively. Background machine load can still affect comparisons.

Input generation/loading/copying, validation, printing, memory tracing,
profiling, and dashboard rendering are outside timed regions. The script checks
expected outputs and stage equivalence before timing and validates timed
outputs after each recorded group.

### Memory definitions
After all timing, each configuration gets one fresh `tracemalloc` run. Input
arrays and queries already exist and are excluded. Preparation runs inside the
trace, and prepared state and output are both kept alive while reading current
and peak bytes. Thus sorted copies/set allocations and output are included.
These are traced Python allocations, not process RSS, every native allocation,
or auxiliary space alone. No timing or profiling runs during memory tracing.

### Source snapshots and stage extraction
To measure phases without duplicating search implementations in the benchmark,
`search_original.py` and `search.py` expose `prepare_*` and `query_*` helpers.
Their public function names and input/output contracts are unchanged. Previous
source is preserved byte-for-byte in `snapshots/`. In the revised version, the
empty-input condition is handled during preparation; a `None` state signals
that every query is absent (or there are no queries). Output is constructed in
the query phase. Both staged versions and both snapshots pass the unchanged
13-test suite; see `test_stages.txt`. Measurements describe the staged versions,
whose extra helper calls can affect very short cases. The revised snapshot
returned an empty result directly, so its absolute timings need not match.

## Offline dashboard
From this submission directory:

```bash
python3 -B dashboard.py
```

Open `dashboard.html` in a browser (on macOS, run `open dashboard.html`, or
right-click the file in VS Code, reveal it in Finder, and double-click it).
The dashboard is a standalone HTML file with embedded saved results, SVG
charts, and JavaScript. It works offline, needs no server or third-party
packages, and can be shared as one file.

- Filter query count, hit scenario, versions, and methods. Choose seconds,
  milliseconds, or microseconds per complete batch, and optional log time axes.
- View separate preparation, query-batch, and total-time charts against n,
  with method colors and solid/dashed version lines. Hover points for details.
- Compare original/revised medians and inspect the full timing summary.
- View current/peak memory in KiB, with explicit inclusion labels.
- Inspect all five raw repeats and download filtered CSVs.
- Inspect environment, seeds, source hashes, skipped cases, and download all
  embedded measurements as JSON.

Query-count filters only offer feasible scenarios. q=0 is explicitly marked
as supplementary with an undefined hit rate; q=1 does not offer mixed queries.
Ratios are observations from this run, not guarantees of stable speedup.

`dashboard.py` loads only saved CSV/JSON files and `dashboard_template.html`;
it does not import or invoke algorithms, data generation, or benchmarks.
It verifies consistent run IDs/counts and recomputes summary medians from the
raw repeats. If measured source hashes differ from current local source, a
warning identifies the mismatch while preserving the historical measurements.
After new benchmark results, rerun the builder to refresh the HTML snapshot.
`--results-dir PATH --output PATH` selects another result set/destination.
`dashboard_validation.txt` records browser verification for the current page.
The dashboard and scripts use only Python's standard library plus browser-native
HTML/CSS/JavaScript. No pip dependencies are required. Development-only browser
checks used an existing Playwright installation and are not required to run it.

## English experiment report
Read `REPORT.md` for correctness evidence, experiment design, measured timing and
memory tables, revision results, limitations, reproduction commands, and the
AI assistance statement. Tables are generated directly from saved measurements.

```bash
python3 -B build_report.py
```

This checks result consistency and source hashes, updates the report, and saves
its table extracts and source-result hashes in `results/report_tables.json`.
It does not rerun benchmarks. `report_validation.txt` records report checks.

## Reproducibility verification
The full seven-command workflow was run successfully in an isolated copy of
the local repository, excluding Git metadata, scratch files, virtual
environments, and caches. See `REPRODUCIBILITY.md` for the command summary and
`reproducibility.json` for complete captured output and checks.

Both versions passed their correctness suites. The fixed-seed regenerated
input matched the saved dataset byte-for-byte. All 108 benchmark configurations
completed, and the English dashboard and report regenerated from the new
measurements. Original saved measurements were preserved. This check uses
local files; a fresh remote-clone check still depends on committing and pushing
the submission.

Report winner counts are computed from saved results rather than fixed prose,
so regenerating measurements also updates those findings.

## Next steps
1. Review the report, code, reasoning, and AI assistance statement.
2. Commit and push the project, recording the commit to be audited.
3. Follow the course submission instructions and complete the Phase 2 peer audit.

## AI assistance
Codex created the initial project skeleton and drafted the shared correctness
tests and this run guide, implemented the three initial algorithms, and ran the
unchanged suite, then proposed and implemented the empty-input revision. Codex also wrote the data generator and validation script and saved shared inputs.
Codex also extracted measurement stages, wrote the benchmark script, and ran
timing and separate traced-memory measurements.
Codex also created the offline dashboard and its saved-data builder.
Codex also wrote the English experiment report and its data-driven builder.
The student should review and record which suggestions are
accepted, corrected, or rejected as work progresses.
