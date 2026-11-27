# Assignment 1: Build and benchmark a limit order book

Submission of Bastian Bundschuh for *Algorithms in Finance* (take-home exercise, due
26 November 2026, 18:00). Task and data: `docs/ASSIGNMENT_README.md`,
`docs/AlgorithmsFinance_Exercise1.pdf`.

**Status: complete.** Both versions, 454 tests, all benchmarks, the dashboard and the report
(`REPORT.md`) are done; every result file in `results/` was measured on one MacBook Air
(see `results/env.json`). The submitted code version is at the end of this file.

A sequential, single-venue BTC limit order book in Python with price-time (FIFO) priority,
in two versions:

| Version | Data organization | File |
|---|---|---|
| A (baseline) | list of orders per side, found by scanning | `lob/version_a.py` |
| B (revision) | price levels with FIFO queues (deque, lazy cancel) + sorted price list + order index | `lob/version_b.py` |

All rules, units, result formats and decisions: **`SPEC.md`**.
Model boundaries: one venue, no fees, balances, hidden orders, self-trade checks or
network delay; synthetic data only; not a production trading system.

## Setup

Python 3.11 or newer. From this folder (`Submissions/BundschuhBastian/Assignment1/`):

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

## Commands

| Step | Command | Writes |
|---|---|---|
| Check supplied data | `.venv/bin/python tools/verify_data.py` | `results/data_checksums.json` |
| Tests | `.venv/bin/python -m pytest -q` | nothing |
| Replay a file | `.venv/bin/python -m lob.replay data/worked_example.jsonl --version A` | stdout |
| Generate data (about 100 MB, 100 s) | `bash bench/make_data.sh` | `data/generated/` (not committed) |
| Benchmarks (several hours; needs the generated data; machine idle, on AC power) | `bash bench/run_all.sh` | `results/` |
| Dashboard | `.venv/bin/streamlit run dashboard/app.py` | nothing (loads `results/` only) |

## Tests

`.venv/bin/python -m pytest -q`: 454 tests; every test with a `book` runs for A and B.
Every event in a test goes through `tests/helpers.py::step()`, which checks invariants
I1-I7 and price-time order after that event (see `SPEC.md` section 4).

| File | What it covers |
|---|---|
| `tests/test_validation.py` | 86 malformed events (non-dict, missing fields, `None`, `True`, floats, `nan`/`inf`, unhashable values, wrong case, duplicate live ids), first-failing-check order (D9), seq bookkeeping, id reuse after fill/cancel, extra fields ignored, no shared objects with the caller |
| `tests/test_matching.py` | empty book, one order, sell smaller/equal/larger than depth, FIFO at one price, several prices, partial fill keeps priority, id spelling vs arrival, 1000-order queue, crossing limit buys/sells at resting prices, equality cross, emptied level recreated, huge integers |
| `tests/test_cancel.py` | cancel before/after partial/full fill, repeat/unknown/near-miss ids, head/middle/tail of queue, only order at best price, cancel everything, add/cancel churn |
| `tests/test_worked_and_files.py` | worked example (file and by hand), replay command, reader edge cases, the five supplied 10,000-event files with outcomes derived from the generator |
| `tests/test_equivalence.py`, `test_process_fuzz.py`, `test_validation_fast.py`, `test_version_b_structure.py` | A and B compared after every event on small adversarial streams, B's internal structure (no empty level, records <= 2 x live orders), the fast validation path against `validate()` |
| `tests/test_generated_data.py`, `tests/test_bench.py`, `tests/test_dashboard.py` | the generated streams and their checksums, the benchmark code (percentiles, limits, gc, counters, liquidation), every dashboard page |

Phase 1 red run (stubs, historical): `docs/test_logs/phase1_red.txt`.

## Expected worked-example output

`data/worked_example.jsonl`: makers fill `b1:1, b2:1, b3:3, b4:1` BTC; 4 BTC stay on `b4`;
the ask `a1` is unchanged; gross value 3,594,000,000,000,000 tick-units = **359,400.00 USD**.
Full expected result: `data/worked_expected.json`. Output of
`.venv/bin/python -m lob.replay data/worked_example.jsonl --version A` (Version B prints the same; the first five
lines, the resting orders, are left out; the sixth is the sell `s1` with its four fills):

```
{"event_id":"event6","order_id":"s1","status":"filled","unfilled_qty_units":0,"fills":[{"maker_id":"b1","taker_id":"s1","price_ticks":6000000,"qty_units":100000000},{"maker_id":"b2","taker_id":"s1","price_ticks":6000000,"qty_units":100000000},{"maker_id":"b3","taker_id":"s1","price_ticks":5990000,"qty_units":300000000},{"maker_id":"b4","taker_id":"s1","price_ticks":5970000,"qty_units":100000000}]}
{
  "version": "A",
  "status_counts": {
    "resting": 5,
    "filled": 1
  },
  "gross_value_tick_units": 3594000000000000,
  "gross_value_usd": "359400.00",
  "remaining_orders": [
    {
      "order_id": "b4",
      "side": "BUY",
      "price_ticks": 5970000,
      "qty_units": 400000000,
      "arrival_seq": 4
    },
    {
      "order_id": "a1",
      "side": "SELL",
      "price_ticks": 6010000,
      "qty_units": 200000000,
      "arrival_seq": 5
    }
  ]
}
```

## Folder layout

```
SPEC.md               rules + decisions D1-D19
lob/                  common.py (reader, reasons, display), version_a.py, version_b.py, replay.py
tests/                hand-calculated, worked example, invariants, A-vs-B equivalence
tools/                verify_data.py, gen_small.py (own small generator), ab_timing.py, hash_generated.py
bench/                timing, latency, memory, counts, liquidation, concentration, churn, flood, fairness; make_data.sh, run_all.sh
results/              saved raw results + environment metadata
dashboard/            Streamlit app that only loads results/
REPORT.md             the report (model, costs, results, incident, limitations)
REVISIONS.md          A -> B changes and the 10 optimization steps with timings
data/                 supplied 10,000-event files + worked example (unchanged)
docs/                 course assignment README and slides (unchanged copies)
generate_orders.py    course generator (unchanged)
MANIFEST.json         course checksum manifest (unchanged)
AI_LOG.md             accepted / corrected / rejected AI suggestions
```

## Benchmark limits and run rules (declared before any benchmark was run)

These rules apply to Version A and Version B alike, to every scenario, seed and event count.
They were fixed by Bastian before the first benchmark run (commit of this section: see
`git log -- README.md`). No missing value is ever invented or extrapolated.

1. **Time limit: 10 minutes (600 s) per single replay.** A replay is one pass of one event file
   through one fresh, empty book. It applies to every kind of run (timing, latency, memory,
   counters). A replay that reaches the limit is killed and recorded as `status=stopped`, with
   the limit, the elapsed time at the kill and the number of events processed so far. Its
   remaining repeats are skipped (not run, not estimated).
2. **Repeats.** The first replay of a (version, file) pair is always timed.
   - If it takes **60 s or less**, it counts as the warm-up and is followed by **5 timed
     replays**. All 5 raw times and their median are saved.
   - If it takes **more than 60 s**, it is used as the one and only measurement: no warm-up, no
     further replays, `repeats=1` is recorded.
   Every replay starts from a fresh empty book. Parsing the file is timed separately from the
   replay.
3. **Version A on 1,000,000-event files.** A runs on a 1,000,000-event file only if A on the
   100,000-event file of the same scenario (seed 42) finished with a replay time **below 60 s**.
   Otherwise the run is recorded as `status=not_run` with the reason (A at 100,000 events took
   X s, or was stopped). Version B runs on all files.

Result statuses in the saved tables: `ok`, `stopped` (rule 1), `not_run` (rule 3 and the
instrumented-run rule below), `error` (the run crashed; the error text is saved, nothing is
estimated). The numbers 60 s and 600 s are the declared constants in `bench/common.py`.

Details of how the rules are applied (also fixed before the first run):

- **Enforcement.** Every run is a child process. The parent measures wall-clock time and, at 600 s,
  stops the child. Events processed at the stop = the `seq` of the event being processed (the
  generator numbers events 1, 2, 3, ...). Stops during a liquidation sale have no event count.
- **Timing** (`bench/bench_time.py`, Phase 6a). `time.perf_counter` around the replay loop only;
  the garbage collector stays **enabled** (default Python behaviour); `gc.collect()` runs before each
  replay, outside the timed region, so that every replay starts from the same heap state. Each run
  parses its file once (gzip + JSON, saved as `parse_seconds`, not part of the replay time). Every
  replay (warm-up and the 5 timed ones) uses a fresh empty book; results are discarded, not stored.
  Throughput = events divided by the median replay seconds (the single measurement if
  `repeats=1`). Output: `results/time_raw.csv` (one row per replay; the median of the run is on every
  row of that run) and `results/env.json` (Python, macOS, machine, git commit, constants).
  *Change record:* the first draft of these rules disabled `gc` during replays. Bastian decided to
  keep it enabled; a first benchmark run started with `gc` disabled was stopped after 33 runs
  (the 1,000-event streams and the first 10,000-event run) and its files were discarded, so no
  reported number comes from it.
  *Incident, run 1 (machine state):* the first full 6a grid showed Version B on `buildup` with
  100,000 events at about 0.20 s for seeds 42 and 43 and about 0.09 s for seed 44, each stable inside
  its own run. The code and the data did not change between those runs, so the machine changed state
  (Bastian was using it; it may also have been on battery). That file is kept unchanged as evidence
  (`results/time_raw_run1.csv`, `results/env_run1.json`) and no reported number comes from it. Run 1
  did not record the start time or the power state, so the cause is not proven. Changes for run 2:
  (1) every row has `start_utc` (start of its run), `power_source` (`ac`/`battery`),
  `battery_percent` and `low_power_mode` (read with `pmset`), and `env.json` has `power_at_start`;
  (2) a **canary** runs before and after each block of runs (a block = all runs of one scenario and
  one event count): Version B, `mixed`, 100,000 events, seed 42, warm-up + 5 repeats, same rules as
  every run, saved in `results/canary_raw.csv` with `block` and `canary_point`. If the canary
  median differs between points, or from the start, the runs in between were taken on a machine in a
  different state and are not comparable; they are re-run, not corrected. (3) The whole grid is run
  again into a new `results/time_raw.csv`. The machine must be on AC power, Low Power Mode off, and
  not used during the run.
- **Instrumented runs, Phase 6b** (`bench/bench_latency.py`, `bench_memory.py`, `bench_counts.py`)
  are separate runs, never part of the primary timing, one after the other, under the same
  conditions as timing run 2: AC power, Low Power Mode off, machine idle. Every result row has
  `start_utc`, `power_source`, `battery_percent`, `low_power_mode`. Each module runs in blocks (one
  module and one event count) with the canary of run 2 before and after the block
  (`results/canary_raw.csv`); a block whose canary medians differ clearly is repeated. Streams: seed
  42; latency and memory 10,000 and 100,000 events, counters 1,000 and 10,000 (small M). A runs at
  100,000 events only if its timing run at that size and scenario finished with a median below 60 s
  (same threshold as rule 3); otherwise `not_run`. No instrumented run uses the 1,000,000-event files.
  Each run is a child process with the 600 s limit.
- **Latency** (`results/latency_summary.csv`). `perf_counter_ns` before and after every `process`
  call, gc enabled as in the timing runs; the cost of the timer pair is measured and reported
  (`timer_overhead_ns`), not subtracted. Nearest-rank percentiles: for n sorted values, the p-th
  percentile is the value at rank ceil(p/100 * n), 1-based (p50, p95, p99). Rows per event type
  (`ALL`, `LIMIT`, `CANCEL`, `MARKET_SELL`; no row if the window holds none of that type) and per
  window: `all`, `first1000`, `last1000` (the first and the last 1,000 events of the stream, to see
  how latency changes while the book grows; asked for `buildup` and `crowded`, computed for every
  scenario), plus 20 equal chunks in order (`latency_by_position.csv`). It is processing time per
  event only, not queueing, not 1 / throughput.
  *gc test* (`python -m bench.bench_latency --gc-test`, `results/latency_gc_test.csv`): B on `buildup`
  with 100,000 events, gc off and gc on, each twice, canary before and after. Max latency: gc on
  13.1 ms and 12.4 ms (at events 91,228 and 44,613, with a second spike of 7.1 and 7.8 ms), gc off
  0.82 ms and 0.88 ms. So the ~12 ms spikes are garbage-collector pauses (full collections while
  the book holds ~10^5 live records). With gc off the largest remaining events sit at 10,922,
  21,845, 43,690 and 87,381, the order-index dict growing at 2/3 of its capacity (a dict of
  16,384, 32,768, 65,536 and 131,072 slots holds 10,922, 21,845, 43,690 and 87,381 entries before it
  is resized). Checked: `sys.getsizeof` of a dict filled with 100,000 string keys jumps when the 10,923rd,
  21,846th, 43,691st and 87,382nd key is inserted, which are event indices 10,922 ... 87,381 in `buildup`
  (one insert per event). Each resize is one longer insert; the cost per insert stays amortized O(1).
- **Memory** (`results/memory.csv`). `tracemalloc`, started after the events are loaded, with a fresh
  book. Counted: Python allocations made during the replay that are still alive at the moment of
  measuring: book structures, the order index, the current result dict and fill list (discarded
  after each event), temporary objects. `peak_bytes` is the maximum of that sum during the replay
  (`reset_peak` at the start); `final_bytes` is the sum after the last event ("after replay").
  Also every 10% of the events (`checkpoints_bytes`) and, for `insert_then_cancel`, after the
  insertions. Not counted: the input event list, the interpreter, native memory, allocator slack
  and fragmentation. No trade history is kept (SPEC D16). tracemalloc slows the replay, so no
  timing comes from these runs, and the numbers are not total process memory.
- **Counters** (`results/counters.csv`). The engines are wrapped, not modified. A: records examined by
  the scans (`scan_is_live`, `scan_best_index`, `scan_cancel`). B: elements moved when a price
  level is inserted or deleted in the sorted price list, levels dropped, compactions and records
  moved. Both: `fills`, `levels_visited` (distinct fill prices per event, summed).
- **Phase 6c** (`bench/liquidation.py`, `bench_concentration.py`, `bench_churn.py`, `bench_flood.py`,
  `bench_fairness.py`): same conditions as 6a and 6b (AC power, canary before and after each block,
  start time and power state on every row, gc enabled, 600 s limit, 60 s single-measurement rule).
- **Liquidation** (`results/liquidation_summary.csv`, `liquidation_raw.csv`). Book = first N BUY
  limits of the `buildup` stream (1,000 price levels), seed 42, N = 10,000 (A and B) and 100,000
  (B; A under the same 600 s limit: if the build or sale of a trial reaches it, the trial is
  `stopped` and the remaining sale sizes of that book are `not_run`, nothing is estimated); sells of
  ceil(10%), 100% and 200% of the total bid quantity (integer arithmetic); fresh book per trial;
  only the sell is timed (build time saved separately). Per trial: `fills` (= makers touched, each
  maker appears once), `price_levels_visited` (distinct fill prices), `unfilled_qty_units`, and a
  hash of the fill list (A and B must agree). Rule 2 applies per (version, book, sale size), with
  one trial (build + sell) as the "replay". The first draft disabled gc during trials; it was
  changed to enabled before any liquidation result was produced.
- **Queue concentration** (`results/concentration_raw.csv`). `buildup`, 100,000 events, seed 42, 4 /
  16 / 64 / 256 / 1,000 / 4,000 price levels, A and B, the usual timing rules; the 1,000-level
  stream is measured again here so all six levels share one set of conditions. Price-time
  correctness on these streams: A-vs-B comparison in `tests/test_generated_data.py`.
- **Cancel churn** (`results/cancel_churn_scaling.csv`). M = 1,000 ... 1,000,000: time from timing run
  2 (median, seconds per event) and a fresh `tracemalloc` run per M (held after the replay, peak,
  every 10%). "No growth" = the bytes stay flat while M grows 1,000-fold.
- **Flood** (`results/flood_peaks.csv`). Peak active orders B and peak price levels P of the
  `buildup` and `crowded` streams, from `results/workload_peaks.csv`.
- **Fairness check** (`results/fairness_time.csv`), 10,000 events only: A, **`A_idset`** (A plus a
  set of live order ids so that "is this id live?" is O(1); `bench/variants.py`, everything else is
  A's code, results identical to A after every event in `tests/test_bench.py`) and B on the five
  scenarios. The variant is labeled in the `version` column and never replaces Version A.


## Dashboard

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run dashboard/app.py
```

The dashboard only **loads** the files in `results/`. It never imports the order books or the benchmark
code and never starts a replay (`tests/test_dashboard.py` checks this). Pages: Overview, Scaling
(log-log; stopped runs marked with a cross at the 600 s limit, not-run runs with a diamond at the top, both
without a value), Throughput, Latency (p50/p95/p99/max by event type, first against last 1,000 events,
gc on and off), Memory (including the state after cancellations and cancel churn), Liquidation,
Concentration, Fairness, Correctness, Run-1 incident (with the canaries), Workload and raw repeats, and
Why A is slow (code, operation counts, complexity). A is orange and B blue on every page; the labeled
variant `A_idset` is a lighter orange. `?page=Scaling` in the URL opens a page directly.


## Measured-data definitions

All files are in `results/`; each row says when it was taken (`start_utc`) and on which power source.
Times are seconds from `time.perf_counter`; sizes are bytes; `events` is the number of events M.

| File | One row is | Main columns |
|---|---|---|
| `time_raw.csv` | one replay (warm-up or timed repeat) of one stream by one version | `version, scenario, seed, events, levels, status, phase, repeat, elapsed_seconds, median_seconds` (median of the run, repeated on each row), `parse_seconds` |
| `time_raw_run1.csv`, `env_run1.json` | the same, from the discarded first run | evidence only (REPORT section 5) |
| `canary_raw.csv` | one replay of the canary (B, mixed, 100,000 events) before or after a block | `block, canary_point` and the columns of `time_raw.csv` |
| `latency_summary.csv`, `latency_by_position.csv`, `latency_hist.json` | percentiles of per-event latency, by event type and window; 20 chunks; log2 histogram | `p50_ns, p95_ns, p99_ns, max_ns`, `timer_overhead_ns` |
| `latency_gc_test.csv` | B buildup 100,000 events with gc off and on | `label, max_ns, events_over_1ms, top5_index_ns` |
| `memory.csv` | `tracemalloc` run of one stream | `final_bytes` (after the replay), `peak_bytes`, `checkpoints_bytes` (every 10%) |
| `counters.csv` | operation counts of one stream | A: `scan_is_live, scan_best_index, scan_cancel`; B: `key_shift_elements, compactions`; both: `fills, levels_visited` |
| `liquidation_raw.csv`, `liquidation_summary.csv` | one trial / one (version, book, sale size) of a large market sell | `sale_qty_units, sell_seconds, fills, price_levels_visited, unfilled_qty_units, fills_digest` |
| `concentration_raw.csv`, `fairness_time.csv` | timing rows as in `time_raw.csv` for 4 to 4,000 price levels; for A, `A_idset` and B | `levels`; `version` |
| `cancel_churn_scaling.csv`, `flood_peaks.csv`, `workload_peaks.csv` | cancel churn against M; peak active orders B and price levels P per stream | `final_bytes, time_per_event_ns`; `peak_active_orders, peak_price_levels` |
| `correctness.csv` | one stream compared A against B after every event | `all_results_equal, best_prices_equal, final_book_equal` |
| `data_checksums.json`, `generated_data_checksums.json` | checksums of the supplied and the generated streams | `decompressed_sha256` (identity), `gz_sha256` (depends on zlib) |
| `env.json` | the machine and code of the timing runs | Python, macOS, hardware, git commit, constants |

`status` is `ok`, `stopped` (a replay reached 600 s; the time is not known), `not_run` (skipped by a declared
rule; the reason is in `reason`) or `error`. A stopped or not-run row never has a median. `levels` is the number
of price levels the generator was set to (1,000 unless a concentration stream). The rules are above.

## Submitted code version

**Code commit: `23b6e74`** (branch `assignment1-BundschuhBastian`): the last commit that changed code, tests,
results or `requirements.txt`. Commits after it change only documentation (README, REPORT, AI_LOG, CLAUDE.md).
Checked in a fresh clone of the pushed branch with a new Python 3.11.0 virtual environment:
`pip install -r requirements.txt`, `pytest -q` (454 passed), `tools/verify_data.py` (all supplied files match),
the worked-example replay for A and B (gross value 359,400.00 USD), and `streamlit run dashboard/app.py --server.headless true`
(health check 200, pages render).
