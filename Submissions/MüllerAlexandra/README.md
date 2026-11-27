# Membership search lab

This project compares three ways to answer an ordered batch of integer-ID
membership queries:

1. explicitly implemented linear search;
2. explicitly implemented binary search on a library-sorted copy; and
3. membership in a standard-library hash set.

The original binary search is recursive. The required revised version is
iterative, and both versions are preserved and measured. Every public method
returns one real Boolean per query in the original query order and leaves the
given ID array unchanged.

## Requirements

- Python 3.12 (measurements were developed with Python 3.12.10)
- Dependencies pinned in `requirements.txt`

Docker packaging is optional for this lab. A `Dockerfile` is provided for a
reproducible Python 3.12.10 environment; local Python setup remains supported.

## Setup on Windows PowerShell

From `Submissions/MüllerAlexandra`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The repository's root `.gitignore` excludes `.venv`, caches, and compiled
Python files.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected result: `58 passed`. The tests apply the same specification to linear
search, original recursive binary search, revised iterative binary search, and
hash-set membership. Cases cover empty IDs and queries, one entry, duplicates,
unsorted input, negative and zero IDs, present and absent queries, output
order, Boolean output types, and preservation of the input array. Additional
tests cover deterministic synthetic data, benchmark interfaces, measurement
smoke runs, and dashboard data transformations.

The first test run occurred before implementation: 27 algorithm tests failed
with `NotImplementedError`, while 12 generator tests passed. After the original
three implementations, all 39 tests passed. The final suite has 58 passing
tests. See `DEVELOPMENT_NOTES.md` for the hand trace, revision, and AI-use log.

## Synthetic data

`synthetic_data.py` is independent of algorithms, measurement, and rendering.
It uses a private seeded `random.Random` instance. Each saved result records:

- input length and query count;
- seed;
- requested and actual hit rate;
- query scenario; and
- duplicate policy.

The default benchmark uses `duplicate_policy="allow"`, which deliberately
generates IDs from a smaller value range and therefore includes duplicates.
A genuinely mixed query batch is impossible when `q=1`, so that one
combination is explicitly omitted and recorded in the saved settings. Mixed
queries are included for `q=100`.

## Benchmark

First commit the algorithms, tests, generator, benchmark, dashboard, dependency
file, and documentation. Supply that code commit's hash to the measurement
command:

```powershell
.\.venv\Scripts\python.exe benchmark.py --code-version <MEASURED_CODE_COMMIT>
```

Do not include the angle brackets. The default fixed matrix is:

- `n` in `{1,000, 10,000, 100,000}`;
- `q` in `{1, 100}`;
- all-present and all-absent batches for both query counts;
- 50% mixed batches for `q=100`;
- duplicate policy `allow`; and
- base seed `20261120`.

The script warms up each method, then performs five repeats and reports the
median. Calls too short for useful direct timing are executed together and
divided by the number of calls; the loop count is stored with every record.
Every method/version receives the identical generated IDs and ordered queries
for a configuration.

Three elapsed quantities are measured independently with
`time.perf_counter()`:

- **preparation:** seconds per preparation; sorting or set construction is
  included, while linear search has no prepared structure;
- **query batch:** seconds per complete ordered query batch against the
  prepared state; and
- **total:** seconds per fresh preparation followed by one complete query
  batch.

The independent total can differ slightly from preparation plus query medians.
Data generation, tests, printing, AI calls, dashboard rendering, and memory
tracing are excluded. Fresh state is constructed inside every combined timing
call, so an earlier sorted copy or hash set is never treated as free.

Raw output is written to:

- `results/raw_benchmark.json` — raw repeats, medians, batching counts,
  generator settings, units and definitions, environment, and code version;
- `results/benchmark_summary.csv` — one flattened summary row per
  configuration and method/version.

### Results from the recorded run

The committed result files measure code version
`810f7db47cee7139bd585ce712e1f5218b19e129` with Python 3.12.10 on Windows 11.
They contain 60 records, five raw repeats per record, and no requested/actual
hit-rate mismatches.

For all-absent batches with `q=100`, median total time increased as follows:

| Method/version | n=1,000 | n=10,000 | n=100,000 |
|---|---:|---:|---:|
| Linear, original | 1.48 ms | 13.16 ms | 151.75 ms |
| Binary, recursive | 0.10 ms | 1.03 ms | 13.95 ms |
| Binary, iterative | 0.08 ms | 1.01 ms | 13.59 ms |
| Hash set | 0.01 ms | 0.14 ms | 2.74 ms |

The hash-set method had the lowest total median in every `q=100`
configuration. With only one query, the preparation cost changes the result:
linear search had the lowest total median in five of the six cases at
`n >= 10,000`, while the hash set narrowly won the `n=1,000` all-absent case.
This illustrates why both preparation and query count must be reported.

The iterative revision had a lower query-batch median than recursive binary
search in 14 of 15 configurations. It did not win every independently measured
total: for the `n=100,000`, `q=100`, mixed case, iterative query time was about
0.10 ms versus 0.12 ms recursively, but the recorded total was 15.69 ms versus
12.51 ms because sorting dominated and timing noise affected the independent
preparation/total measurements. The data therefore supports a narrower claim
about query-phase overhead, not a universal total-time speedup.

At `n=100,000`, peak traced memory was about 1,172 KiB for either binary
version, about 2,560 KiB for the hash set, and below 1 KiB for linear search in
these runs. These figures exclude the pre-existing input and queries but
include prepared structures and output as defined below.

## Memory measurement

Memory measurement is a separate run and is never mixed with timing. The input
and queries are generated before `tracemalloc.start()`, so their allocation is
excluded. Then a fresh preparation and complete query batch are run. The
prepared sorted copy or set and returned Boolean list remain alive when
`get_traced_memory()` reads current and peak traced bytes, so both are included.

`tracemalloc` reports traced Python allocations, not every native allocation,
and the measurement is not a direct proof of theoretical auxiliary-space
complexity. The dashboard displays current and peak values in KiB; the raw file
keeps bytes.

## Dashboard

Generate results first, then run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open the local URL shown by Streamlit (normally `http://localhost:8501`). The
dashboard loads `results/raw_benchmark.json`; changing filters never reruns a
benchmark. It shows separate preparation, query-batch, and total charts with
one curve per method/version, plus the memory table, raw repeats, loop counts,
seeds, settings, definitions, code version, and machine/Python details.

## Docker (optional)

Docker commands must be run from `Submissions/MüllerAlexandra`. The image uses
Python 3.12.10 and installs the exact direct dependency versions from
`requirements.txt`.

Build the image:

```powershell
docker build --tag algorithms-finance-mueller:phase1 .
```

Run all tests without editing files in the container:

```powershell
docker run --rm algorithms-finance-mueller:phase1 python -m pytest
```

Run the dashboard using the saved results packaged in the image:

```powershell
docker run --rm --publish 8501:8501 algorithms-finance-mueller:phase1
```

Open `http://localhost:8501` and stop the container with `Ctrl+C`.

To display host-side saved results instead, mount them read-only:

```powershell
$savedResults = (Resolve-Path .\results).Path
docker run --rm --publish 8501:8501 --mount "type=bind,source=$savedResults,target=/app/results,readonly" algorithms-finance-mueller:phase1
```

To run a new benchmark and save its output outside the temporary container,
create a host directory and bind-mount it at `/app/results`. Replace
`<CODE_VERSION>` with the commit hash being measured:

```powershell
New-Item -ItemType Directory -Force .\docker-results | Out-Null
$dockerResults = (Resolve-Path .\docker-results).Path
docker run --rm --mount "type=bind,source=$dockerResults,target=/app/results" algorithms-finance-mueller:phase1 python benchmark.py --code-version <CODE_VERSION>
```

Timing still describes the host machine and Docker resource limits. The
container does not make timings portable across machines.

The submitted Docker configuration was validated with Docker Desktop's Linux
engine: the image built successfully, all 58 tests passed inside the container
on Python 3.12.10, and the packaged dashboard rendered the saved results on
port 8501.

## Project files

- `algorithms.py` — original methods, preserved recursive binary search, and
  revised iterative binary search
- `synthetic_data.py` — deterministic input generation
- `benchmark.py` — timing, memory measurement, and saved result export
- `dashboard.py` — Streamlit result viewer
- `dashboard_data.py` — testable result-loading transformations
- `tests/` — shared behavioral and supporting tests
- `DEVELOPMENT_NOTES.md` — trace, revision rationale, and AI-use record
- `requirements.txt` — pinned direct dependencies
- `results/` — generated raw JSON and CSV measurements
- `Dockerfile` and `.dockerignore` — optional container packaging

## Interpretation limits

Passing tests provide evidence, not a proof of correctness. Runtime results
describe the recorded Python version, machine, host load, and measured code
version. They should not be generalized to every platform or input
distribution without further experiments.
