# Assignment 1 — Limit order book (Version A and Version B)

Bejoy Padamadan · Algorithms in Finance · submitted 26 November 2026

A sequential, single-venue BTC limit order book in Python with a list-based baseline (Version A) and a revised version with price levels, FIFO queues and an order index (Version B). Academic project on synthetic data, not a production trading system. See `REPORT.md` for correctness reasoning, complexity, results and limitations.

## Project structure

| Path | Content |
| --- | --- |
| `orderbook/version_a.py` | Version A: one list of orders, scanned for the best order |
| `orderbook/version_b.py` | Version B: `{price: deque}` per side, sorted price lists, `{order_id: order}` index |
| `orderbook/validation.py` | event validation shared by both versions (spec rule 6) |
| `tests/test_cases.py` | 19 hand-calculated tests (run against A or B) |
| `tests/test_compare_versions.py` | randomised generator + A-vs-B comparison after every event |
| `replay.py` | replay one event file through A or B |
| `benchmark.py` | timing, latency, memory, liquidation and correctness experiments → `results/` |
| `dashboard.py` | builds `results/dashboard.html` from the saved CSV results |
| `generate_orders.py`, `data/` | course generator and supplied sample data (worked example + five 10,000-event files) |
| `results/` | saved raw results, environment metadata and the dashboard |
| `REPORT.md`, `NOTES.md` | report; working log |

## Clean-environment run path

Requirements: Python 3.11 or newer (measured with 3.14.7); only the standard library, plus `pytest` for the tests.

```sh
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install pytest==9.2.0

python3 -m pytest -q                                   # tests on Version A  → 20 passed
ORDERBOOK_VERSION=B python3 -m pytest -q               # same tests on Version B → 20 passed
python3 replay.py data/worked_example.jsonl            # worked example, Version A
python3 replay.py data/worked_example.jsonl --version B
python3 benchmark.py --quick                           # ~5 s smoke run
python3 benchmark.py                                   # full run, ~30–40 min; regenerates data files
python3 dashboard.py                                   # rebuild results/dashboard.html from saved CSVs
```

Open `results/dashboard.html` in a browser (charts load Chart.js from a CDN, so an internet connection is needed).

## Interface

`OrderBook()` (same in both versions):

- `process_event(event: dict) -> dict` — validates, then dispatches by `event["type"]`
- `AddLimitOrder(event) -> dict`, `FillMarketSell(event) -> dict`, `CancelOrder(event) -> dict`
- `snapshot() -> list[dict]` — active orders `{order_id, side, price_ticks, qty_units, arrival_seq}`; bids by price high→low then arrival, then asks low→high then arrival

Results: submissions return `event_id`, `order_id`, `status` (`resting`/`filled` for limits; `filled`/`partial`/`unfilled` for market sells), `unfilled_qty_units` and `fills` (ordered `{maker_id, taker_id, price_ticks, qty_units}`, current event only). Cancels return `event_id`, `target_order_id`, `status` (`cancelled`/`not_found`), `cancelled_qty_units`. Rejected events return `event_id`, `status: "rejected"`, `reason`.

## Expected worked-example output

`python3 replay.py data/worked_example.jsonl` (identical with `--version B`):

```
Version A: 6 events replayed
Status counts: {'resting': 5, 'filled': 1}
Last result: {
  "event_id": "event6",
  "order_id": "s1",
  "status": "filled",
  "unfilled_qty_units": 0,
  "fills": [
    {"maker_id": "b1", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000},
    {"maker_id": "b2", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000},
    {"maker_id": "b3", "taker_id": "s1", "price_ticks": 5990000, "qty_units": 300000000},
    {"maker_id": "b4", "taker_id": "s1", "price_ticks": 5970000, "qty_units": 100000000}
  ]
}
Remaining active orders: 2
```

(The script prints each fill over several lines.) Remaining: `b4` 4 BTC at 59,700 and `a1` 2 BTC at 60,100. Gross proceeds 3,594,000,000,000,000 tick-units = 359,400.00 USD.

## Measured-data definitions

Units: `price_ticks` = 0.01 USD per BTC; `qty_units` = 0.00000001 BTC; times in seconds (`_s`) or microseconds (`_us`); memory in bytes.

`results/timing.csv` — one row per raw repeat (primary timing run)
- `version` A/B (`-` for the parse row); `scenario`; `seed`; `events` = M (all events incl. cancels and sells)
- `phase`: `parse` = gzip + JSON reading; `replay` = engine only, fresh empty book
- `repeat` 1–5 (after 1 unrecorded warm-up); `elapsed_s`
- `status`: `ok` or `stopped>30s` (declared limit; no time recorded, never estimated)
- `active_peak` / `level_peak`: maximum active orders / occupied price levels during the stream

`results/latency.csv` — separate instrumentation run, seed 42
- per-event `time.perf_counter_ns` around `process_event`; `window` = `all`, `first10pct`, `last10pct` of events
- `p50_us`, `p95_us`, `p99_us`: nearest-rank percentiles (smallest value with at least p% of values ≤ it). Processing latency only; excludes queueing/network.

`results/memory.csv` — separate `tracemalloc` run, seed 42
- `peak_traced_bytes`, `final_traced_bytes` (still allocated at the end, e.g. after cancel churn), `final_active_orders`
- Boundary: events preloaded before tracing (input excluded); book and per-event result dicts included; no trade history kept.

`results/liquidation.csv` — one market sell against a fresh bid book built from the first M buildup events (seed 42), rebuilt for every repeat
- `pct` 10/100/200 of total bid quantity, `requested_qty` (rounded up, ≥ 1 unit); `build_s` (construction) and `sell_s` (matching + updates + fill list) timed separately
- `fills`, `makers_touched`, `levels_visited`, `unfilled_qty`

`results/correctness.csv` — A and B results identical after every event and identical final books (M ≤ 10,000, all seeds); worked example matches `data/worked_expected.json` for both versions.

`results/environment.json` — Python version, OS, machine, git commit measured, generator settings, time limit, repeats, percentile convention, memory boundary.

## Data and reproducibility

Generated event files are not committed (`.gitignore`); their settings and SHA-256 checksums are in `data/*_s*.jsonl.gz.metadata.json`. To regenerate one file:

```sh
python3 generate_orders.py --scenario buildup --events 100000 --levels 1000 --seed 42 --out data/buildup_100000_s42.jsonl.gz
```

`benchmark.py` regenerates all of them (scenarios buildup, crowded, mixed, sweep, cancel_churn × 1,000 / 10,000 / 100,000 events × seeds 42, 43, 44, levels 1000). A one-million-event run was not attempted within the time available.

## Code version

- Version A: commit `e2a5a74`; validation: `1ccf24c`; Version B: `dfc4322`
- Benchmark results measured at commit `0f700e4` (recorded in `results/environment.json`)
- Submitted commit: `1c780d5`
