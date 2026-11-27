# Assignment 1 — BTC limit order book

Garv Sharma · Phase 1 only · Due 26 November 2026, 18:00 course time.

Version A is `BaselineBook`; Version B is `RevisedBook` in `orderbook.py`.
Both implement their own matching logic. Python's standard library is the only
dependency. Docker is optional and is not used. This is an educational,
sequential, single-venue model using synthetic data, without fees, balances,
hidden orders, self-trade prevention, networking or concurrent execution.

## Run from a clean checkout

Use Python 3.11 or newer. The recorded run uses the exact Python and hardware
shown in `results/environment.json`; timings vary by machine.

```sh
git clone https://github.com/garvsharma1118-code/AlgorithmsFinance.git
cd AlgorithmsFinance/Submissions/SharmaGarv/Assignment1
python -B -m unittest discover -s tests -v
python -B replay.py data/worked_example.jsonl --version A
python -B replay.py data/worked_example.jsonl --version B
python -B dashboard.py
python -m http.server 8000
```

Expected: all **20 tests pass**, and both replay commands print the same six
event results followed by a final JSON summary. The last sell's makers are
`b1:100000000`, `b2:100000000`, `b3:300000000`, `b4:100000000`, in that order.
It is `filled`, with zero residual; `b4` retains 400000000 units and `a1`
retains 200000000. Gross proceeds are 3594000000000000 tick-times-quantity
units, or **USD 359400.00**. Exact expected objects are in
`data/worked_expected.json`.

The dashboard builder prints `Wrote dashboard.html from saved results (no
experiments executed).` Open <http://localhost:8000/dashboard.html>, or open
`dashboard.html` directly in a current Edge/Chrome/Firefox browser. The page
embeds saved results; no exchange access or experiment rerun is needed. Hover
chart points for their series and exact values; use workload/seed selectors.
The price-range and sale-fraction curves are identified in point tooltips.

## API

```python
from orderbook import BaselineBook, RevisedBook
book = RevisedBook()
result = book.AddLimitOrder({"seq": 1, "event_id": "e1", "type": "LIMIT",
    "order_id": "b1", "side": "BUY", "price_ticks": 6000000,
    "qty_units": 100000000})
result = book.FillMarketSell({"seq": 2, "event_id": "e2", "type": "MARKET_SELL",
    "order_id": "s1", "qty_units": 100000000})
print(book.inspect())  # []
```

`process(event)` validates and dispatches to `AddLimitOrder(event)`,
`CancelOrder(event)` or `FillMarketSell(event)`. Each public method accepts the
same event dictionary schema as the supplied data and returns one result
dictionary. Calling a method with the wrong event type rejects it atomically.
`inspect()` returns detached order dictionaries, bids descending then asks
ascending, FIFO within price. `stats()` returns active orders, occupied levels
and live bid quantity. Submission results contain event/order identifiers,
status, unfilled quantity and ordered fills; cancellation results contain
target, status and cancelled residual. Unknown cancels are valid no-ops.

Validation rejects booleans as integers, nonpositive/noninteger prices and
quantities, invalid sides/types, missing identifiers, duplicate live order
identifiers and nonincreasing sequences before changing state. Historical
identifier reuse validation is outside scope. Rejection does not advance the
last accepted sequence. Unfilled market quantity is discarded. Matching and
conservation use integer cents and 1e-8 BTC units; divide price*quantity by
10,000,000,000 for USD. Execution always uses the resting maker's price.

## Reproduce measurements

The saved `results/raw.jsonl` is the primary evidence, with every recorded
repeat, including stopped runs. To rerun, use a fresh copy or move `results/`
aside first (preserve it if you need the recorded submission evidence):

```sh
python -B benchmark.py --limit 3
python -B dashboard.py
```

The runner creates `results/` if needed, refuses to overwrite existing primary
raw results, and prints `Benchmark complete` when done. Expect several minutes
or longer, depending on hardware and stopped baseline runs. It generates each
input before timing, uses one experiment worker at a time, and removes only
the temporary datasets it generated. No pip install is required.

The full grid is 5 workloads × 3 seeds (42/43/44) × 3 stream sizes
(1000/10000/100000) × 2 versions. Every replay has five raw repeats and a fresh
book after a 500-event warmup; each input is read/parsed five times separately.
GC is enabled and collected before repeats. An additional run measures each
event's processing time; another run uses `tracemalloc`. Stream deadlines are
checked every 256 events, so a long individual matching event can exceed a
phase deadline. The external process watchdog provides a 90-second hard bound
per grid worker. A three-second phase budget applies equally to both engines.

Fresh-book liquidation uses initial B=1000 and 10000 buys, price ranges 4 and
1000, seeds 42/43/44 and requests 10%, 100%, 200% of initial bid quantity, five
repeats each. Construction is timed separately. Every individual sale includes
matching, index updates and fill-list creation; oversized requests expose the
discarded residual. Sale time above three seconds is labelled `over_limit`
after completion; the 90-second worker watchdog can stop the process mid-sale.
No completed-over-limit sale is used for a five-repeat median. The same rule
and watchdog apply to both versions. This asymmetry in cooperative versus
uninterruptible sale cancellation is an explicit measurement limitation.

A one-million-event buildup stream, seed 42, is attempted for **both** engines
with the same phase budget and a 45-second whole-worker deadline. Incomplete
or stopped phases are recorded rather than extrapolated. No byte-based memory
cap is imposed; time budgets are the declared resource limit. The tests and
diagnostic operation counters run outside primary timing; `cProfile` output
covers a fresh 3000-maker full liquidation for each version.

### Measurement fields and boundaries

* `version`: A or B; `scenario`, `seed`, `event_count`: input definition.
* `levels`: generator's available price range per side, not actual occupied
  levels; crowded streams always use four available prices per side.
* `phase`: `parse`, `replay`, `latency`, `memory`, `construction`, `sale`,
  `operations`, or worker-level failure/stop. `repeat` is zero-based.
* `elapsed_seconds`: `perf_counter` wall time in that phase. Replay includes
  validation, dispatch, mutation and result construction; excludes generation,
  file I/O and JSON/gzip parsing. Parse includes file I/O/decompression/JSON.
* `active_order_peak`, `price_level_peak`, `fill_count`: separate instrumented
  run, not expensive per-event primary-timing observations. Stopped runs may
  lack these totals. Null/absent fields mean not measured, never zero.
* `throughput_events_per_second`: M divided by a successful replay duration.
  Latency is measured independently with `perf_counter` around each process
  call; nearest-rank percentiles use sorted index `ceil(p*n)-1`. Saved histograms
  retain counts in fixed time buckets. Begin/end medians use up to 1000 events.
* `traced_peak_bytes`, `traced_current_bytes`: separate `tracemalloc` run started
  **after preloading the input**. Includes engine, transient outputs, samples
  and runner overhead; excludes preloaded events, native allocations and total
  process RSS. Memory checkpoints show book construction or cancellation state.
  No full trade history is retained. Timing while tracing is not primary time.
* `requested_qty_units`, `maker_orders_touched`, `price_levels_visited`,
  `unfilled_qty_units`: individual fresh-book sale diagnostics. Fills execute
  once per maker, so maker touches equal fill count in this model.
* `status=stopped/over_limit/error`: censored or failed evidence. Summary
  medians exist only for groups with five successful repeats. Missing groups
  after a hard worker stop have no inferred observations.

`results/environment.json` records OS, CPU description/count, Python, clock,
settings, dataset checksums and exact generation commands. Source provenance is
`source_sha256`: SHA-256 of sorted top-level/test Python relative paths, NUL
separator, and file bytes, computed by `benchmark.source_fingerprint()`.
This identifies the actual measured code independently of later documentation
and result commits. `SUBMITTED_COMMIT.txt` records the immutable submission
snapshot once published; its small follow-up receipt commit avoids a circular
attempt to put a commit's own hash inside itself.

`results/tests_initial.txt` records missing-engine failure before implementation;
`tests_final.txt` and `correctness.json` record the final unchanged suite plus
added regressions. `interrupted_pre_fix.jsonl` is **exploratory, excluded from
dashboard/medians**: the first benchmark was interrupted to fix malformed-type
dispatch, then the entire primary grid was restarted against the final code.

### Large datasets

Only the tiny supplied worked fixture is committed as event data.
All benchmark inputs, including the million-event stream, are regenerated
with commands/checksums in `results/environment.json`, for example:

```sh
python generate_orders.py --scenario buildup --events 100000 --levels 1000 --seed 42 --out data/buildup_100000_seed42.jsonl.gz
python generate_orders.py --scenario buildup --events 1000000 --levels 1000 --seed 42 --out data/buildup_1000000_seed42.jsonl.gz
```

The supplied generator uses a fixed gzip header. Byte checksums may differ
across Python/zlib versions; use the recorded environment for byte identity.
Metadata created by the standalone generator is additional to the runner's
dataset registry. No historical/proprietary exchange data are included.

## Files

* `orderbook.py`, `replay.py`: preserved A/B engines and replay command.
* `tests/test_orderbook.py`: independent examples, invariants and parity tests.
* `generate_orders.py`, `data/`: supplied synthetic generator and worked fixtures.
* `benchmark.py`, `results/`: measurements, settings, profiles and correctness.
* `dashboard.py`, `dashboard_template.html`, `dashboard.html`: saved-data viewer.
* `REPORT.md`: specification, correctness, runtime, memory, profiling, revision
  and measured limitations. `AI_USAGE.md` explains AI involvement.

Only `Submissions/SharmaGarv/Assignment1/` is part of this submission. No peer
audit or Phase 2 work is included; no other student's or course files change.
