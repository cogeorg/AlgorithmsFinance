# Assignment 1: Limit order book, baseline vs revision

A sequential, single-venue BTC limit order book in Python with price-time (FIFO) priority,
an own `FillMarketSell`, two implementation versions, tests written first, benchmarks of
time and memory, and a dashboard that reads the saved results.

* **Version A** (`lob/book_a.py`): transparent baseline. One list per side, every lookup is a linear scan.
* **Version B** (`lob/book_b.py`): revision. It uses price levels (`OrderedDict` FIFO queues), a sorted key list
  per side, and an `order_id` index. After profiling, it also got a fused fast-path dispatcher and orders stored as
  4-item lists. The intermediate revision steps are kept in `bench/variants/` and measured separately.
* The specification as handed out is kept unchanged in [`ASSIGNMENT.md`](ASSIGNMENT.md) and
  `AlgorithmsFinance_Exercise1.pdf`. `ASSIGNMENT.md` is the course's `README.md`, renamed. The course's
  `MANIFEST.json` is also left unchanged, so its `README.md` entry (SHA-256 `17ce011b…`) refers to what is now
  `ASSIGNMENT.md`. The report is [`REPORT.md`](REPORT.md) and AI usage is recorded in [`AI_LOG.md`](AI_LOG.md).

Modelling boundaries: one venue, one event at a time, all orders eligible. There are no fees, balances,
hidden orders, self-trade checks or network delays. All data is synthetic teaching data, not
calibrated to an exchange. This is not a production trading system.

## Requirements

* Python ≥ 3.11 (measured with CPython 3.13.15 on macOS 26 / Apple M4 Pro). **Standard library
  only**, so nothing needs `pip install`.
* A web browser for `dashboard/index.html`. The page is self-contained (inline SVG charts, no CDN) and works offline.

## Clean-environment run path

Nothing has to be installed beyond Python ≥ 3.11: no virtual environment and no `pip install`.

```sh
git clone https://github.com/cogeorg/AlgorithmsFinance.git
cd AlgorithmsFinance/Submissions/WelscherYannick/Assignment1
python3 --version                        # 3.11 or newer
python3 -m unittest discover -s tests -t .
python3 replay.py data/worked_example.jsonl --impl b
sh bench/run_all.sh                      # regenerates data/generated/ first, then all measurements
open dashboard/index.html
```

The generated inputs (`data/generated/`, ~70 MB) are not committed. Run `python3 bench/make_data.py`
before any single `bench/run_*.py` script; `run_all.sh` does this itself.

## Commands (run from this folder)

```sh
# 1. Tests (A and B run the same unchanged tests; ~5 s)
python3 -m unittest discover -s tests -t .

# 2. Replay any event file through either version
python3 replay.py data/worked_example.jsonl --impl a
python3 replay.py data/mixed_10000.jsonl.gz --impl b --quiet

# 3. Full pipeline: generate inputs, verify, benchmark, build dashboard (~35 min on an M4 Pro)
sh bench/run_all.sh

# 4. Open the dashboard (built from results/ only, never reruns experiments)
open dashboard/index.html        # or: python3 dashboard/build.py to rebuild it from results/
```

Step 3 runs these scripts in order. Each one can also be run on its own:

| Script | Output | What it does |
|---|---|---|
| `bench/make_data.py` | `data/generated/` (git-ignored), `results/generated_inputs.json` | Generates every input with the unchanged `generate_orders.py`, outside timing; records commands and SHA-256 |
| `bench/verify_correctness.py` | `results/correctness.json` | Oracle + A-vs-B comparison after every event; unit-test summary |
| `bench/run_timing.py` | `results/timing.csv`, `results/env.json` | Replay times, warmup + 5 repeats, fresh process per configuration (also one parse per configuration as a sanity value) |
| `bench/run_parse.py` | `results/parse.csv` | Reading + gzip + JSON parse per input, warmup + 5 repeats (version-independent) |
| `bench/run_revision_steps.py` | `results/revision_steps.csv` | Times Version B revision steps 1–3 on the same inputs and checks identical results |
| `bench/run_version_c.py` | `results/version_c.json` | Experiment: Version C (deque + lazy cancel) vs B, measured and not adopted |
| `bench/run_liquidation.py` | `results/liquidation.csv`, `results/liquidation_agreement.json` | 10 %, 100 % and 200 % market sells on fresh books; work counts |
| `bench/run_latency.py` | `results/latency.json`, `results/latency_raw_10000.json.gz` | Per-event latency percentiles in a separate run |
| `bench/run_memory.py` | `results/memory.csv` | `tracemalloc` peaks, book size after replay, growth checkpoints |
| `bench/run_counts.py` | `results/op_counts.csv` | Exact operation counts via instrumented subclasses (separate from timing) |
| `bench/run_profile.py` | `results/profile.json` | cProfile hot spots per version (separate run) |
| `bench/run_mutations.py` | `results/mutations.json` | Injects 20 deliberate bugs into a temporary copy; checks that the unchanged tests catch each |
| `bench/summarize.py` | `results/summary.md` | Key tables quoted in REPORT.md |
| `bench/run_gc_check.py` | `results/gc_check.json` | Diagnostic: Version B with the garbage collector on vs off |
| `bench/provenance.py` | `results/code_fingerprint.json`, `provenance/` | Code fingerprints, readable git history, git bundle |
| `dashboard/build.py` | `dashboard/index.html` | Embeds the saved results into a self-contained page (inline SVG, no external libraries) |

### Expected output of the worked example

`python3 replay.py data/worked_example.jsonl --impl a` (identical for `--impl b` except the `impl` field):

```
{"event_id": "event1", "order_id": "b1", "status": "resting", "unfilled_qty_units": 100000000, "fills": []}
{"event_id": "event2", "order_id": "b2", "status": "resting", "unfilled_qty_units": 100000000, "fills": []}
{"event_id": "event3", "order_id": "b3", "status": "resting", "unfilled_qty_units": 300000000, "fills": []}
{"event_id": "event4", "order_id": "b4", "status": "resting", "unfilled_qty_units": 500000000, "fills": []}
{"event_id": "event5", "order_id": "a1", "status": "resting", "unfilled_qty_units": 200000000, "fills": []}
{"event_id": "event6", "order_id": "s1", "status": "filled", "unfilled_qty_units": 0, "fills": [{"maker_id": "b1", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000}, {"maker_id": "b2", "taker_id": "s1", "price_ticks": 6000000, "qty_units": 100000000}, {"maker_id": "b3", "taker_id": "s1", "price_ticks": 5990000, "qty_units": 300000000}, {"maker_id": "b4", "taker_id": "s1", "price_ticks": 5970000, "qty_units": 100000000}]}
remaining_orders:
{"order_id": "b4", "side": "BUY", "price_ticks": 5970000, "qty_units": 400000000, "arrival_seq": 4}
{"order_id": "a1", "side": "SELL", "price_ticks": 6010000, "qty_units": 200000000, "arrival_seq": 5}
{"impl": "A", "statuses": {"resting": 5, "filled": 1}, "fills": 4, "gross_proceeds_tick_units": 3594000000000000, "gross_proceeds_usd": "359400.00", "remaining_orders": 2}
```

The tests should end with `Ran 124 tests ... OK`.

`python3 replay.py data/mixed_10000.jsonl.gz --impl a --quiet` (and `--impl b`, apart from the `impl` field) should print:

```
{"impl": "A", "statuses": {"resting": 5325, "cancelled": 617, "not_found": 1821, "partial": 844, "unfilled": 571, "filled": 822}, "fills": 3926, "gross_proceeds_tick_units": 928905461126000000, "gross_proceeds_usd": "92890546.11", "remaining_orders": 1587}
```

## Interface

Both versions inherit from `lob.common.OrderBookBase`, so validation, dispatch and result formats are
the same code. Events are the dicts read from the JSON Lines files.

```python
from lob.book_b import BookB          # or: from lob.book_a import BookA
book = BookB()
book.process(event)          # event dispatcher: validates, applies, returns a result dict
book.AddLimitOrder(event)    # LIMIT only (an event of another type is rejected)
book.FillMarketSell(event)   # MARKET_SELL only
book.CancelOrder(event)      # CANCEL only
book.inspect_book()          # active orders: bids (price desc, arrival asc), then asks (price asc, arrival asc)
```

| Result | Fields |
|---|---|
| LIMIT / MARKET_SELL | `event_id`, `order_id`, `status`, `unfilled_qty_units`, `fills`. `status` is `filled`/`resting` for a limit and `filled`/`partial`/`unfilled` for a market sell |
| CANCEL | `event_id`, `target_order_id`, `status` (`cancelled`/`not_found`), `cancelled_qty_units` |
| rejected | `event_id` (or `null`), `status: "rejected"`, `reason` |
| fill | `maker_id`, `taker_id`, `price_ticks`, `qty_units`, listed in execution order |
| book entry | `order_id`, `side`, `price_ticks`, `qty_units`, `arrival_seq` |

Only the current event's fills are returned. No trade history is stored.
`lob.common.gross_proceeds_tick_units(fills)` returns Σ price·qty exactly; `format_usd()` rounds it for display only.

### Interpretation decisions (where the specification leaves room)

* **Required fields:** a missing required field is rejected. `event_id`, `order_id` and `target_order_id` must be non-empty strings.
* **Integer fields:** `seq`, `price_ticks` and `qty_units` must have exact type `int`. JSON `true`/`false` and `100.0` are rejected.
* **Duplicate live ids:** a `MARKET_SELL` whose `order_id` equals a *live* resting order is rejected as a duplicate live identifier. A market sell never becomes live itself.
* **Reused ids:** reusing the id of an order that was already filled or cancelled is accepted. The specification puts historical reuse out of scope.
* **Duplicate `event_id`:** not checked. Detecting it would need storage that grows with every event.
* **Cancel targets:** a cancel of an unknown, filled or cancelled target is valid (`not_found`) and advances the last accepted `seq`. A cancel with a missing or non-string target is rejected.
* **Rejected events** change neither the book nor the last accepted `seq`.

## Layout

```
lob/common.py        shared validation, dispatcher, result formats, helpers
lob/book_a.py        Version A (list scan baseline)
lob/book_b.py        Version B (price levels + index)
replay.py            command-line replay
tests/test_spec.py   hand-calculated specification tests + independent oracle on random streams (A and B)
tests/oracle.py      independent checker: price-time priority, conservation, validation
tests/streams.py     own small random stream generator (few prices, invalid events)
tests/test_added_checks.py  extra oracle coverage and storage checks added after the revision
tests/test_version_c.py      Version C experiment: spec suite, C vs B per event, compaction stress test
tests/test_equivalence.py   A vs B after every event; B fast path vs generic path; B structure;
                            snapshot restore; stale storage
bench/               generation, verification and measurement scripts (see above)
bench/variants/      Version B revision steps 1 and 2 (history, measured) and Version C (experiment, not adopted)
results/             saved raw results + environment metadata
dashboard/           build.py and the generated index.html
```

## Measured-data definitions (`results/*.csv`)

All CSVs share the same columns. `run_kind` separates timing, liquidation and memory runs, so timing
and memory are never measured together.

| Column | Meaning |
|---|---|
| `version` | `A` or `B` |
| `scenario`, `seed`, `events`, `levels` | generator settings; `events` = M, total events including cancels and sells |
| `phase` | `parse` (read+gzip+JSON), `replay` (engine only), `reset` / `sell` (liquidation), `input` / `replay_peak` / `book_after` / `book_after_incl_input_objects` / `checkpoint` (memory, see below) |
| `repeat` | 0 = warmup (status `warmup`, not used for medians), 1–5 = timed repeats; for memory checkpoints: events processed |
| `elapsed_s` | seconds from `time.perf_counter` |
| `status` | `ok`, `warmup`, `stopped_time_limit`, `not_attempted` or `failed` (worker exited with an error). Stopped and failed runs are kept, not dropped |
| `active_orders_peak`, `price_levels_peak` | B and P peaks over the stream. Liquidation: resting orders on both sides and occupied **bid** levels (bid order count is in `note`). Memory `book_after` / `checkpoint`: stored entries at that moment, not peaks |
| `fills` | maker fills F over the stream / in the sell |
| `requested_qty_units`, `unfilled_qty_units` | liquidation sale size and unfilled remainder |
| `makers_touched`, `levels_visited`, `work_steps` | liquidation work counts (A: list entries scanned; B: fills + levels) |
| `traced_peak_bytes`, `traced_current_bytes` | `tracemalloc` peak / current traced bytes |

Memory boundary: `replay_peak` and `book_after` trace from *after* the input is loaded. Strings and ints
created while parsing (order ids, prices, seqs) and later held by the book are therefore not counted there.
`book_after_incl_input_objects` traces from *before* loading and drops the input list afterwards, so it
counts everything the book holds. "Bytes per order" uses this value.

Declared limits:
* **Timing and liquidation:** 120 s wall-clock per configuration (timing: parse + warmup + 5 repeats; liquidation:
  6 trials). A configuration that hits the limit is recorded as `stopped_time_limit`, and any finished repeats are kept.
  Once a Version A scenario is stopped, its other seeds and larger sizes are recorded as `not_attempted`.
* **Memory:** 480 s per configuration.
* **No limit:** latency, revision steps, operation counts, profile and parse. They only run configurations whose timing
  run finished, or Version B / version-independent work.
* **Near the limit:** Version A on `mixed` with 100,000 events needs about 110 s of the 120 s. Whether it finishes
  therefore depends on machine load; the dashboard flags such runs.

Provenance: `results/env.json` records the commit that ran the timing step (`git_commit`, 48076ba).
`git diff <that commit> -- lob` shows docstring-only changes, so the engine code that was measured is
unchanged.

Results of different steps come from different code states:
* **Produced with the scripts of that commit:** timing, revision steps and liquidation.
* **Changed later in those scripts:**
  * worker exit codes are now checked;
  * the liquidation agreement file records which versions ran;
  * the memory run skips stopped configurations.

  These changes only matter when a worker fails. Every timing and liquidation configuration was checked
  to be complete or explicitly stopped, so there was no silent failure.
* **Produced with the final scripts:** parse, latency, memory, counts, profile, GC check, mutations, the
  Version C experiment and the per-event verification.

## Code version and submitted commit

* **Submitted commit (course repository):** `d61cd1f644b02b8aca531d40deb5cd364a8d6390` (`d61cd1f`), branch
  `submission/welscher-yannick` of the author's fork. It contains all code, results and documents; the
  commit after it only records this id here.
* **Measured code:** the timing step records its commit in `results/env.json` (`git_commit`). That commit
  belongs to the author's working repository, whose full history is included as
  `provenance/history.bundle`, together with a readable `provenance/git_history.txt`:
  * the tests-first commit comes before any implementation;
  * every later change is listed with its date and files.

  Check the bundle with `git bundle verify provenance/history.bundle`. Inspect it with
  `git clone provenance/history.bundle /tmp/history`.
* **Same code as measured:** `results/code_fingerprint.json` lists the SHA-256 of every engine file, both in
  the measured commit and in this submission. The engine files `lob/*.py` are identical except for one
  docstring line in `lob/book_b.py`.

## Large data

Million-event files are not committed. `results/generated_inputs.json` lists the exact generator
command and SHA-256 for every generated input. `bench/make_data.py` regenerates them and confirms that the
10,000-event seed-42 files are byte-identical to the supplied samples.
