# Phase 1: Three Methods, One Specification

Author: Peng Huize

This project compares linear search, binary search on a sorted copy, and
membership queries using Python's standard-library hash set. Development used
a test-first workflow and preserves both the original recursive binary search
and the revised iterative version.

## Project files

- `algorithms.py`: preparation/query layers and all algorithm versions.
- `synthetic_data.py`: deterministic integer IDs and ordered queries.
- `test_algorithms.py`: one shared correctness specification for every method.
- `test_synthetic_data.py`: generator, scenario, and duplicate-policy tests.
- `benchmark.py`: fixed-input timing and `tracemalloc` measurements.
- `dashboard.py`: Streamlit view of saved results; it never reruns benchmarks.
- `results/`: raw repeats, median summaries, and environment details.
- `requirements.txt`: pinned Python dependencies.

## Setup

From `Submissions/PengHuize/`:

```bash
python3 -m pip install -r requirements.txt
```

Python 3.9 or newer is required.

## Correctness tests

```bash
python3 -m pytest -q
```

Expected result before the benchmark/dashboard files are added to the test
suite:

```text
51 passed
```

The shared tests cover empty inputs, one entry, duplicates, unsorted input,
present and absent queries, repeated queries, Boolean output, output order,
and an unchanged input array. Passing tests are evidence of correctness, not a
formal proof.

## Algorithm versions and revision

All public methods accept an integer ID sequence and ordered queries, return
one Boolean per query in the same order, and leave the input unchanged.

- Linear search scans IDs from left to right for each query.
- Original binary search sorts a copy and recursively halves the search range.
- Revised binary search sorts a copy and iteratively halves the search range.
- Hash-set search builds a standard-library set and performs membership tests.

The revision replaced recursive binary search with an iterative loop. It keeps
the same `O(log n)` query complexity after sorting, avoids recursive calls, and
is easier to benchmark without function-call recursion overhead. Both versions
are preserved and run through the same tests and fixed-input experiments.

## Synthetic data

`generate_synthetic_data` uses a local `random.Random(seed)` instance. Equal
settings and seeds reproduce equal datasets without modifying global random
state. The full benchmark uses:

- array lengths `n = 1,000`, `10,000`, and `100,000`;
- query counts `q = 1` and `100`;
- all-present (`hit_rate=1.0`), all-absent (`0.0`), and mixed (`0.5`) queries;
- `allow_duplicates=True`, recorded explicitly in every saved row;
- identical generated inputs for every method and version in one configuration.

## Runtime and memory measurements

Run a small smoke experiment:

```bash
python3 benchmark.py --quick
```

Run the required full experiment:

```bash
python3 benchmark.py
```

The benchmark warms up each method, repeats every measurement five times, and
reports medians. `time.perf_counter()` records seconds per complete query
batch. Very short operations are executed several times and divided by the
inner-loop count. Fresh preparation state is created for every recorded
repeat; total-time inner loops also prepare from scratch.

Definitions:

- **Preparation:** no-op for linear search, sorting a copy for binary search,
  or constructing the hash set.
- **Query batch:** all `q` ordered queries against already prepared state.
- **Total:** fresh preparation plus the complete query batch.

Data generation, tests, printing, dashboard rendering, memory tracing, and AI
calls are outside the timed regions. Raw repeat values and inner-loop counts
are saved in `results/raw_timings.csv`; medians and memory values are saved in
`results/summary.csv`.

Memory is measured in a separate run with `tracemalloc`. Inputs and queries are
built before tracing. Prepared structures and returned output stay alive when
current and peak traced bytes are read. These values cover Python allocations,
not every native allocation, and do not directly equal theoretical auxiliary
space.

## Dashboard

After saved results exist, run:

```bash
python3 -m streamlit run dashboard.py
```

The dashboard loads the saved CSV/JSON files. It displays preparation,
query-batch, and total time separately; compares every method and both binary
versions; shows query count, scenario, hit rate, units, memory measurements,
raw repeats, and environment details.

## AI-use record

AI assistance was used for project scaffolding, test review, benchmark design,
and documentation. Accepted suggestions included deterministic seeds, shared
tests, preserving recursive and iterative versions, and separating preparation
from queries. The initial generator design was corrected to expose an explicit
duplicate policy, and timing output was revised to retain raw repeats and inner
loop counts. Optional Docker packaging and `psutil` RSS sampling were not used
because they are outside the required scope. The student ran the tests,
inspected failures, corrected indentation/decorator placement, and verified the
Git workflow.

## Reproducible audit version

The measured source snapshot to audit is commit
`b7289538b761aceb086c921a190fb874f1f2331d`. It contains the full algorithms,
tests, benchmark, dashboard, dependencies, and saved results. The source hash
and run-time Git state are retained in `results/environment.json`. Reviewers
can run tests, the benchmark, and the dashboard without editing source files.
