# Assignment 1: limit order book

This project implements and measures two Python versions of a sequential,
single-venue BTC limit order book. The transparent list-based Version A is
implemented and measured. The indexed FIFO-price-level Version B is implemented
and measured under the same behavioral contract, inputs, instrumentation, and
stopping limits.

## Submitted implementation

The submitted implementation is commit
`c4d1c2f70731685c377fc83ab83fedb9295d9b49`. The later documentation-only
commit that records this identifier does not change source code, tests,
measurements, or saved evidence.

## Environment

- Python 3.12.10
- Dependencies pinned in `requirements.txt`

From `Submissions/MüllerAlexandra/Assignment1`, create a fresh project-local
environment in Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest
```

The `.venv/` directory is ignored by Git. Python 3.11 or newer satisfies the
package requirement, while the saved verification and measurements use Python
3.12.10. On macOS or Linux, replace the launcher with `python3.12 -m venv
.venv` and use `.venv/bin/python` for the remaining commands.

## Replay one event file

Replay any plain `.jsonl` or gzip-compressed `.jsonl.gz` file with either
implementation:

```powershell
.\.venv\Scripts\python.exe scripts\01_replay.py `
  --version baseline `
  --input data\supplied\worked_example.jsonl
```

Use `--version revised` for Version B. By default the command prints one JSON
document containing every event result and the final canonical book. This
explicitly retains result history and can therefore be large. To create a new
file without replacing an earlier result, add `--out path\to\replay.json`.

## Test-first evidence

Use the evidence runner from the project root:

```powershell
.\.venv\Scripts\python.exe scripts\00_run_tests.py --stage 01_before_implementation
```

The runner records the exact command, output, exit code, UTC time, Python and
pytest versions, platform, Git branch and commit, and pre-run working-tree
state. It refuses to overwrite an existing run.

The first run is expected to collect successfully and fail because the two
order-book classes deliberately raise `NotImplementedError`. The original
pre-implementation run is preserved, followed by a reviewed run after a
sequence-state test was strengthened. Passing tests are not expected until
the corresponding implementation checkpoint.

## Public interface

Both `BaselineOrderBook` and `RevisedOrderBook` provide:

- `process_event(event)`
- `add_limit_order(event)`
- `cancel_order(event)`
- `fill_market_sell(event)`
- `inspect_book()`

The two versions accept identical event dictionaries and return plain
dictionaries. Book inspection is canonical: bids by decreasing price and
arrival sequence, followed by asks by increasing price and arrival sequence.

## Worked-example expected output

Both implementations reproduce `data/supplied/worked_expected.json`. The final
market sell is filled with no residual and executes, in order:

```text
b1: 100000000 units at 6000000 ticks
b2: 100000000 units at 6000000 ticks
b3: 300000000 units at 5990000 ticks
b4: 100000000 units at 5970000 ticks
```

The remaining book contains `b4` with 400,000,000 units at 5,970,000 ticks and
`a1` with 200,000,000 units at 6,010,000 ticks. Gross proceeds are
3,594,000,000,000,000 tick-times-quantity units, or USD 359,400.00.

## Supplied data

The files under `data/supplied/` are byte-for-byte copies of the assignment
package's worked example and five 10,000-event synthetic workloads. Larger
files belong under `data/generated/` and are not committed.

The formal input plan contains 45 core configurations (five scenarios, three
event counts, and seeds 42, 43, and 44) plus one additional four-level buildup
stream for the controlled queue-concentration comparison. Generate missing
streams and verify all metadata and checksums outside timing with:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\06_prepare_inputs.py `
  --generate `
  --plan-out experiments\08_input_plan.json
```

The command refuses to replace the saved plan. Generated compressed streams
remain ignored; their small metadata files and the complete verified plan are
committed for reproducibility.

Formal tasks use a preregistered 60-second wall-clock limit per configuration,
identically for both implementations. The runner saves gzip-compressed raw
results only after validation and otherwise saves an explicit failure or
timeout status without inventing a measurement:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\07_run_formal.py `
  --version baseline `
  --resume
```

Filters such as `--phase`, `--scenario`, `--event-count`, `--seed`, and
`--task-id` support pilots and review. Formal execution begins only from a
committed runner checkpoint.

After completing the original 114-task matrix for both versions, an optional
one-million-event extension was defined separately. It uses seed 42, all five
workload families, throughput only, and the same warm-up, five repeats, and
60-second limit for both versions. Large generated inputs remain ignored; the
verified plan and metadata are retained:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\09_prepare_million_inputs.py --generate
.\.venv\Scripts\python.exe scripts\10_run_million.py --version baseline --resume
.\.venv\Scripts\python.exe scripts\10_run_million.py --version revised --resume
```

Extension results are stored below `results/extension_1m/` and are not counted
as part of the original formal matrix.

## Development status

1. Specification and independent tests: strengthened by pre-revision critical review.
2. Transparent baseline: implemented and passing its applicable contract tests.
3. Revised implementation: implemented; final full suite has 226 passes.
4. Throughput: both formal matrices recorded under identical settings.
5. Per-event latency: both representative matrices recorded.
6. Memory: both state and retained-output matrices recorded.
7. Formal input matrix: generated, checksum-verified, and replayed by both.
8. Timeout-aware runner: 228 formal statuses recorded (114 per version).
9. Liquidation and diagnostics: both formal stress runs recorded.
10. Dashboard: implemented from saved results; 238 task statuses represented.
11. Optional one-million-event extension: test-first harness implemented;
    paired throughput results recorded.
12. Arbitrary plain/gzip replay command: implemented test-first and verified
    from a clean project-local environment.

## Saved-results dashboard

Launch Streamlit with the committed saved-result table:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m streamlit run dashboard\12_app.py
```

The builder refuses to overwrite an existing artifact. The committed dashboard
loads `results/summary/13_dashboard_data.json.gz`; changing a filter or view
does not rerun an experiment. The tables preserve raw throughput and
liquidation repeats, stopped tasks, latency percentiles, memory checkpoints,
settings, environment/code metadata, and correctness diagnostics.

Task-coverage tables intentionally remain separate from completed-run timing
tables: coverage includes stopped tasks that have no timing value, whereas the
timing tables contain only completed measurements. Comparative timing charts
use logarithmic axes so a much faster version is not visually compressed to
zero. Throughput charts distinguish fresh empty-engine initialization from
replaying the entire event stream. The default memory view is the largest saved
state-only cancellation-churn run, making post-cancellation state directly
visible.

To reproduce the aggregation without replacing the committed artifact, build a
second file and point the dashboard at it:

```powershell
.\.venv\Scripts\python.exe scripts\11_build_dashboard_data.py `
  --out results\summary\13_dashboard_data_rebuilt.json.gz
$env:ASSIGNMENT1_DASHBOARD_DATA = `
  "results\summary\13_dashboard_data_rebuilt.json.gz"
.\.venv\Scripts\python.exe -m streamlit run dashboard\12_app.py
```

The short interpretation report is `docs/07_results_report.md`.

Validate the baseline against all supplied 10,000-event streams:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\03_validate_supplied.py --version baseline
```

Use `--version revised` to validate Version B against the same supplied
streams.

The baseline deliberately uses a list of individual resting orders. It scans
and sorts that list during matching and scans it during cancellation. This is
the transparent Version A to preserve before a measured data-organization
revision.

## Non-formal benchmark smoke check

The smoke check exercises input parsing, checksumming, fresh-state warm-up and
repeats, exclusive JSON persistence, and environment metadata on only the
first 100 events. It is harness verification, not a formal performance result:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\04_benchmark.py `
  --version baseline `
  --input data\supplied\cancel_churn_10000.jsonl.gz `
  --max-events 100 `
  --warmups 1 `
  --repeats 2 `
  --out evidence\05_benchmark_smoke\05_baseline_cancel_churn_100.json
```

The command refuses to overwrite an existing result. Choose a new explicitly
labelled output path to repeat the smoke check.

The separate latency smoke check performs one untimed replay on its own book,
then records each event on a new empty book. It retains raw nanoseconds and
summarizes overall, per-event-type, and early/late-window latency:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\04_benchmark.py `
  --phase latency `
  --version baseline `
  --input data\supplied\cancel_churn_10000.jsonl.gz `
  --max-events 100 `
  --warmups 1 `
  --repeats 5 `
  --out evidence\06_latency_smoke\06_baseline_cancel_churn_100.json
```

Every measured repeat uses a new empty book, and raw records retain both repeat
and event indices. Like the throughput smoke check, this verifies
instrumentation and persistence; its 100-event timings are not formal
performance evidence.

Memory is measured separately with input parsing completed before
`tracemalloc` starts. Run state-only and retained-output modes independently:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\05_measure_memory.py `
  --version baseline `
  --mode memory_state `
  --input data\supplied\cancel_churn_10000.jsonl.gz `
  --max-events 100 `
  --checkpoints 10 `
  --out evidence\07_memory_smoke\07_baseline_cancel_churn_100_state.json

.\.venv\Scripts\python.exe scripts\05_measure_memory.py `
  --version baseline `
  --mode memory_retained_output `
  --input data\supplied\cancel_churn_10000.jsonl.gz `
  --max-events 100 `
  --checkpoints 10 `
  --out evidence\07_memory_smoke\07_baseline_cancel_churn_100_retained_output.json
```

The additional buildup smoke record uses the same state-only command with
`buildup_10000.jsonl.gz`. These 100-event records verify boundaries, growth
samples, and persistence; their byte values are not formal A-versus-B results.

The separate stress command rebuilds a deterministic 1,000-maker, 100-level
bid book for every 10%, 100%, and 200% liquidation repeat. It also runs
correctness diagnostics on the five 1,000-event seed-42 workloads:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts\08_run_stress.py `
  --version baseline `
  --order-count 1000 `
  --price-levels 100 `
  --warmups 1 `
  --repeats 5 `
  --diagnostic-events 1000 `
  --out results\stress\baseline\10_stress_and_diagnostic.json.gz
```

