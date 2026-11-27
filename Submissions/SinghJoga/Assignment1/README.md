# Student quick start — Assignment 1

This section is a student-added entry point. The original professor-provided
assignment specification begins immediately below and is otherwise preserved.
Because this authorized addition changes `README.md`, its SHA-256 will differ
from the supplied `MANIFEST.json` entry; the manifest is retained as historical
package evidence, not rewritten.

From the repository root, open PowerShell and change to this assignment:

```powershell
cd .\Submissions\SinghJoga\Assignment1
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m orderbook.replay data\worked_example.jsonl --version baseline
.\.venv\Scripts\python.exe -m orderbook.replay data\worked_example.jsonl --version revised
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

Python 3.14.7 was used; pinned dependencies are in `requirements.txt`.
The full test suite is expected to pass (185 tests at the latest full run).
The 10,000-event supplied-stream parity check completed for mixed and
cancel-churn; buildup, crowded, and sweep remain partial after their
individual 60-second limits. See [`docs/test_coverage.md`](docs/test_coverage.md)
for the completed event counts and preserved progress.
Both worked-example replays should finish with the ask unchanged, 4 BTC
remaining on `b4`, and gross proceeds of `$359,400`. See
[`RUNNING.md`](RUNNING.md) for all commands, [`docs/report.md`](docs/report.md)
for results and limitations, and [`dashboard/app.py`](dashboard/app.py) for
the saved-results dashboard. The dashboard reads existing evidence only; it
does not launch benchmarks.

# Professor-provided assignment specification

# Assignment 1 — Build and benchmark a limit order book

This take-home exercise extends **Phase 1: Implement and measure** of the coding lab. The assignment slides are `AlgorithmsFinance_Exercise1.pdf`. Work individually, using the same tests throughout implementation and revision. Submission is due 26 November 2026, 18:00:00h. Grading weights are not specified here.

## Task and financial model

Implement a sequential, single-venue Bitcoin (BTC) limit order book in Python, including your own `FillMarketSell`. Compare a transparent baseline with an improved implementation. Test first; implement; revise without weakening the tests; measure time and memory; build a dashboard from saved results; submit a reproducible project.

A limit buy is willing to pay at most its limit price; a limit sell accepts at least its limit price. A market sell accepts the available bids until its quantity is exhausted or the book runs out. At each price, earlier resting orders execute first: **first-in, first-out (FIFO)** priority. This is continuous matching at existing resting prices, rather than a batch auction with one clearing price.

All orders are eligible. There are no fees, account balances, hidden orders, self-trade checks, network delays or simultaneous execution. Document these modeling boundaries. Do not describe the result as a production trading system. Synthetic orders represent submissions to one venue, not the combined liquidity of several exchanges.

## Integer units

- `price_ticks`: positive integer cents; one price tick is **0.01 US dollars per BTC**.
- `qty_units`: positive integer units of **0.00000001 BTC**. Thus one BTC is 100,000,000 units.
- A trade with `price_ticks=p`, `qty_units=q` has gross value `p*q` in tick-times-quantity units. Divide the total by 10,000,000,000 to express proceeds in dollars. Use integers for matching and conservation checks; round only for display.
- `seq`: strictly increasing positive integer defining arrival order. Do not use the spelling of an identifier to decide priority.

## Input files and interface

Files use JavaScript Object Notation (JSON), with one JSON object per line (JSON Lines). Files ending `.gz` use gzip compression. Use the Python standard library `json` and `gzip` to read them. All benchmark streams start with an empty book and must be replayed in `seq` order.

Each event has `seq`, unique `event_id`, and `type`. Submission `order_id` values are globally unique in the supplied valid streams. Do not assume a cancel target is still active.

| Type | Additional required fields | Meaning |
|---|---|---|
| `LIMIT` | `order_id`, `side` (`BUY` or `SELL`), `price_ticks`, `qty_units` | Match against eligible opposite-side orders; rest any residual at the limit. |
| `MARKET_SELL` | `order_id`, `qty_units` | Call your own `FillMarketSell`; discard any unfilled residual rather than resting it. |
| `CANCEL` | `target_order_id` | Remove the target's entire remaining quantity, if still active. |

For example:

```json
{"seq":1,"event_id":"event1","type":"LIMIT","order_id":"b1","side":"BUY","price_ticks":6000000,"qty_units":100000000}
{"seq":2,"event_id":"event2","type":"MARKET_SELL","order_id":"s1","qty_units":100000000}
```

Provide `AddLimitOrder`, `CancelOrder`, `FillMarketSell`, an event dispatcher, and a book-inspection function. You may choose Python method signatures, but document them and supply a command to replay a file. Both implementation versions must accept the same event files and return equivalent results.

### Matching rules

1. A limit buy crosses when its limit is at least the lowest ask. A limit sell crosses when its limit is at most the highest bid. Take the best available opposite-side price first, then arrival order at that price.
2. Execute `min(incoming remaining quantity, resting remaining quantity)` at the **resting order's price**. Continue while crossing prices and positive quantities remain.
3. An exhausted resting order is removed. A partially filled resting order retains its original arrival priority. A residual incoming limit order joins its own price queue after the earlier orders there, using its original event `seq` as its arrival rank.
4. `FillMarketSell` uses the highest bid first, then lower bids, obeying the same queue priority. It mutates the live book. The lecture's read-only fill plan is therefore extended to update individual orders and queues.
5. Cancelling an active order removes only its remaining quantity, including after a partial fill. Cancelling a fully filled, already cancelled or unknown order is a no-op with status `not_found`.
6. Invalid events (unknown type/side, noninteger or nonpositive prices/quantities, duplicate live submission identifiers, or nonincreasing `seq`) are rejected without changing the book. Rejected events do not advance the last accepted sequence. Cancellation of an unknown target is valid. Validation of historical identifier reuse is outside scope; valid submissions are assumed globally unique.

After each valid event, there must be no crossed resting book, no nonpositive resting quantities, and no active order stored in two places. Best bid/ask may be absent if that side is empty.

### Required results

Return an ordered fill list containing `maker_id` (resting order), `taker_id` (incoming order), `price_ticks`, `qty_units`; preserve execution order. Include `event_id`, incoming `order_id`, `status`, and `unfilled_qty_units` on submission results. For limits, `status` is `filled` if nothing rests, otherwise `resting`. For market sells, use `filled` if the request is completed, `partial` if it trades but is not completed, or `unfilled` if nothing trades. Unfilled market quantity never becomes an order in the book.

A cancellation returns its `event_id`, `target_order_id`, status `cancelled` or `not_found`, and `cancelled_qty_units` (zero for `not_found`). Rejected results return `event_id` if available, status `rejected`, and a reason. Return only the current event's fills; retaining the entire trade history is optional and must be identified as extra storage.

Book inspection returns active orders with their side, price, remaining quantity and original arrival sequence. For comparison, sort bids by decreasing price then arrival and asks by increasing price then arrival. Compare identifiers and quantities as well as aggregate depth.

## Worked example and tests first

`data/worked_example.jsonl` submits two one-BTC buys at 60,000, a three-BTC buy at 59,900, a five-BTC buy at 59,700, and a two-BTC ask at 60,100 dollars. It then sells six BTC. `data/worked_expected.json` supplies the expected final sell result and remaining orders.

The four resting makers fill in this order: `b1:1`, `b2:1`, `b3:3`, `b4:1` BTC. Four BTC remain on `b4`; the ask is unchanged. Gross proceeds are **359,400 dollars**. This extends the lecture's three price levels with individual resting order identities.

Before implementing, write independent expected outcomes for at least: empty book; one order; zero/negative/invalid input; sale smaller than, equal to and larger than available depth; multiple makers at one price; multiple price levels; a partial fill followed by another sale; cancellation before/after partial or full filling; repeat/unknown cancellation; crossing limit buys and sells; noncrossing residual limits; identifier order different from arrival order; and a long queue at one price. Confirm tests initially fail for the missing or incorrect behavior.

Check conservation: submitted incoming quantity equals its fills plus returned residual; a maker loses exactly its executed quantity; a cancellation removes exactly the residual; and proceeds equal the sum of price times quantity. Do not count a discarded market residual as resting liquidity. Add small generated tests and compare your two versions after **every event**, including their ordered fills and canonical remaining books. Neither agreeing versions nor one supplied example replaces independently calculated tests.

## Implement and revise

Build Version A as a clear baseline, for example scanning/sorting a list of individual orders. Build Version B using a justified data organization or meaningful revision. Library lists, dictionaries, queues, sorting and heaps are allowed; an existing matching engine is not. You must write the matching logic yourself.

Explain the invariants supporting price-time priority and quantity conservation. Give pseudocode and runtime/space reasoning for insertion, cancellation and market selling for the implementations actually measured. Distinguish active orders `B`, occupied price levels `P`, incoming events `M`, and maker fills `F`. More submitted events need not imply a larger active book. Include validation, output construction, index updates, inactive entries and cleanup in the costs where applicable. If using delayed cleanup, explain whether a claim is worst-case, expected or amortized.

Preserve both versions. Run unchanged tests after the revision; add tests for discovered bugs without weakening existing expected results. Record what changed, why, and which artificial intelligence (AI) suggestions you accepted, corrected or rejected if you used AI, as in the lab.

## Synthetic data supplied

The generator requires only the Python standard library and was checked with Python 3.11.9.

All supplied event data are independently generated teaching data, **not sampled or calibrated historical exchange records**. There is no matching solution in the generator. Cancel targets may already have disappeared; this deliberately exercises `not_found` behavior.

| Sample | Purpose |
|---|---|
| `buildup_10000.jsonl.gz` | Passive submissions on both sides grow the active book over many prices. |
| `crowded_10000.jsonl.gz` | Passive submissions concentrate on four prices per side; long arrival queues. |
| `mixed_10000.jsonl.gz` | Mixed additions (including crossing limits), cancellations and market sells; intentionally sell-heavy, so bids can frequently exhaust. |
| `sweep_10000.jsonl.gz` | First 80% builds the book; later sells sweep depth, with a final deliberately oversized sale. |
| `cancel_churn_10000.jsonl.gz` | Alternate one submission and its cancellation; active size stays tiny while event count grows. |

Each sample contains exactly 10,000 events, seed 42. Metadata files record units, settings and Secure Hash Algorithm 256-bit (SHA-256) checksums (content fingerprints). Generate larger inputs **outside timing**:

```sh
python generate_orders.py --scenario buildup --events 100000 --levels 1000 --seed 42 --out data/buildup_100000.jsonl.gz
python generate_orders.py --scenario mixed --events 1000000 --levels 1000 --seed 43 --out data/mixed_1000000.jsonl.gz
```

`--events` is total event count, including cancels and sells; it is not active-order count. `--levels` is the available passive price range per side; `crowded` instead uses four prices per side. The fixed price reference is 60,000 dollars; queues, sizes and bursts are stylized and do not model strategic behavior or realistic event timing. Sequence numbers order events; do not interpret them as elapsed market time.

## Benchmark experiments

Use at least `M = 1,000; 10,000; 100,000` events and several seeds, including 42, 43 and 44, across the five workload families. Try one million events if feasible; report a declared time/memory limit and any stopped run rather than silently omitting it. Apply the same workload and limits to both versions. A slow baseline may be stopped and reported as such; never invent its missing results.

Separate these questions:

1. **Submission flood:** how does processing scale with many resting orders? Measure book construction and full-stream processing; record active-order and occupied-price peaks.
2. **Large liquidation:** against the same fresh bid book, independently test sale sizes of 10%, 100% and 200% of its available bid quantity. Use integer quantities (round 10% up to at least one unit). Count maker orders touched, price levels visited, fills and the unfilled remainder. A repeated test must not reuse an already depleted book.
3. **Queue concentration:** hold the initial order count fixed and vary the number of prices (for example 4 versus 1,000). Test price-time correctness as well as speed.
4. **Cancellation churn:** show memory and time after many cancellations when few orders remain active; detect unbounded stale-entry or history accumulation.

For small diagnostic runs, record operation counts to explain the plots. Run counters and heavy instrumentation separately from primary timing. Do not extrapolate a one-dimensional bound without controlling active depth, fill count and workload mix.

### Time and latency

Use `time.perf_counter`, warm up, repeat five times and keep **every raw repeat** plus its median. Give each implementation the same pre-generated events and a fresh empty book for every replay. Report JSON/gzip reading and parsing separately from engine replay; full application time can additionally include both. Do not hide book construction or copying as free when reporting total cost. For fixed-book sell tests, report construction/reset time separately and include matching, state updates and fill-list construction in the measured sell.

Report throughput (events divided by replay seconds). In a separate instrumentation run, record per-event processing times and median, 95th and 99th percentiles using a documented percentile convention. This is algorithm processing latency; it excludes queueing/network latency and cannot establish real-time overload capacity. Never infer latency from the reciprocal of total throughput. For submission bursts, process long uninterrupted batches and record latency near the beginning and end as the book grows.

### Memory

Use `tracemalloc` in a separate run. Report peak traced bytes and whether preloaded event input, book structures, returned fills and saved history are included. Also measure book growth during insertion and after cancellation churn. Explain why measured allocation is not identical to auxiliary space or total process/native memory. If preloading becomes too large, stream inputs and report input parsing separately, with the changed measurement boundary explicit.

### Results and dashboard

Save a machine-readable comma-separated values (CSV) or JSON table containing version, scenario, seed, event count, active-order/price-level peaks, requested quantity for sell tests, fill count, phase, repeat, elapsed seconds and traced peak bytes (where measured). Keep timing and memory runs distinguishable. Record Python, dependencies, machine, operating system, code version and generator settings.

Build a dashboard that loads saved results rather than rerunning experiments. Show construction, replay and individual-sale scaling; original versus revised versions; throughput and processing latency distributions; memory including post-cancellation state; and a table of correctness outcomes. Label units and missing/stopped runs. Explain at least one measured bottleneck using the code, operation counts and complexity reasoning. Do not assume your revised version must win on every workload.

## Submit a reproducible project

Use the course repository `https://github.com/cogeorg/AlgorithmsFinance`, under `Submissions/LastnameFirstname/Assignment1/`. Due 26 November 2026, 18:00:00h. Keep course folders and other students' work unchanged. Include:

- Both implementation versions, tests, your additional generators and exact run commands.
- Saved raw results, environment/settings metadata, dashboard code and dependency versions.
- A short report covering the specification, correctness reasoning, runtime, memory, profiling, revision and limitations.
- A README with a clean-environment run path, expected worked-example output and measured-data definitions.
- The commit identifier (a recorded code version) for the submitted work. Do not upload generated million-event datasets; supply generator commands and checksums instead.

Docker packaging remains **optional**, as in the lab. No peer audit is required for this take-home exercise. Do not include account credentials or proprietary data in the public submission.

## What is shared

This package contains the assignment PDF, generator, five small synthetic event files, a worked input/expected output pair, and a file-checksum manifest. Historical exchange snapshots are not supplied or required. Generate larger synthetic event streams locally using the commands above; no exchange-data account or download is needed. The synthetic workloads are not calibrated to an exchange and do not reconstruct historical trading.
