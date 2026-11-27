# Assignment 1 — Limit order book (Maurice Bonacker)

Submission for Assignment 1 of Algorithms in Finance (Frankfurt School), due 26 November 2026, 18:00.
Report: `07_docs/REPORT.md`. Dashboard: `06_dashboard/dashboard.html`.

Submitted commit: `76a97a7` (full hash `76a97a7d1e61030f23f4154270f4fc3f29ba0058`, branch `bonacker/phase1`): all code, tests, results, dashboard and report.
Later commits only change this README. The timing benchmark was measured at `4b9df5f`, the latency and memory rerun at `ade26d1`; the engines are identical in all three commits.

## Reproduce everything from a clean environment

Run every command from `Assignment1/`.

### 1. Python and packages

Python 3.13 (measured with 3.13.15 on Windows 11). The engines, `replay.py`
and the benchmark scripts use only the standard library. `pytest` runs the
tests and `matplotlib` draws the dashboard plots.

The submitted commit lives on my fork (branch `bonacker/phase1`). Once the pull
request is merged into the course repository, the same folder is also under
`cogeorg/AlgorithmsFinance`; if the merge was squashed, use the fork to check out
`76a97a7` exactly.

```bash
git clone https://github.com/Oxilop365/AlgorithmsFinance.git
cd AlgorithmsFinance/Submissions/BonackerMaurice/Assignment1
git checkout 76a97a7
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt   # pytest==9.1.1, matplotlib==3.11.2
```

### 2. Tests

```bash
python -m pytest
```

Expected: **182 passed** (about 3 seconds).

### 3. Worked example

```bash
python 03_code/replay.py 00_instructions/data/worked_example.jsonl --version b_sorted --results worked_results.jsonl --print-book
```

Expected console output, the same for `a`, `b_sorted` and `b_heap` except for
`version` and `wall_seconds`:

```
version=b_sorted  scenario=worked_example  events=6  fills=4  rejected=0  not_found_cancels=0  peak_active_orders=  peak_price_levels=  final_book_size=2  invariants_ok=not checked  wall_seconds=...
final book: 2 resting orders (bids best first, then asks best first; FIFO within a price)
{"order_id": "b4", "side": "BUY", "price_ticks": 5970000, "qty_units": 400000000, "arrival_seq": 4}
{"order_id": "a1", "side": "SELL", "price_ticks": 6010000, "qty_units": 200000000, "arrival_seq": 5}
```

The last line of `worked_results.jsonl` is the six-BTC market sell. Its status
is `filled`, with 0 unfilled and these fills, in this order:

| Maker | Price (ticks) | Price (USD) | Quantity (units) | Quantity (BTC) |
|---|---|---|---|---|
| b1 | 6000000 | 60,000 | 100000000 | 1 |
| b2 | 6000000 | 60,000 | 100000000 | 1 |
| b3 | 5990000 | 59,900 | 300000000 | 3 |
| b4 | 5970000 | 59,700 | 100000000 | 1 |

Gross proceeds: sum of `price_ticks * qty_units` / 10^10 = **USD 359,400.00**.
The expected values come from `00_instructions/data/worked_expected.json`.

### 4. Regenerate the data

```bash
python 04_benchmarks/run_benchmark.py --phases data
```

This takes about one minute and writes 55 event files (about 35 MB,
gitignored) to `05_results/data/bench/`. `05_results/benchmark_datasets.csv`
lists each file with its generator command and SHA-256, so
`git diff --stat 05_results/benchmark_datasets.csv` is empty when the same
files came out. The checksum is of the `.gz` file. A different zlib build can
compress the same events to different bytes.

### 5. Benchmark

Run nothing else heavy next to it, and plug the laptop in. Times are from the
measured machine (Intel Core Ultra 5 228V, 31.5 GiB RAM).

| Command | What it runs | Time |
|---|---|---|
| `python 04_benchmarks/run_benchmark.py` | everything: tests, data, timing, liquidation, concentration, latency, memory, opcounts, summary | about 75 min (mostly Version A, up to the 120 s limit per replay) |
| `python 04_benchmarks/run_benchmark.py --latency-memory` | only latency and memory, on the existing data | about 12 min |
| `python 04_benchmarks/run_benchmark.py --phases timing summary` | any selected phases, always in the order above | timing 33, liquidation 10, concentration 18, latency 3, memory 10 min; tests, data, opcounts and summary: about 1 min or less each |
| `python 04_benchmarks/run_benchmark.py --smoke` | every phase with 1,000 events only, into `05_results/smoke/` (gitignored) | about 1 min |

- Without `--smoke`, the script refuses to run when the code is not committed,
  so every result belongs to a known commit. For a copy without git, add
  `--allow-dirty`; this is recorded.
- Selected phases replace only their own output and write their own record
  (`benchmark_run_<phases>.json`, `environment_<phases>.json`). The record of
  the full run stays as it is.
- Without the data phase, the event files must exist and match their SHA-256.
- The runs write into `05_results/`.
  `git checkout -- 05_results 06_dashboard` brings the submitted results back.

### 6. Dashboard

```bash
python 06_dashboard/build_dashboard.py
```

This takes about 15 seconds. It reads only the saved files in `05_results/`
and writes `06_dashboard/dashboard.html`, one file that opens in any browser.
To rerun the tests for its correctness table first (about 5 seconds):

```bash
python 04_benchmarks/export_test_results.py
```

### Definitions of the measured data

The full wording is saved with each run (`definitions` in
`05_results/benchmark_run*.json`) and comes from `DEFINITIONS` in
`04_benchmarks/bench_common.py`.

| Measure | Definition |
|---|---|
| Versions | `a` = list scan (baseline), `b_sorted` and `b_heap` = price levels with FIFO queues, differing only in the price index |
| Workloads | `buildup`, `crowded`, `mixed`, `sweep`, `cancel_churn` with 1,000 / 10,000 / 100,000 events and seeds 42, 43, 44; also `buildup --levels 4` and one `mixed` file with 1,000,000 events (seed 43) |
| `elapsed_seconds` | `time.perf_counter()` around the measured step only. Loading and parsing (`parse`), full replay (`replay`), building a book (`build`) and one market sell (`sell`) are separate phases. |
| Replay | A fresh empty book, then every preloaded event. Results are not stored. |
| Sell | One `MARKET_SELL` of 10, 100 or 200% of the bid quantity, on a newly built book for every repeat. Includes matching, state updates and the fill list. |
| Repeats | 1 warm-up (recorded, not used) and 5 timed repeats, each with its raw row. Reported: median, min and max. |
| Throughput | events / median replay (or build) seconds |
| Time limit | 120 s per single replay, build or sell. A step that takes longer is stopped and recorded as `stopped`. Missing values are never estimated. |
| Garbage collection | The same for every version: collect before, disabled during and enabled after each timed step |
| Latency | A separate run: `perf_counter_ns()` around each `process_event` call, in nanoseconds, including one timer call. Processing only, no queueing or network, and never derived from throughput. Reported for all events, the first 1,000 and the last 1,000. |
| Latency per event type | The same timed events, split into `LIMIT resting` (no fill), `LIMIT traded` (at least one fill, also if a residual rests), `MARKET_SELL`, `CANCEL found`, `CANCEL not_found` and `rejected`: count, median, p95, p99, max. Count 0 means the type does not occur in that file. |
| Percentiles | Nearest rank: the p-th percentile of n sorted values is value number ceil(p/100 · n). No interpolation. |
| Memory | A separate `tracemalloc` run, in bytes. The events are loaded before tracing starts, so the input is excluded. Included: the book and the returned output of the current event, which stays referenced while the sample is read and is released before the next event. No history is saved. |
| `traced_peak_bytes` | Maximum during the replay |
| `traced_with_output_bytes` | After the last event, its output still referenced |
| `traced_current_bytes` | In `memory_end_state.csv` and `benchmark_results.csv`: after that output is released, so the book. In `memory_samples.csv`: the book plus the output of the sampled event. |
| `process_peak_bytes` | Peak memory of the whole process (interpreter, input and caches included). For context only. |
| Operation counts | A separate run with counting subclasses, not timed |

| File in `05_results/` | Content |
|---|---|
| `benchmark_results.csv` | Every raw repeat (`run_kind` = `timing` or `memory`) |
| `benchmark_summary.csv` | Median, min, max, spread and throughput |
| `benchmark_datasets.csv` | Every event file: command, SHA-256, event mix, peaks |
| `latency_summary.csv`, `latency_quantiles.csv`, `latency_by_type.csv` | Latency overall and early/late, all percentiles, per event type |
| `memory_samples.csv`, `memory_end_state.csv` | Memory during the replay and after it |
| `concentration_check.csv`, `opcounts.csv` | Price-time check of the queue-concentration runs, operation counts |
| `tests_by_case.csv`, `tests_by_case_run.json` | One row per test case, and the commit they ran on |
| `benchmark_run*.json`, `environment*.json` | Commit, settings, definitions, phases, machine, Python and packages |

## Replay your own event file

Run this from `Assignment1/`. The engine and `replay.py` use only the
standard library, so nothing needs to be installed.

```bash
python 03_code/replay.py my_events.jsonl --version b_sorted --results my_results.jsonl --print-book
```

| Option | Meaning |
|---|---|
| `my_events.jsonl` | Your file: `.jsonl` or `.jsonl.gz`, one JSON event per line. Several files can be given; `--results` takes exactly one. |
| `--version a` / `b_sorted` / `b_heap` | Which engine to use. All three give identical results. A is the slow list-scan baseline. |
| `--results OUT.jsonl` | Writes one JSON result per non-empty input line, in file order. |
| `--print-book` | Prints the final book after the summary line. |
| `--check` | Also checks the book's invariants after every event. Slow: use it on small files. |
| `--csv OUT.csv` | Writes one summary row per file. |

### Input: one event per line

```json
{"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1", "side": "BUY", "price_ticks": 6500000, "qty_units": 100000000}
{"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "m1", "qty_units": 40000000}
{"seq": 3, "event_id": "e3", "type": "CANCEL", "target_order_id": "b1"}
```

Units:

- `price_ticks` is in cents (USD 0.01). 6500000 means USD 65,000.00 per BTC.
- `qty_units` is in 1e-8 BTC. 100000000 means 1 BTC.

### Output

**Console.** One summary line per file:

```
version=b_sorted  scenario=my_events  events=5  fills=1  rejected=1  not_found_cancels=0  peak_active_orders=  peak_price_levels=  final_book_size=1  invariants_ok=not checked  wall_seconds=0.000034
```

- `events` counts the non-empty lines, malformed ones included.
- The peaks and `invariants_ok` are only filled in with `--check`.

**`--results`.** One JSON object per non-empty input line, in file order. Its
shape depends on the event:

| Event | Result |
|---|---|
| LIMIT | `{"event_id", "order_id", "status": "filled" \| "resting", "unfilled_qty_units", "fills"}`. For `resting`, `unfilled_qty_units` is the quantity that rests. |
| MARKET_SELL | Same keys, with `"status": "filled" \| "partial" \| "unfilled"`. An unfilled rest is discarded and never rests. |
| CANCEL | `{"event_id", "target_order_id", "status": "cancelled" \| "not_found", "cancelled_qty_units"}` |
| any rejected event | `{"event_id", "status": "rejected", "reason"}` |
| malformed line | `{"event_id": null, "status": "rejected", "reason": "malformed JSON line <n>"}` |

Each fill is `{"maker_id", "taker_id", "price_ticks", "qty_units"}` and trades
at the resting (maker) order's price.

Example. The input file has six lines:

1. bid `b1`
2. an empty line
3. ask `a1`
4. a market sell `m1`
5. a line that is cut off
6. a cancel of `a1`

It gives these results:

```
{"event_id": "e1", "order_id": "b1", "status": "resting", "unfilled_qty_units": 100000000, "fills": []}
{"event_id": "e2", "order_id": "a1", "status": "resting", "unfilled_qty_units": 30000000, "fills": []}
{"event_id": "e3", "order_id": "m1", "status": "filled", "unfilled_qty_units": 0, "fills": [{"maker_id": "b1", "taker_id": "m1", "price_ticks": 6500000, "qty_units": 40000000}]}
{"event_id": null, "status": "rejected", "reason": "malformed JSON line 5"}
{"event_id": "e4", "target_order_id": "a1", "status": "cancelled", "cancelled_qty_units": 30000000}
```

**`--print-book`.** After the summary line it prints a header line, then one
JSON object per resting order:

```
final book: 1 resting orders (bids best first, then asks best first; FIFO within a price)
{"order_id": "b1", "side": "BUY", "price_ticks": 6500000, "qty_units": 60000000, "arrival_seq": 1}
```

- Bids come first, highest price first, then asks, lowest price first.
- Within one price, orders are in arrival order.
- To keep the book in a file, redirect the output, e.g.
  `... --print-book > final_book.txt`.

### Assumptions

- **Ids.** `order_id` and `target_order_id` must be JSON strings. A number
  such as `7` is rejected, and `"7"` and `7` are not the same id. `event_id`
  must be present and is echoed back unchanged.
- **File order is processing order.** Events are processed one at a time,
  exactly in file order, and are never sorted.
- **seq must increase.** `seq` must be a positive integer greater than the
  last accepted `seq`. An event with a non-increasing `seq` is rejected, not
  reordered. A rejected event does not use up its `seq`.
- **Malformed lines are rejected, and the replay continues.** A line that is
  not valid JSON gives the malformed-line result above. This includes invalid
  UTF-8 and nesting too deep to parse. `<n>` is the 1-based line number in the
  (decompressed) file, counting empty lines. The book is not touched.
  Empty or whitespace-only lines are skipped and give no result.
- **Other invalid events are rejected with a reason.** This covers valid JSON
  that is not a valid event: a non-object, a missing field, an unknown `type`,
  a `side` other than `BUY` / `SELL` (case-sensitive), or a wrong number type.
  The book and the last accepted `seq` stay unchanged.
- **Numbers.** `seq`, `price_ticks` and `qty_units` must be JSON integers
  greater than 0. `100.0`, `"100"` and `true` are rejected. There is no upper
  limit.
- **Extra fields** in an event are ignored.
- **Duplicate ids.** An `order_id` is a duplicate only while an order with
  that id is still resting. After it is filled or cancelled, the id can be
  used again.
- **Cancel targets.** Cancelling an id that is not resting (unknown, already
  filled or cancelled, or a market sell, which never rests) gives
  `not_found` with `cancelled_qty_units` 0.
- **Reason texts** are for people and may change. Only
  `malformed JSON line <n>` is a fixed format.
