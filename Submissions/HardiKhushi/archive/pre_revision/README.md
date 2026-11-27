# HardiKhushi — Search methods

Self-contained submission for *Algorithms in Finance*. All source files,
documentation, tests, and generated results for this work live in this folder.
Python 3.10 or newer is sufficient; no third-party packages are required.

**Status: work in progress.** The existing CSVs are preliminary measurements of
the initial library-based search implementations. The assignment requires manual
linear and binary search, original/revised versions, separate preparation/query/
total timing, and raw repeats. These are not complete yet. See `PROGRESS.md` for
the detailed checklist and `AGENTS.md` for the working agreement.

## Files

| File | Purpose |
| --- | --- |
| `README.md` | Setup, commands, and measurement definitions |
| `AI_USAGE.md` | Disclosure of AI assistance |
| `AGENTS.md` | Working rules and command approval requirements |
| `PROGRESS.md` | Work history, decisions, checks, and remaining requirements |
| `search.py` | Linear, binary, and set-based membership search |
| `test_search.py` | Correctness and input-preservation tests for all methods |
| `data_generator.py` | Separate, seeded workload generator with a preview command |
| `test_data_generator.py` | Generator settings, known-answer, and reproducibility checks |
| `benchmark.py` | Uses the generator; measures runtime and memory separately |
| `results/timing.csv` | Preliminary measured batch runtime in milliseconds |
| `results/memory.csv` | Preliminary measured peak traced allocation in bytes |
| `results/README.md` | Provenance and limits of the saved measurements |
| `dashboard.py` | Builds the offline dashboard from both CSV files |
| `dashboard.html` | Charts, result table, and links to the CSV files |

## Commands from the repository root

These instructions do not grant an agent permission to execute commands.
Ask before each new batch. Test discovery includes 7 search tests and 6 generator
tests (13 total).

```bash
python3 -m unittest discover -s Submissions/HardiKhushi -v
```

Open `Submissions/HardiKhushi/dashboard.html` in a browser. It works offline
without a web server or dependencies. The benchmark refreshes both CSV files
under `results/` and the dashboard in this folder, regardless of the current
working directory. Running it overwrites existing measurements; request approval
and preserve the preliminary results before a future benchmark run.
To rebuild the dashboard from existing CSVs without rerunning measurements:

```bash
python3 Submissions/HardiKhushi/dashboard.py
```

Custom benchmark example (not executed during the organization/generator step):

```bash
python3 Submissions/HardiKhushi/benchmark.py --sizes 1000 5000 10000 --queries 200 --repeats 5 --seed 42 --scenario mixed --duplicate-policy unique
```

## Synthetic-data generation

`data_generator.py` does not import search or measurement code. It returns a
`Workload` containing `ids`, ordered `queries`, known `expected` answers, and
`settings`. The benchmark creates this once per size, before measurements, and
passes the same inputs to every method.

Small preview command (prints JSON, writes no files):

```bash
python3 Submissions/HardiKhushi/data_generator.py --n 10 --queries 6 --seed 42
```

The Python API is `generate_workload(n, q, seed=42, scenario="mixed",
duplicate_policy="unique")`; the last three arguments are keyword-only.

- `unique` IDs are shuffled integers from 0 through n-1. `repeated` IDs cycle
  through ceil(n/2) distinct integers before shuffling, producing duplicates
  when n is at least 2. Shuffling does not guarantee the result is unsorted.
- `all-present` and `all-absent` give known 100% and 0% hit rates. `mixed` gives
  ceil(q/2) hits and floor(q/2) misses, then shuffles query order. For q=1,
  mixed means one hit; using both endpoint scenarios still tests hits and misses.
- Queries are sampled with replacement, so repeated queries are allowed.
- Present values and absent values come from disjoint ranges, so expected
  answers are known without invoking an implementation under test.
- A local `random.Random(seed + n)` keeps generation repeatable without changing
  global random state. Settings record the effective seed, generator version,
  sizes, actual hit rate, distinct-ID count, and duplicate/query policies.
- Empty inputs and queries are supported. Nonempty present/mixed queries with
  no IDs are rejected because a present query would be impossible.

The default workload matches the original benchmark's arrays and queries. The
existing CSVs were not regenerated. Future benchmark runs write the new generator
settings as additional CSV columns; old CSVs retain their original schema.

## Search contract and costs

Each function accepts a list of integer IDs and a list of integer queries,
returning one Boolean per query in the original query order. Neither input is
modified. Duplicate IDs, repeated queries, unsorted IDs, and empty inputs work.

For `n` IDs and `q` queries:

| Method | Work per batch, including preparation | Extra space excluding results |
| --- | --- | --- |
| Linear | Worst-case O(nq) | O(1) |
| Binary | O(n log n + q log n) | O(n), including copied/sorted IDs |
| Set | Expected O(n + q) | O(n) |

Every method also allocates an O(q) result list. Set lookup costs are expected
costs and depend on hashing. The implementations use Python's built-in list
membership, `sorted`/`bisect_left`, and `set` operations.

## Measurement protocol

Defaults: 1,000, 5,000, and 10,000 unique shuffled IDs, 200 queries per batch,
five repeats, and seed 42. Half the queries are present and half absent; odd
query counts have one extra present query. Queries may repeat. All three
methods receive the same inputs at each size. A fixed seed reproduces the
workload; elapsed times vary between runs.

Each method gets one untimed correctness check/warm-up per input size.
`perf_counter_ns` measures each full batch, including sorting or set construction
and result creation. Input generation and correctness checks occur outside the
timed region. `results/timing.csv` reports median, minimum, and maximum milliseconds.

Memory uses separate `tracemalloc` runs to avoid tracing overhead in timing.
`results/memory.csv` reports median, minimum, and maximum peak newly traced bytes during
each complete call, including results and temporary structures. Existing input
lists are excluded. This is Python allocation tracing, not process RSS.
Both CSVs record workload settings, Python version, platform, and UTC timestamp.

The dashboard displays measured values from these CSVs. It supports the original
CSV schema and new generator-setting columns. The original mixed/unique settings
are explicitly identified when those columns are absent. The results describe
this machine and workload; they do not establish performance for every dataset.
After approval for new measurements, regenerate the dashboard and CSVs together
with `benchmark.py`. The present dashboard rebuild used saved CSVs only.
