# Assignment 1: Build and benchmark a limit order book

Huang Jiaxin, Algorithms in Finance, take-home exercise. Due 26 November 2026, 18:00.

A sequential, single-venue BTC limit order book in Python with price-time (FIFO) priority,
two implementation versions (a transparent baseline A and a revision B), tests written
first, time and memory benchmarks, and a dashboard built from saved results.
The full write-up is in **[REPORT.md](REPORT.md)**.

## Modelling boundaries

One venue, one event at a time, in `seq` order. All orders are eligible. No fees, account
balances, hidden orders, self-trade checks, network delays or simultaneous execution. The
data are synthetic teaching data from the course generator; they are not historical
exchange records and not calibrated to any exchange. This is a teaching model, **not a
production trading system**.

## Quick start (clean environment)

Python 3.11 or newer. From this folder:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests                                   # expected: 207 passed
python replay.py data/supplied/worked_example.jsonl         # the course example
bash run_all.sh                                             # everything (about 40 to 60 min)
streamlit run dashboard.py                                  # http://localhost:8501
```

`bash run_all.sh --quick` runs a smaller grid in a few minutes. The declared time limit
per run is 30 seconds (`LOB_TIME_LIMIT_S`); runs above it are recorded as `stopped`.

### With Docker (optional)

```bash
docker build -t lob-a1 .
docker run --rm -v "$(pwd)":/app -e CODE_COMMIT=$(git rev-parse HEAD) lob-a1 bash run_all.sh
docker run --rm -p 8501:8501 -v "$(pwd)":/app lob-a1
```

`CODE_COMMIT` records the code version, because the container has no git.

### Expected output of the worked example

```
$ python replay.py data/supplied/worked_example.jsonl
version B, file data/supplied/worked_example.jsonl
results by status: filled 1, resting 5
maker fills: 4, gross proceeds: 3594000000000000 tick-units = 359,400.00 USD
bids: 1 active orders
            b4    59,700.00 USD   4.00000000 BTC  arrival 4
asks: 1 active orders
            a1    60,100.00 USD   2.00000000 BTC  arrival 5
```

The market sell `s1` fills b1: 1, b2: 1, b3: 3 and b4: 1 BTC, matching the course's
`worked_expected.json` (`--version A` gives the same output).

## Interface

Both versions (`lob/book_a.py: OrderBookA`, `lob/book_b.py: OrderBookB`) have the same
methods; the full description is in `lob/interface.py`.

| Method | Assignment name | Input | Returns |
|---|---|---|---|
| `process(event)` | event dispatcher | any event dict | the result of the matching method, or a rejection |
| `add_limit_order(event)` | `AddLimitOrder` | LIMIT event | `{event_id, order_id, status: filled/resting, unfilled_qty_units, fills}` |
| `fill_market_sell(event)` | `FillMarketSell` | MARKET_SELL event | `{event_id, order_id, status: filled/partial/unfilled, unfilled_qty_units, fills}` |
| `cancel_order(event)` | `CancelOrder` | CANCEL event | `{event_id, target_order_id, status: cancelled/not_found, cancelled_qty_units}` |
| `snapshot()` | book inspection | none | `{bids: [...], asks: [...]}` in canonical price-time order |
| `best_bid()`, `best_ask()` | | none | price in ticks or `None` |

A fill is `{maker_id, taker_id, price_ticks, qty_units}`; fills are listed in execution
order. A rejection is `{event_id, status: "rejected", reason}`. Only the current event's
fills are returned; no trade history is stored.

## Files

| Path | Content |
|---|---|
| `lob/` | `book_a.py` (version A), `book_b.py` (version B), `validation.py` (shared rules), `interface.py`, `events_io.py` |
| `tests/` | written before the implementation; every test runs on both versions |
| `bench/experiments.py` | timing: replay, large liquidation, queue concentration, churn |
| `bench/instrumentation.py` | separate runs: per-event latency, tracemalloc memory, operation counts |
| `bench/profile_run.py` | cProfile (diagnostic) |
| `replay.py` | replay any event file through either version |
| `make_data.py`, `generate_orders.py` | dataset generation with checksums (course generator, unchanged) |
| `dashboard.py` | Streamlit dashboard; loads `results/` only |
| `results/` | saved raw results and environment metadata |
| `evidence/` | saved test runs at each step |
| `TRACE.md` | hand trace of the worked example through version B |
| `REPORT.md` | specification, correctness, runtime, memory, profiling, revision, limitations |

## Measured-data definitions

| Column / file | Meaning |
|---|---|
| `elapsed_s` (`timing_raw.csv`) | seconds for one complete replay of a preloaded event list on a fresh empty book (phase `replay`), or for reading and parsing the file (phase `parse`) |
| `events_per_s` | throughput: events divided by replay seconds |
| `peak_active_orders`, `peak_price_levels` | largest number of active orders B and occupied price levels P (both sides) during the stream |
| `status` | `ok`, or `stopped` when the untimed warm-up exceeded the declared 30 s limit; stopped runs have no timing values |
| `construction_s`, `sale_s` (`liquidation_raw.csv`) | building the bid book by replaying the stream; the single market sell (matching, state updates and fill list) |
| `requested_units`, `fill_count`, `makers_touched`, `price_levels_visited`, `unfilled_units` | sale request in 1e-8 BTC, fills, distinct makers, distinct prices, discarded remainder |
| `vwap_ticks`, `best_bid_ticks`, `worst_fill_ticks` | average fill price, best bid before the sale and lowest fill price, in 0.01 USD |
| `p50_us`, `p95_us`, `p99_us` (`latency_summary.csv`) | per-event engine latency in microseconds; nearest-rank percentiles |
| `replay_peak_bytes`, `book_bytes_after_replay` (`memory.csv`) | tracemalloc peak during the replay and traced size after it; the preloaded input is excluded and reported as `input_bytes_preloaded` |
| `stale_deque_entries`, `stale_heap_entries` | version B entries that no longer belong to an active order or price level |

Timing rules: `time.perf_counter`; one untimed warm-up; 5 timed repeats, all saved; the
median is reported; garbage collection is disabled during timed blocks; data generation,
tests, printing and dashboards are outside timing; memory and operation counts run
separately from timing.

## Data

All event data are synthetic teaching data from the course generator, not historical
exchange records, and not calibrated to any exchange.

* `data/supplied/`: the course package files, unchanged (five 10,000-event samples with
  seed 42, the worked example and its expected result, and the course `MANIFEST.json`).
* `generate_orders.py`: the course generator, unchanged (its SHA-256 matches the course
  manifest).
* `python make_data.py` generates every benchmark input **outside timing** into
  `data/generated/` (not committed) and records the exact command, settings and SHA-256 of
  each file in `data/generated_manifest.json`. `python make_data.py --million` adds the
  one-million-event streams.
  * Main grid: 5 scenarios × M ∈ {1,000; 10,000; 100,000} × seeds {42, 43, 44}, 1,000 price
    levels per side.
  * Queue concentration: `buildup` with 4 price levels per side, M ∈ {10,000; 100,000},
    seeds {42, 43, 44}, compared with the same streams at 1,000 levels.
* Check: the generator reproduces the five supplied samples byte for byte
  (`make_data.py` verifies the supplied checksums; the seed-42, 10,000-event files in the
  generated manifest have the same SHA-256 as the supplied ones).
* `lob/events_io.py` reads JSON Lines files, plain or gzip-compressed, either streamed
  (`iter_events`) or preloaded (`read_events`). Reading and parsing are timed separately
  from the matching engine.

## Tests (written before the implementation)

`python -m pytest -q tests` runs every test against **both** versions.

| File | What it checks | Expected values from |
|---|---|---|
| `test_worked_example.py` | the course example: fills b1:1, b2:1, b3:3, b4:1 BTC, 359,400 dollars, remaining book | course `worked_expected.json` |
| `test_matching.py` | empty book; one order; sells smaller than, equal to and larger than depth; several makers at one price; several price levels; partial fill then another sale; cancellation before/after partial and full fills; repeated and unknown cancels; crossing buys and sells at resting prices; residual limits; identifiers whose spelling differs from arrival order; a queue of 1,000 orders at one price | calculated by hand |
| `test_validation.py` | 25 kinds of invalid events (type, side, zero/negative/float/string/bool prices and quantities, missing fields, duplicate live identifiers, nonincreasing seq) leave the book and the last accepted seq unchanged | the rules in the assignment |
| `test_invariants.py` | after every event of 20 random streams: no crossed book, positive quantities, no order stored twice, canonical order; incoming quantity = fills + residual; each maker loses exactly its fills at its own price; cancels remove exactly the residual; fills follow price-time priority; market residuals never rest | checked from snapshots, independent of the implementation |
| `test_equivalence.py` | versions A and B give identical results and books after every event (30 random streams, the five supplied 10,000-event samples) | comparison between versions |

Before any implementation, both versions were empty stubs. The run is saved in
`evidence/step3_tests_before_implementation.txt`: 152 tests failed and 37 passed. The only
passes were the empty-book test for each version (an empty stub is a correct empty book) and
all 35 equivalence tests (30 random streams, 5 samples), because two empty stubs trivially
agree with each other. This is why agreement between
versions is only extra evidence and never replaces the hand-calculated expected results.
