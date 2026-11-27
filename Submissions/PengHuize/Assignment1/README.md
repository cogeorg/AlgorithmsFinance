# Assignment 1: Build and benchmark a limit order book

This project implements the same sequential, single-venue BTC limit-order-book
contract twice:

- **Version A (`A-list`)** stores unsorted individual orders and scans them.
- **Version B (`B-indexed`)** uses an order-ID index, sorted price lists, and an
  insertion-ordered FIFO queue at each price.

The project uses the Python standard library only. It models synthetic submissions
to one venue. It is not a production trading system and does not model fees,
balances, hidden orders, self-trade checks, network delay, simultaneous execution,
or combined exchange liquidity.

## Clean run

Python 3.9 or newer is sufficient. From this directory:

```sh
python3 -m scripts.check_correctness
python3 -m scripts.replay data/worked_example.jsonl --version A --validate-each --output results/worked_A.json
python3 -m scripts.replay data/worked_example.jsonl --version B --validate-each --output results/worked_B.json
```

The worked market sell must fill `b1`, `b2`, `b3`, and `b4` for 1, 1, 3, and 1
BTC respectively. Four BTC remain on `b4`, the ask `a1` is unchanged, and gross
proceeds are USD 359,400.00.

## Interfaces

Both classes provide the same public operations:

- `process_event(event)` validates and dispatches one event.
- `AddLimitOrder(event)` matches a validated limit order and rests any residual.
- `CancelOrder(event)` removes an active target's remaining quantity.
- `FillMarketSell(event)` consumes bids from best price downward.
- `inspect_book()` returns canonical price-time ordered active orders.
- `validate_invariants()` checks uniqueness, positive quantity, and an uncrossed book.

Use `lob.make_book("A")` or `lob.make_book("B")` to construct a version. Rejected
events do not mutate the book or advance `last_accepted_seq`.

## Full benchmark

The default command covers all required combinations: five workloads; event counts
1,000, 10,000, and 100,000; seeds 42, 43, and 44; both versions; and five raw
repeats. A run that exceeds the declared per-replay limit is recorded as stopped.

```sh
python3 -m scripts.benchmark \
  --event-counts 1000 10000 100000 \
  --seeds 42 43 44 \
  --repeats 5 \
  --time-limit 3 \
  --output results/full_results.csv \
  --metadata results/full_environment.json
```

Input generation occurs before timing. The benchmark performs separate runs for:

- primary replay time and throughput;
- instrumented per-event latency and operation counts;
- `tracemalloc` peak allocation.

Latency percentiles use the nearest-rank convention. Input events are pre-generated
and excluded from traced memory. The live book and current event result are included;
full result history is not retained. Traced Python allocation is neither auxiliary
space alone nor total process/native memory.

Run the separate event-type and early/late latency experiment:

```sh
python3 -m scripts.benchmark_latency_detail \
  --events 10000 \
  --seed 42 \
  --scenarios mixed buildup \
  --versions A B \
  --output results/latency_detail.csv
```

This reports median, nearest-rank p95 and p99 by event type and for the first and
last 10% of each stream. The warm-up uses a separate book, and the measured replay
starts from a fresh empty book.

Run the fixed-book liquidation and price-concentration experiment separately:

```sh
python3 -m scripts.benchmark_liquidation \
  --initial-orders 2000 \
  --price-levels 4 1000 \
  --seeds 42 43 44 \
  --repeats 5 \
  --output results/liquidation_results.csv
```

Every 10%, 100%, and 200% sale receives a freshly constructed bid book. Construction
and sell matching are timed separately.

## Dashboard

Build the dashboard only from saved measurement files:

```sh
python3 -m scripts.build_dashboard \
  --results results/full_results.csv \
  --liquidations results/liquidation_results.csv \
  --latency-detail results/latency_detail.csv \
  --correctness results/correctness.json \
  --environment results/full_environment.json \
  --output dashboard.html
```

Opening `dashboard.html` or changing its filters never reruns an experiment.

## Synthetic data generation

The supplied generator uses no exchange records. Example commands:

```sh
python3 generate_orders.py --scenario buildup --events 100000 --levels 1000 --seed 42 --out data/buildup_100000.jsonl.gz
python3 generate_orders.py --scenario mixed --events 1000000 --levels 1000 --seed 43 --out data/mixed_1000000.jsonl.gz
```

Do not commit generated million-event files. Record their commands and checksums.

## Project contents

- `lob/`: common contract plus Versions A and B.
- `tests/`: independent expected outcomes and cross-version checks after every event.
- `scripts/`: replay, correctness, benchmark, liquidation, and dashboard commands.
- `results/`: raw CSV/JSON evidence.
- `REPORT.md`: specification, correctness, complexity, revision, and limitations.
- `AI_USAGE.md`: required disclosure of AI assistance.

Before submission, place this directory at
`Submissions/LastnameFirstname/Assignment1/` in the course repository and record the
submitted commit identifier in `SUBMISSION_COMMIT.txt`.
