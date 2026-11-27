# Assignment 1: limit order book — Tolgahan Yildirim

A sequential, single-venue BTC limit order book in Python with its own
`FillMarketSell`, in two preserved versions (plus the preserved first draft of
the revision), with tests, benchmarks, saved raw results and an offline
dashboard. Everything lives in
`Submissions/YildirimTolgahan/Assignment1/`; only the Python standard library is
used. The short report is [REPORT.md](REPORT.md); measured numbers are in
[results/observations.md](results/observations.md).

This is a teaching model on synthetic, uncalibrated data. It is not a production
trading system: all orders are eligible, and there are no fees, balances, hidden
orders, self-trade checks, network delays or simultaneous execution.

## Run from a clean checkout

Reference environment: CPython 3.13.12 on Windows 11 x64 (any CPython 3.10+
should work; nothing to install). In PowerShell, from the repository root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
cd Submissions\YildirimTolgahan\Assignment1
python -B replay.py data/worked_example.jsonl --version B --expect data/worked_expected.json
python -B -m unittest test_orderbook test_adversarial test_measurement
python -B benchmark.py --quick --output results/smoke
python -B dashboard.py --results results/smoke/measurements.json --output results/smoke/dashboard.html
python -B verify_results.py
Start-Process .\results\dashboard.html
```

On macOS/Linux use `python3 -m venv .venv`, `source .venv/bin/activate` and
forward slashes. `python -B experiments.py` repeats the three follow-up
experiments of report section 4 (about a minute; not needed for anything else).
The dashboard is one self-contained HTML file: no server,
network access or API key.

The commands above do not replace the submitted measurements. To reproduce
them (about 1.5 hours on the reference laptop; use mains power and leave the
machine alone, because anything else running shows up in the timings):

```powershell
python -B benchmark.py            # add --resume to continue an interrupted run
python -B profile_run.py
python -B tuning.py               # first revision (B1) against the submitted version B
python -B observations.py
python -B dashboard.py
python -B verify_results.py
```

### Expected worked-example output

`replay.py ... --expect` exits with status 0 and prints, among other fields:

```json
"gross_value_usd": "359400.00",
"matches_expected": true,
"last_result": {"event_id": "event6", "order_id": "s1", "status": "filled", "unfilled_qty_units": 0,
  "fills": [{"maker_id": "b1", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000},
            {"maker_id": "b2", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000},
            {"maker_id": "b3", "taker_id": "s1", "price_ticks": 5990000, "qty_units": 300000000},
            {"maker_id": "b4", "taker_id": "s1", "price_ticks": 5970000, "qty_units": 100000000}]},
"remaining_orders": [
  {"order_id": "b4", "side": "BUY", "price_ticks": 5970000, "qty_units": 400000000, "arrival_seq": 4},
  {"order_id": "a1", "side": "SELL", "price_ticks": 6010000, "qty_units": 200000000, "arrival_seq": 5}]
```

Makers fill in the order b1:1, b2:1, b3:3, b4:1 BTC; four BTC remain on b4 and
the ask is untouched. Expected test result: `Ran 107 tests` and `OK`, in about
four minutes on mains power (the saved transcript `results/test_after.txt` was
taken on battery and shows about thirteen).

## Interface

All versions are classes with the same methods and accept the same event files
(`book_b1.OrderBookB1` too).

```python
from book_b import OrderBookB          # or: from book_a import OrderBookA
book = OrderBookB()
book.ProcessEvent(event)               # dispatcher: one parsed JSON event -> result dict
book.AddLimitOrder(order_id, side, price_ticks, qty_units, seq, event_id=None)
book.FillMarketSell(order_id, qty_units, event_id=None, seq=<optional>)
book.CancelOrder(target_order_id, event_id=None, seq=<optional>)
book.InspectBook()                     # active orders: bids by falling price then arrival, then asks by rising price then arrival
book.best_bid(); book.best_ask()       # price_ticks or None
book.active_orders(); book.price_levels(); book.last_seq
```

Results are plain dictionaries with the field names of the assignment:

| Event | Result |
|---|---|
| `LIMIT`, `MARKET_SELL` | `event_id`, `order_id`, `status`, `unfilled_qty_units`, `fills` (ordered list of `maker_id`, `taker_id`, `price_ticks`, `qty_units`) |
| `CANCEL` | `event_id`, `target_order_id`, `status` (`cancelled` / `not_found`), `cancelled_qty_units` |
| rejected | `event_id` (or `null`), `status: "rejected"`, `reason` |

Limit status is `filled` or `resting`; market-sell status is `filled`, `partial`
or `unfilled`. Only the current event's fills are returned and no trade history
is stored. Units: `price_ticks` are integer cents per BTC, `qty_units` integer
1e-8 BTC; gross value is `price_ticks * qty_units` and is divided by 10^10 only
for display (`events.format_usd`).

Validation choices beyond the assignment text, all tested: identifiers must be
non-empty strings; integers must be real `int` values (`true`, `1.0`, `"1"` and
`NaN` are rejected); a market sell may not use an identifier that is currently
resting; the dispatcher requires `event_id` and `seq`; a line that is not JSON
at all stops a file replay with its line number, while valid JSON of the wrong
shape is passed on and rejected by the book.

## Files

| File | Purpose |
|---|---|
| `events.py` | Shared envelope: file reading, validation, sequencing, result shapes. No storage or matching. |
| `book_a.py` | **Version A**: two unsorted lists of orders, `min()` scans. |
| `book_b.py` | **Version B**: FIFO queue per price, price heap per side, order index. |
| `book_b1.py` | Version B as first written ("B1"), preserved; same tests, compared by `tuning.py`. |
| `tuning.py` | Interleaved timing of B1 against B; writes `results/tuning.json`. |
| `experiments.py` | Three small follow-up experiments run by hand (break-even book size, cancel position, rejected events); writes `results/experiments.json`. Not part of the benchmark or the dashboard. |
| `replay.py` | Command line replay of a file through one or both versions. |
| `test_orderbook.py` | First test suite, written before the implementations. |
| `test_adversarial.py` | Second suite: exhaustive short sequences, targeted fuzzing, damaged files, planted bugs. |
| `test_measurement.py` | Generators, measurement helpers, result files, dashboard export. |
| `generate_orders.py`, `data/` | Supplied generator, the five supplied 10,000-event samples, worked example (unchanged). |
| `workloads.py` | Additional generators: `mass_cancel` streams and one-sided bid books; dataset checksums. |
| `instrumented.py` | Counting subclasses for operation counts (never used in timing). |
| `benchmark.py` | All measurements; writes `results/measurements.json`, `summary.csv`, `raw_repeats.csv`. |
| `profile_run.py` | cProfile of both versions; writes `results/profile.json`. |
| `observations.py` | Derives `results/observations.md` from the saved results. |
| `dashboard.py`, `dashboard_template.html` | Build `results/dashboard.html` from saved results. |
| `verify_results.py` | Checks coverage, medians, CSV/JSON agreement, hashes, version agreement, dashboard rebuild. |
| `results/` | Saved raw results, transcripts, dashboard, verification report. |

## Measured-data definitions

**Workloads.** Six stream families: the five supplied ones (`buildup`,
`crowded`, `mixed`, `sweep`, `cancel_churn`) and `mass_cancel` (first half
passive limits, second half cancellations that leave about 1% active). Stream
lengths M = 1,000, 10,000 and 100,000 with seeds 42, 43 and 44; M = 30,000 and
1,000,000 with seed 42; 1,000 available prices per side. Files are generated
before anything is timed. Generated files are not committed; the command and
SHA-256 of every file are saved in `results/measurements.json` (`datasets`) and
shown in the dashboard. For example:

```sh
python generate_orders.py --scenario mixed --events 1000000 --levels 1000 --seed 42 --out data/generated/mixed_1000000_seed42_levels1000.jsonl.gz
python workloads.py --scenario mass_cancel --events 100000 --levels 1000 --seed 43 --out data/generated/mass_cancel_100000_seed43_levels1000.jsonl.gz
```

**Symbols.** M events in a stream, B active orders, P occupied price levels,
F maker fills. Peaks of B and P are recorded per stream; P is counted in
version B's pass (constant time there) and copied to version A's row only when
both result digests are identical.

**Cells and passes.** Each (workload, seed, size, version) cell runs in a fresh
child process, in this order: untimed warm-up; five timed replays; one latency
pass; one operation-count pass (M ≤ 10,000 only); one `tracemalloc` pass. Which
version runs first is shuffled per cell with a recorded seed.

| Quantity | Definition |
|---|---|
| `replay` seconds | `time.perf_counter` around loops over already parsed events, in blocks of at most 1,000 events, summed; fresh empty book and `gc.collect()` before every repeat; garbage collector left enabled. Includes validation, matching, index updates, cleanup and building each result. |
| `build` / `after_build` | The same replay split at the event where `sweep` (80%) or `mass_cancel` (50%) stops building its book. |
| throughput | M divided by the median replay seconds. |
| `read_parse` seconds | gzip reading plus JSON parsing of the whole file, five repeats, version-independent. "Application" time in the dashboard is this median plus the replay median. |
| `construction` seconds | Inserting N passive bids into a fresh book, timed in every fixed-book trial. |
| `sell` seconds | One `FillMarketSell` call on that fresh book: matching, state updates and the fill list. Sale sizes are 10% (rounded up, at least one unit), 100% and 200% of the available bid quantity. |
| latency | Separate pass, `perf_counter_ns` around each dispatcher call. Median, 95th and 99th percentile by the nearest-rank convention (smallest observation with at least p% of the sample at or below it); also per event type, per tenth of the stream, and for the first and last 10% of events. Engine processing only. |
| traced bytes | Separate pass under `tracemalloc`: peak, value at every 5% of the stream, and value at the end. Includes the book, its indexes and the latest returned result; excludes preloaded input. For M above 100,000 the input is parsed in blocks inside the trace, so up to 1,000 parsed events are included. Not auxiliary space and not process memory. |
| operation counts | Separate pass with `instrumented.py`: list records examined by version A's scans; heap pushes, pops and stale discards in version B. |

**Limits.** 60 s per replay, 30 s per single market sell, 1 GiB traced memory,
identical for both versions. A replay over its limit is stopped at the next
block boundary and its remaining repeats and passes are skipped; a sale over its
limit is ended by terminating the child process. Stopped cells are saved with
status `stopped`, the time reached and the events completed, and are shown as
open markers in the dashboard. Nothing is extrapolated for them.

**Saved tables.** `results/raw_repeats.csv` has one row per repeat and phase
with `experiment`, `run_kind` (`timing` or `memory`), `version`, `scenario`,
`seed`, `events`, `levels`, `book_orders`, `sale_pct`, `requested_qty_units`,
`phase`, `repeat`, `status`, `elapsed_seconds`, `events_completed`,
`peak_active_orders`, `peak_price_levels`, `fill_count`, `unfilled_qty_units`,
`traced_peak_bytes`, `traced_current_bytes`. `results/summary.csv` has one row
per cell with medians, percentiles and digests. `results/measurements.json`
holds everything, including Python, operating system, processor, clock
resolution, settings, limits, generator commands and the SHA-256 of every
measured source file.

**Second pass.** Six of the 282 cells of the submitted run were measured again
with `benchmark.py --resume` because a browser had been started on the laptop
while they ran; they are listed in REPORT.md, section 8. The first pass's log is
`results/benchmark_log_first_pass.txt`.

## Code version

The submitted version is the head commit of the pull request that adds this
folder. The measurements were taken before that commit existed, so
`git_commit` in the metadata reads `unavailable`; the measured code is
identified instead by the SHA-256 of each source file, and
`python verify_results.py` fails if any of those files differs from what was
measured.

## Use of AI

The implementation, tests, measurement code and documentation were generated
with Claude Code (Anthropic) under my direction, starting from my earlier lab
submission in `Submissions/YildirimTolgahan/`. The record of accepted, corrected
and rejected suggestions is in [REPORT.md](REPORT.md#7-revision-and-use-of-ai).
The follow-up experiments (`experiments.py`) were parameterised, run and
interpreted by me; the script itself was generated.
