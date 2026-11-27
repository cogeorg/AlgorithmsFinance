# Assignment 1: Bitcoin limit order book

Two sequential Python engines implement limit buys/sells, cancellations and a
custom, mutating `FillMarketSell`. A transparent list baseline is compared with
an indexed FIFO revision. Exact integer matching, tests written before engines,
raw measurements and an offline saved-results dashboard are included.

This is separate from the earlier search lab and peer audit in the parent folder.
Source assignment documents are preserved in `assignment/`, supplied teaching
data in `data/`, and AI instructions/contributions in `AI/` and `agent/`.

## Clean-environment run

Python 3.10+; **no third-party packages**. Use a modern browser with JavaScript
for the dashboard. Benchmarks require POSIX signal timers (macOS or Linux).
The actual measured interpreter/machine is recorded in `results/environment.json`.
From the repository root:

```sh
cd Submissions/HardiKhushi/Assignment1
python3 -B -m unittest discover -s tests -v
python3 -B replay.py data/worked_example.jsonl --version baseline
python3 -B replay.py data/worked_example.jsonl --version revised
python3 -B verify_results.py
python3 -B dashboard.py
```

Open `dashboard.html` directly in the browser. It needs no server or network and
does not run benchmarks. Rebuilding from the same saved inputs is deterministic.
`verify_results.py` checks source/data hashes, original test immutability, matrix
coverage, raw-repeat medians, memory invariants, every saved latency percentile
and the dashboard's embedded measurement data when the dashboard exists.

The worked example's final result is `filled` with zero residual. Makers b1/b2/b3/b4
fill 1/1/3/1 BTC, respectively; b4 retains 4 BTC and a1 retains 2 BTC.
Gross proceeds are **USD 359,400.00**. The full exact JSON contract is in
`data/worked_expected.json`; `replay.py` prints the final event plus remaining book.

## Interfaces and integer units

```python
from orderbook.revised import OrderBook  # or orderbook.baseline

book = OrderBook()
result = book.process(event)
orders = book.inspect()
```

`AddLimitOrder(event)`, `CancelOrder(event)` and `FillMarketSell(event)` take the
same complete event dictionaries as `process(event)`, require their corresponding
type, and return the same result contract. All accepted events must have increasing
positive integer `seq`. Wrong direct-method event types are rejected atomically.
`inspect()` returns defensive copies of active orders in canonical bid-then-ask
price/time order with `order_id`, `side`, `price_ticks`, `qty_units`, `arrival_seq`.
`storage()` is diagnostic; `OrderBook(instrument=True).metrics` enables counters.

One price tick is USD 0.01 per BTC and one quantity unit is 10^-8 BTC. Prices and
quantities must be positive integers; booleans are rejected. Matching uses no
floating point. Divide summed `price_ticks * qty_units` by 10^10 for dollars;
round only at display time. Execution uses the resting price, best price first,
then original arrival sequence. Partial makers keep priority. Market residuals
never rest. Unknown/repeated/fully-filled cancellation targets return `not_found`.
Invalid events leave both book and last accepted sequence unchanged.

Only current-event fills are returned. Neither engine retains trade history or
historical IDs. Input event IDs and historical submission IDs are assumed unique
in valid streams; duplicate **live** submission IDs are checked. JSON parsing uses
standard-library `json` and `gzip`; malformed JSON reports its line number.

## Reproduce measurements

The saved main matrix uses five scenarios, sizes 1,000/10,000/100,000 and seeds
42/43/44, both versions, a four-second deadline per individual trial, five repeats
after warmup, and separate memory/latency/counter runs. Liquidations use fresh
bid books at 4 and 1,000 available prices, for 10/100/200% of initial bid quantity.
The million-event feasibility trial streams cancellation churn at seed 42.

The benchmark refuses to overwrite an existing result table. Use a new output
directory so the submitted measurements and their provenance remain preserved:

```sh
python3 -B benchmark.py --out .preview/reproduction
```

A small protocol check, with the same five-repeat rule:

```sh
python3 -B benchmark.py --sizes 1000 --seeds 42 --scenarios mixed cancel_churn --skip-million --out .preview/small-run
```

Inspect an alternate run without replacing the dashboard:

```sh
python3 -B -c 'from pathlib import Path; from verify_results import verify; print(verify(Path(".preview/reproduction")))'
```

Generate individual larger inputs outside timing:

```sh
python3 generate_orders.py --scenario buildup --events 100000 --levels 1000 --seed 42 --out data/generated/buildup_100000.jsonl.gz
python3 generate_orders.py --scenario mixed --events 1000000 --levels 1000 --seed 43 --out data/generated/mixed_1000000.jsonl.gz
```

The latter command is a regeneration example, **not a claim that that million-event
mixed workload was measured**. `results/inputs.json` contains exact measured-input
commands and checksums. Large generated datasets remain ignored and are not part
of the submission. The supplied generator writes stable gzip headers; compressed
bytes may still vary across Python/zlib versions. The recorded hashes identify
this run's exact bytes.

## Saved-data definitions

| File | Meaning |
| --- | --- |
| `results/measurements.jsonl` | Every raw timing repeat/warmup, stopped trial, memory snapshot, counter/depth/correctness result and latency summary |
| `results/summary.json` | Per-case timing medians with actual successful-repeat counts; five-repeat comparisons use only complete groups |
| `results/latency_raw.csv.gz` | Individual processing times, separate from primary replay; configuration/sequence/type/seconds |
| `results/environment.json` | Python, OS, CPU architecture/count, limits, protocol, engine base commit and actual measured source hashes |
| `results/inputs.json` | Generated input settings, SHA-256 fingerprints and exact regeneration commands |
| `results/FINDINGS.md` | Conclusions generated from the saved raw results, including regressions and stops |
| `results/evidence/` | Actual red/baseline/revised/final test logs and second-verification evidence |

Measurement rows identify `version`, `scenario`, `seed`, `event_count`, `levels`,
`phase`, `repeat` and `status`; sale rows also identify `sale_percent` and
`requested_qty_units`. Phase-specific fields are deliberate: depth rows contain
active/price peaks and fill counts; memory rows contain traced bytes/checkpoints;
sale outcomes contain makers/prices touched, residual and proceeds. Join by
scenario/seed/event_count (and version where relevant); depth is measured using
the revised engine and represents the equivalent logical workload, not timing
instrumentation inside the baseline. `event_count` is submitted events, not B.
For sweep construction it names the parent stream; the actual prefix is 80%.

`repeat=0` is warmup. A stopped warmup has no successful-repeat median; partial
groups retain their actual count. `elapsed_seconds` on `memory_run`, diagnostics
or a stopped trial is wall time for that phase, not a replay performance sample.
No missing times are invented, and no stopped run is plotted as zero.
Replay excludes parsing; application includes streamed parsing. Reset time is
separate from the sale, and is never treated as free. Throughput uses replay M/time.
Latency percentiles use nearest rank, not reciprocal throughput. Allocation
tracing excludes preloaded inputs, includes current output and checkpoint overhead,
and is neither total process memory nor pure auxiliary space.

## Traceability and review

- `docs/TRACEABILITY.md`: PDF pages mapped to implementation and evidence.
- `docs/REPORT.md`: model, pseudocode, invariants, complexity, profiling and limits.
- `agent/PROGRESS.md`: authorized steps, actual checks, commits and outstanding review.
- `AI/INSTRUCTIONS.md`, `AI/DECISIONS.md`: user requests versus document content and AI contributions.

Tests were committed before engines, and original test hashes are verified.
All commits require explicit user approval. Git history records each approved
checkpoint; `git rev-parse HEAD` identifies the checked-out submission commit.
`results/environment.json` identifies the engine-source checkpoint plus exact
file hashes actually measured, including the then-uncommitted benchmark harness.
Later documentation commits do not change that measurement identity.

This single-venue sequential teaching model excludes fees, balances, hidden orders,
self-trade checks, network delay and concurrency. It uses synthetic submissions,
not historical exchange liquidity, and is not a production trading system.
Student review and understanding of the AI-assisted work remain necessary.
