# Algorithms in Finance — Phase 1

## Objective and Functional Specification

This project implements, tests, measures, and compares three approaches to
ordered membership queries over integer IDs:

1. Manual Linear Search
2. Manual Binary Search on a sorted copy
3. Python standard-library hash-set membership

Each public method accepts an integer ID sequence and an ordered integer query
sequence. It returns exactly one Boolean per query in the original query order
and leaves the input array unchanged.

```python
array = [7, 11, 7]
queries = [11, 9, 7]
expected = [True, False, True]
```

## Development Status

| Stage | Status |
|---|---|
| 1. Repository Setup | Completed |
| 2. Synthetic Data Setup | Completed and tested |
| 3. Test Development | Completed; test-first failure recorded |
| 4. Algorithm Implementation and Revision | Completed; all tests pass |
| 5. Performance Benchmarking | Completed with raw repetitions |
| 6. Memory Measurement | Completed with `tracemalloc` |
| 7. Streamlit Dashboard | Implemented and startup-validated |
| 8. Documentation and Reproducibility | Completed, except final audited commit ID |

No Git commit, push, or Pull Request was created by AI assistance.

## Repository Structure

```text
ErtenZeynep/
├── README.md
├── AGENTS.md
├── requirements.txt
├── 01_source/
│   └── algorithms_finance/
│       ├── data_01_generation.py
│       └── algorithms/
│           ├── algorithm_01_linear_search.py
│           ├── algorithm_02_binary_search_recursive.py
│           ├── algorithm_03_binary_search_iterative.py
│           └── algorithm_04_hash_set_membership.py
├── 02_tests/
│   ├── conftest.py
│   ├── test_01_data_generation.py
│   ├── test_02_search_contract.py
│   ├── test_03_algorithm_failure_modes.py
│   └── test_04_randomized_differential.py
├── 03_measurements/
│   ├── measurement_01_benchmarks.py
│   └── measurement_02_memory.py
├── 04_results/
│   ├── benchmarks/
│   ├── memory/
│   └── metadata/
├── 05_dashboard/
│   └── dashboard_01_app.py
└── 06_documentation/
    ├── 01_methodology.md
    ├── 02_revision_history.md
    ├── 03_ai_assistance.md
```

## Algorithms

### Linear Search

Each query manually scans the array from left to right and stops at the first
match. Preparation is `O(1)`, a complete query batch is `O(nq)`, and no
prepared auxiliary structure is allocated.

### Recursive Binary Search — Original

Preparation creates a sorted copy in `O(n log n)` time and `O(n)` memory. Each
query uses a manually implemented recursive Binary Search in `O(log n)` time
with an `O(log n)` call stack. The caller's array is not sorted in place.

### Iterative Binary Search — Revised

The preserved revision replaces recursion with a `while` loop. Preparation and
asymptotic query time remain the same, but the search removes recursive call
overhead and uses `O(1)` search-state memory beyond the sorted copy.

### Hash Set Membership

Preparation constructs a fresh Python `set` in average `O(n)` time and `O(n)`
memory. The ordered query batch takes average `O(q)` time.

Every module exposes separate preparation and prepared-query functions so that
benchmarking can measure preparation, query-batch, and total time fairly. The
public wrapper retains the shared `(array, queries) -> list[bool]` contract.

## Synthetic Data

The mandatory matrix contains all 18 combinations:

- `n ∈ {1_000, 10_000, 100_000}`
- `q ∈ {1, 100}`
- `scenario ∈ {all_present, all_absent, mixed}`

Mandatory arrays sample with replacement from `[0, 10n)`. Duplicates are
allowed but not forced. `duplicate_count` is `n - len(set(array))`, and
`duplicate_rate` is `duplicate_count / n`.

Absent queries use within-range gaps by default. An optional balanced
outside-range policy is available as a separately labeled stress case. Optional
array profiles include all-unique, all-identical, and high-duplicate inputs.

For `q=100`, mixed batches contain exactly 50 present and 50 absent queries. A
true mixed batch is impossible for `q=1`; seed parity deterministically selects
one present or absent query, and metadata records target hit rate `0.5`, actual
hit rate `1.0` or `0.0`, and `is_true_mixed_batch=false`.

Array and query RNGs are separate local `random.Random` instances. Final seeds,
generator version, duplicate metrics, actual hit rate, environment information,
and SHA-256 input fingerprints are recorded. Data generation is excluded from
all timing measurements.

## Setup

The measured environment used CPython 3.13.17 on Windows 11 AMD64. The root
`requirements.txt` is the canonical dependency file. From a fresh checkout,
create an isolated environment and install the pinned dependencies.

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux or macOS:

```bash
python3.13 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

Pinned direct dependencies:

- pytest 9.2.0
- Streamlit 1.67.0
- pandas 3.1.1

## Testing

The test suite covers the shared contract, empty/minimal inputs, duplicates,
unsorted arrays, integer extremes, input immutability, Binary Search boundaries,
realistic failure modes, 100 seeded randomized cases per algorithm, and
synthetic-data reproducibility.

Before algorithm implementation, the minimal shared contract run produced four
setup errors because all four required modules were absent. This honestly
records the test-first red state. After implementation, the complete suite
passed:

```text
553 passed in 13.27s
```

Run the suite:

```powershell
.\.venv\Scripts\python.exe -m pytest 02_tests -q -p no:cacheprovider
```

## Synthetic-Data Generation Check

Generate the 18 mandatory cases outside benchmark timing:

```powershell
$env:PYTHONPATH = "01_source"
.\.venv\Scripts\python.exe -c "from algorithms_finance.data_01_generation import generate_mandatory_cases; print(len(generate_mandatory_cases()))"
```

Expected output: `18`.

## Runtime Benchmarking

Run:

```powershell
.\.venv\Scripts\python.exe 03_measurements\measurement_01_benchmarks.py
```

The benchmark uses `time.perf_counter()`, one warm-up, five repetitions, fresh
preparation per repetition, rotating method order, and medians. Very short
operations are measured across multiple calls and normalized. Preparation,
complete query-batch, and total (`preparation + query batch`) seconds are saved
separately. Data generation, tests, printing, AI calls, memory tracing,
profiling, and dashboard rendering are excluded.

Outputs:

- `04_results/benchmarks/result_01_raw_repetitions.csv` — 360 raw rows
- `04_results/benchmarks/result_02_median_summary.csv` — 72 summaries
- `04_results/metadata/result_01_environment.json` — environment/methodology

## Measured Runtime Results

Across the 18 mandatory configurations:

- Linear Search had the lowest measured total time in all nine `q=1` cases.
- Hash Set Membership had the lowest measured total time in all nine `q=100`
  cases.
- Iterative Binary Search had a lower median query-batch time than recursive
  Binary Search overall at each required `n`; the median iterative/recursive
  ratios were approximately `0.908`, `0.767`, and `0.740` for `n=1,000`,
  `10,000`, and `100,000`, respectively.

For `n=100,000`, `q=100`, mixed queries:

| Method | Preparation (s) | Query batch (s) | Total (s) |
|---|---:|---:|---:|
| Hash Set Membership | 0.017976 | 0.000005 | 0.017981 |
| Iterative Binary Search | 0.032595 | 0.000251 | 0.032959 |
| Recursive Binary Search | 0.038629 | 0.000496 | 0.039126 |
| Linear Search | <0.000001 | 0.545281 | 0.545281 |

These figures are machine- and environment-dependent observations, not
universal performance guarantees. Raw values must be consulted for auditing.

## Memory Measurement

Run separately from timing:

```powershell
.\.venv\Scripts\python.exe 03_measurements\measurement_02_memory.py
```

The input is built before each fresh `tracemalloc` session. Preparation and one
complete query batch are traced. The prepared structure and returned output are
alive when current and peak bytes are read.

For `n=100,000`, `q=100`, mixed queries:

| Method | Current traced bytes | Peak traced bytes |
|---|---:|---:|
| Linear Search | 920 | 1,016 |
| Iterative Binary Search | 800,920 | 1,199,952 |
| Recursive Binary Search | 800,976 | 1,199,952 |
| Hash Set Membership | 4,195,384 | 6,291,720 |

`tracemalloc` does not capture every native allocation or process RSS. These
measurements are not exact auxiliary-space complexity.

## Dashboard

The dashboard loads saved results and never reruns measurements when filters
change. It includes preparation, query-batch, and total-time charts; original
versus revised versions; hit-rate/query-count information; memory tables; raw
repetitions; and environment/code-version metadata.

```powershell
.\.venv\Scripts\python.exe -m streamlit run 05_dashboard\dashboard_01_app.py
```

The headless startup was validated successfully on port 8502. A Streamlit
`AppTest` smoke test also verifies that the dashboard renders without
exceptions, displays the expected title and tables, and exposes Preparation,
Query batch, and Total tabs.

## Clean-Environment Reproducibility Check

On 2026-11-20, the current project files were copied to a separate temporary
directory under the submission, and a new Python 3.13 virtual environment was
created without access to the previously installed project packages. The root
`requirements.txt` installed successfully and `pip check` reported no broken
requirements. In that clean copy:

- The complete suite passed: `553 passed in 13.27s`.
- The deterministic generator produced all 18 mandatory cases.
- The runtime script saved 360 raw rows and 72 median summaries.
- The memory script saved 72 rows.
- The Streamlit `AppTest` completed without dashboard exceptions.

The temporary copy and virtual environment were removed after verification.
No source-file or path edits were needed. An actual GitHub-clone test cannot be
performed until the user authorizes a commit and push, but the clean-copy run
verifies path independence and isolated dependency installation.

## Reproducibility and Code Version

The measurement environment file records base commit
`d6f72e7d48031785b0a9e7b2c462a2fe74758063-dirty`, correctly indicating that
measurements were made from an uncommitted working tree. This is not the final
audited commit. After the user explicitly authorizes and creates the final
commit, its exact identifier must replace or supplement this value in the
documentation.

Reproduction requires no manual source edits: install dependencies, run tests,
run the two measurement scripts, and launch the dashboard using the commands
above.

## AI Assistance

Material AI assistance is documented in
`06_documentation/03_ai_assistance.md`. No test, benchmark, memory, or dashboard
result is claimed unless the corresponding command was actually executed.

## Revision History

| Date | Change | Verification |
|---|---|---|
| 2026-11-20 | Initialized repository documentation and agent rules. | Structure inspected. |
| 2026-11-20 | Added deterministic synthetic-data generation. | 28 generator tests passed. |
| 2026-11-20 | Added test-first shared and randomized tests. | Initial four missing-module errors recorded. |
| 2026-11-20 | Added Linear, recursive/iterative Binary, and Hash Set methods. | Full suite passed. |
| 2026-11-20 | Added runtime and memory measurement scripts and raw results. | 360 timing rows and 72 memory rows saved. |
| 2026-11-20 | Added the saved-result Streamlit dashboard and documentation. | Clean environment: 553 tests passed; dashboard AppTest passed. |
