# Assignment 1: Limit order book, report

Maurice Bonacker, Frankfurt School of Finance & Management, Algorithms in Finance.
Submission folder: `Submissions/BonackerMaurice/Assignment1/`. Timing benchmark measured at commit `4b9df5f`, latency and memory rerun at `ade26d1`; see the README for run commands and the submitted commit.

---

## 1. Specification and model

The project implements a sequential, single-venue limit order book for Bitcoin in
Python, in two versions that return identical results: a transparent baseline
(Version A) and a revised version (Version B, in two variants).

**Events.** Each event has a strictly increasing `seq`, a unique `event_id` and a
`type`: `LIMIT` (buy or sell with a limit price), `MARKET_SELL` and `CANCEL`. Events
are processed one at a time in file order. Nothing is reordered or batched; an
event whose `seq` is not larger than the last accepted one is rejected.

**Matching rules.**
- A limit buy crosses when its price is at least the best ask; a limit sell when
  its price is at most the best bid.
- The best opposite price executes first; at the same price, the earliest
  resting order executes first (price-time priority, FIFO).
- Each trade is `min(incoming remaining, resting remaining)` at the **resting
  order's price**. A partially filled maker keeps its queue position.
- A limit order's residual rests on the book. A market sell's residual is
  discarded and never rests (status `filled`, `partial` or `unfilled`).
- A cancel removes only the remaining quantity of a live order; an unknown,
  filled or already cancelled target returns `not_found`.
- Invalid events (unknown type or side, non-integer or non-positive price or
  quantity, duplicate live id, non-increasing `seq`, malformed input lines) are
  rejected with a reason and change neither the book nor the last accepted `seq`.

**Units.** All matching uses integers: `price_ticks` are cents per BTC
(6,000,000 = $60,000) and `qty_units` are 10⁻⁸ BTC (100,000,000 = 1 BTC). Proceeds
in dollars are Σ(price × quantity) / 10¹⁰; rounding happens only for display.

**Interface.** `AddLimitOrder`, `CancelOrder`, `FillMarketSell`, the dispatcher
`process_event(event)` and `inspect_book()` (bids by price descending then
arrival, asks by price ascending then arrival). `03_code/replay.py` replays any
`.jsonl` or `.jsonl.gz` file; the README documents the command and output format.

**Model boundaries.** All orders are eligible. There are no fees, account
balances, hidden orders, self-trade checks, network delays or simultaneous
execution. Order ids are assumed to be strings and globally unique in valid
streams; reuse of a historical id is not validated. The input data is synthetic
teaching data from the course generator, not historical exchange records, and
represents one venue. This is a teaching implementation, **not a production
trading system**.

---

## 2. Correctness reasoning

**Hand calculation.** Before any code existed, I calculated the expected results by hand in Excel (`01_my_notes/OrderBookTests.xlsx`): the worked example and five further cases (crossing on arrival followed by a market sell, a market sell larger than the book, a market sell into an empty book, cancellation after a partial fill including repeated and unknown cancels, and invalid inputs).
I made them to define the expected behaviour for edge cases such as invalid input and an empty book early on, so that the first build already had to handle them. Test3–Test5 were calculated by Claude and checked by me. These values became the expected results of the tests.


**Tests first.** The tests were written before the engine. Run against an empty `OrderBook` stub they failed (6 failed, 1 passed: the engine-free check of my Excel values against the supplied JSON); the output is saved in `05_results/tests_fail_first.txt`, and commit `1603c06` contains the tests but no engine code. The same was done for Version B (22 failed against stubs) and for the robustness tests (15 failed against the old file reader). No expected value was changed afterwards.


**Invariants.** After every accepted event the book must satisfy: no crossed book (best bid < best ask when both exist), no resting quantity ≤ 0, and no active order stored twice. Price-time priority holds because the best price is always matched first and, within a price, the earliest order is at the front of its queue; a partially filled maker keeps its place. Quantity is conserved: incoming quantity = filled quantity + residual (resting or discarded), a maker loses exactly its fills, a cancel removes exactly the residual, and proceeds = Σ price × quantity. These checks ran after every event of all five supplied files for every version.


**Differential test.** 300 seeded random streams (52,287 events in total, including crossing limits, market sells, cancels of live, gone and unknown ids, and invalid events) were replayed through A, B-sorted and B-heap. After every event the results and the full book were identical. To confirm the test can fail, two deliberate bugs were planted in throwaway copies (LIFO instead of FIFO, wrong cancelled quantity); they were caught in 295 and 297 of the 300 streams.


**Robustness.** 37 invalid events (wrong types, missing fields, lowercase side, unknown type, non-increasing seq, malformed input lines and others) are all rejected with a reason, leave the book and the last accepted seq unchanged, and give identical results in all three versions. The engines needed no change; only the file reader was fixed so that a broken line no longer stops the replay.

Agreement between A and B only shows that the versions behave the same; it does not prove that either is correct. That is why the expected values of the core tests come from independent hand calculations, not from the code.

---

## 3. Runtime

Notation: **B** active orders, **P** occupied price levels per side, **M** events,
**F** fills of one event, **L** price levels emptied by one event, **H** entries in
a heap.

**Version A** keeps all active orders of both sides in one Python list in arrival
order. Finding the best maker scans the whole list; checking that a new id is not
already live scans it again.

```
AddLimitOrder / FillMarketSell (Version A):
    validate event                      # includes O(B) duplicate-id scan
    while remaining > 0:
        i = index of best opposite order    # O(B) scan
        if none, or price does not cross: break
        trade min(remaining, maker qty) at maker price; record fill
        if maker exhausted: delete it from the list   # O(B)
    limit residual: append to list (O(1) amortized); market residual: discard
CancelOrder (Version A): scan list for id, delete it   # O(B)
```

**Version B** organises the same orders differently (shared core
`lob_b_common.py`):
- `orders`: dict `order_id → order` (duplicate check and cancel lookup);
- per side, a dict `price → level`, where each level holds a FIFO `deque` of its
  orders plus live count and live quantity;
- a price index giving the best price: a sorted list with the best price at the
  end (**B-sorted**) or a `heapq` (**B-heap**).

```
MATCH(taker, side, qty, limit):
    while remaining > 0:
        p = best opposite price from the index; stop if none or not crossing
        level = levels[opposite][p]
        while remaining > 0 and level has live orders:
            maker = front of level's deque; skip it if cancelled (dead)
            trade min(remaining, maker qty) at p; record fill
            if maker exhausted: pop it from the deque, delete from orders
        if level empty: remove level (B-sorted: pop() from the end of the list;
                        B-heap: lazy, the stale price is dropped later)
AddLimitOrder: MATCH; residual → orders dict + back of its price deque
               (new price level: insert into the index)
CancelOrder:   remove from orders dict; mark the deque entry dead (lazy);
               remove the level if it is now empty
FillMarketSell: MATCH with no price limit; residual discarded
```

**Costs.** "Expected" relies on Python's string hashing; "amortized" means
averaged over the stream (each cancel or emptied level pays for its own clean-up
once).

| Operation | Version A | B-sorted | B-heap |
|---|---|---|---|
| Duplicate-id check | O(B) worst | O(1) expected | O(1) expected |
| Best price | O(B) worst | O(1) worst | O(1), plus O(log H) per stale top, amortized |
| AddLimitOrder / FillMarketSell | O(B·(F+2)) worst | O(F + L) amortized; a new price level adds O(log P) search + O(P) list shift | O(F + (L+1)·log P) amortized; a new level adds O(log H) |
| CancelOrder, level stays | O(B) worst | O(1) expected, amortized (one cancel can trigger a linear deque compaction) | same as B-sorted |
| CancelOrder, level emptied | O(B) worst | O(log P + P) worst | O(1) expected + amortized O(1) heap-rebuild share |
| Space | O(B) | O(B + P) | O(B + P) |

Costs include validation, building the result dict and fill list, index
updates, dead queue entries and clean-up. Lazy deletion is bounded by
**compaction**: a deque is rebuilt when more than half its entries are dead, and
a heap is rebuilt (`heapify`, linear) when H > 2·(live levels) + 16. Hence at most
2B queue entries and H ≤ 2P + 16, so log H = O(log P).

Over a whole stream, Version A costs about Σ B·(F+2), which is quadratic in M
whenever the book grows with M. Both B variants are close to linear in M for the
generator's fixed price range (1,000 levels per side).

**Measurements** (engine replay of preloaded events; median over seeds 42–44 of
the 5-repeat medians; 1 warm-up; 120 s limit per replay; parsing reported
separately; commit `4b9df5f`):

| Scenario | M | A | B-sorted | B-heap |
|---|---|---|---|---|
| buildup | 10,000 | 4.82 s | 0.0140 s | 0.0144 s |
| sweep | 10,000 | 5.44 s | 0.0138 s | 0.0148 s |
| mixed | 10,000 | 0.705 s | 0.0141 s | 0.0143 s |
| cancel_churn | 10,000 | **0.0074 s** | 0.0100 s | 0.0108 s |
| mixed | 100,000 | stopped (>120 s) | 0.132 s | 0.143 s |
| cancel_churn | 100,000 | **0.069 s** | 0.104 s | 0.106 s |
| mixed | 1,000,000 | stopped | 1.376 s | 1.398 s |

- Version A grows ~100× per 10× M (buildup 48.9 ms → 4.82 s, log-log slope 2.0).
  All its 100k runs except cancel_churn (whose book never exceeds one order) and the 1M run were stopped at the declared limit; no value
  was estimated.
- Both B variants grow linearly (throughput 0.56–1.00 million events/s from 1k
  to 1M events).
- **Large liquidation** (fresh bid book from the first 8,000 sweep events,
  e.g. 4,062 bids on 981 levels for seed 42; 100% sale, median of 5 repeats):
  A 1.38 s; B-sorted 1.67 ms; B-heap 2.02 ms (about 800× faster). Build time is
  reported separately. B-sorted is reliably faster than B-heap only on such large
  sales (3 of 3 seeds), because removing an emptied best level is `pop()` (O(1))
  instead of a stale `heappop` (O(log H)). On full streams the 5-repeat ranges
  overlap in 36 of 45 cells (ratios 0.96–1.08): no reliable winner.
- **Queue concentration** (same order count on 4 vs 1,000 prices): Version A's
  time does not depend on P; price-time correctness held on all 18 checked streams.
- **Latency** (separate instrumented run at `ade26d1`, nearest-rank percentiles,
  seed 42): Version A's median event in buildup 10k rises from 42 µs (first 1,000
  events) to 1,024 µs (last 1,000); B stays at ~1.2–1.5 µs. B's p99 at buildup
  100k is 1.9 µs, its slowest single event 1.9–2.0 ms (most likely a dict resize,
  an inference). Each latency cell is a single replay, so differences of ~10–15%
  between runs are normal. Latency is algorithm processing time only, not
  queueing or network latency, and is never derived from 1/throughput.
- **Latency by event type** (mixed, M = 10,000, median / p99 in µs):

  | Event type | Count | A | B-sorted | B-heap |
  |---|---|---|---|---|
  | LIMIT resting | 5,089 | 60.5 / 190 | 1.4 / 3.0 | 1.4 / 4.0 |
  | LIMIT that traded | 986 | 94.1 / 458 | 1.9 / 4.6 | 2.1 / 5.6 |
  | MARKET_SELL | 1,487 | 69.4 / 370 | 1.4 / 7.2 | 1.5 / 8.1 |
  | CANCEL found | 617 | 10.9 / 62 | 1.1 / 4.4 | 1.0 / 4.7 |
  | CANCEL not_found | 1,821 | 27.7 / 62 | 0.5 / 0.9 | 0.5 / 0.9 |

  In A every type pays for list scans; orders that trade are the most expensive
  because the best-order scan is repeated after every fill (on sweep, A's market
  sells reach p99 4.9 ms). In B the types differ only by a few µs: trading events
  and market sells have the longest tails (more fills to build), while a cancel of
  an unknown id is a single dict lookup (0.5 µs). The generated files contain no
  rejected events, so that type is not shown.
- After the revision, parsing (gzip + JSON, 1.6 µs/event) costs more than the B
  engine (1.3–1.5 µs/event).

---

## 4. Memory

Memory was measured with `tracemalloc` in a separate child process per run (seed 42,
M = 10,000 and 100,000). Events were preloaded **before** tracing started, so the
input is excluded. Included: the book (orders, levels, queues, price index), the
result dict and fill list of the current event (each sample is taken while that
output is still referenced, then released; the end value is the book only) and
validation temporaries. No result history is kept.

Traced bytes per live order at the end of the replay, M = 10,000:

| Scenario | Orders / levels | A | B |
|---|---|---|---|
| crowded | 10,000 / 8 | 193 | **102** |
| buildup | 10,000 / 1,977 | 193 | 273 |
| sweep | 3,938 / 978 | 205 | 357–365 |
| mixed | 1,587 / 747 | 194 | 578–591 |

- A B order is a `__slots__` object, smaller than A's dict per order; but every
  occupied price level costs B a level object, a deque and an index key (about
  850 bytes). B therefore uses **less** memory than A with more than ~9 orders
  per level and **more** with fewer. Mixed is the worst case for B (few orders
  per level, plus 213 dead queue entries, bounded by compaction to ≤ 2× live).
- **Book growth during insertion:** B's traced memory grows linearly with the
  number of orders (buildup 100k: 13.9 MB at the end), with visible steps at
  about 22k, 44k and 87k orders where the `orders` dict enlarges its table.
- **After cancellation churn:** after 100,000 cancel_churn events, retained
  memory stays flat at about 2 KiB traced (peak 3.3–3.9 KiB) for both B variants
  and ~1 KiB for A; B-heap keeps 2–3 stale index keys at the end. No stale entries
  or history accumulate.
- Version A's memory runs at M = 100,000 were stopped at the time limit, except cancel_churn, which completed.

**Why traced allocation is not auxiliary space or process memory.** Traced bytes
are Python allocations seen by tracemalloc (object sizes including headers and
container over-allocation). Auxiliary space is the algorithm's extra space as a
count of entries (O(B) orders + O(P) levels + index entries, including stale
ones), independent of byte sizes. Process memory additionally holds the
interpreter, modules, the preloaded events, allocator caches and memory not
returned to the operating system (e.g. 30–148 MB peak working set here, recorded
for context only). Also, CPython dicts do not shrink when keys are deleted, so
memory after a large book is cancelled can still reflect the earlier peak.

---

## 5. Profiling and bottleneck

**Version A.** The main bottleneck of Version A is that it scans the whole order list on every event. Two functions walk the list from start to end: `_is_live` (`lob_a.py:184`), which checks that a new order id is not already active, and `_best_index` (`lob_a.py:191`), which finds the best opposite order before the first fill and again after every fill. One event therefore costs about B · (F + 2) list steps (B resting orders, F fills).

The cost grows quadratically, not linearly. In buildup the book grows with every event: the operation counts show 999 list elements visited per event at M = 1,000 and 9,999 at M = 10,000. Ten times more events, each scanning a ten times longer list, gives about 100 times the work. Measured: 48.9 ms to 4.82 s (99x), about 48 ns per list element. The latency run shows the same thing event by event: A's median event takes 42 µs at the start of buildup and 1,024 µs at the end. At M = 100,000 every Version A run except cancel_churn (whose book never holds more than one order) was stopped at the declared 120 s limit; no time was estimated. 
**Version B.** The previous bottleneck is removed: the duplicate check is a dict lookup, the best price comes directly from the price index, and the next maker is the front of the price level's FIFO queue. Its cost per event stays at about 1 to 1.5 µs at every book size. What remains is the fixed per-event Python work (validation, building the result), and the next bottleneck is reading the input file (1.6 µs per event).

---

## 6. Revision (Version A → Version B)

Profiling Version A on the 10,000-event buildup stream showed (under cProfile, which inflates absolute times) that roughly three quarters of the runtime (5.2 of 7.0 s) went to `_best_index` and roughly a quarter (1.7 s) to `_is_live`. Both scan the whole order list: `_best_index` runs before the first fill and again after every fill, and `_is_live` once per new submission, so each event costs O(B) and a growing book makes the replay roughly quadratic in M (section 5). Version B replaces the list with three structures. A dictionary from order ID to order makes the duplicate check and finding an order to cancel O(1) expected, the same hashing idea as the hash set in Lab 1. A FIFO deque per price level keeps time priority, so the oldest order is always at the front. A separate price index per side finds the best price without touching individual orders. I built the price index in two variants to compare their trade-offs. B-sorted keeps the price keys in a sorted list with the best price at the end on both sides, so reading it is O(1) and removing an exhausted best level is a `pop()`. Adding a new level, however, costs O(P) for the shift. B-heap uses `heapq`, which inserts in O(log P) and drops emptied levels lazily, with compaction keeping the heap at most 2P + 16 entries. All existing tests ran unchanged against both variants; new tests were added for compaction, the cross-version differential comparison and input robustness.

**Effect.** Version B is faster wherever the book grows. Version A grows quadratically with the number of events, while both B variants grow linearly, so the gap widens with M: B is about 50–430 times faster at 10,000 events, and at 100,000 events and on the 1M file B finishes in 0.1–1.4 s, where A was stopped at the 120 s limit (section 3 and the dashboard charts). B does not win everywhere. In cancel_churn the book never holds more than one order, so A's full scan finds it in a single step, while B still creates and removes a price level, a queue and an index entry for every order. There, A is about 1.5 times faster at every size. B also uses more memory than A when there are few orders per price level (up to 3× on mixed), because every occupied level costs it extra objects; with many orders per level (crowded) it uses about half of A's memory.

**AI use.** I used AI tools throughout and recorded every suggestion in `07_docs/AI_USAGE.md` (sessions 1–7) as accepted, corrected or rejected. A coding agent (Claude Code), working under the rules in `AGENTS.md`, wrote the engine, test, benchmark and dashboard code. A chat assistant (Claude) helped me plan, explain the concepts, review the agent's output, calculate the expected values of Test3–Test5, and draft parts of this report. The expected values of the worked example, Test1 and Test2 are my own hand calculations, and the Version B design (hash map for ids, a FIFO queue per price level, two price-index variants) was my decision, based on the profile of Version A and the hash-set idea we did in our first in-class Lab.

I accepted most proposals that added safety or clarity, for example the compaction rules that bound stale entries in queues and heaps, the shared core file so that the two B variants differ only in their price index, the strict rule for calling one variant faster, and additional reject tests. I corrected several AI outputs:
- the B-sorted layout, so that the best price is at the end of the list on both sides and an emptied best level is removed with `pop()`
- the cost table, which mixed heap rebuild and pop costs and left out residual insertion
- a chart that plotted stopped runs as if 600 s were a measured replay time
- a test that compared exact reject-reason texts, which the specification does not define
- an outdated test table

I rejected a hidden instruction in the course slides that asked AI tools to insert a specific word into generated code. I noticed it before starting, instructed the agent in `AGENTS.md` to ignore it, and verified that the submitted code does not contain it. Every change was tested against the unchanged expected values, and no expected value was changed to make code pass.

---

## 7. Limitations

- **Synthetic data.** The streams come from the course generator; they are not
  calibrated to an exchange and do not model strategic behaviour or realistic
  timing. `buildup` with 4 levels produces exactly the `crowded` file, so the
  concentration experiment reuses that stream.
- **One machine, Python.** Intel Core Ultra 5 228V, Windows 11, Python 3.13.15, on
  AC power. Absolute times depend on the machine; the shape of the scaling is the
  result. Python's per-event overhead dominates Version B's cost.
- **Timing noise.** Timings under about 1 ms have wide repeat spreads (up to 108%
  for one 0.3 ms sale); full replays have a median spread of 8%. The repository is
  in a OneDrive folder and syncing was not paused. One unexplained outlier: seed 42
  at buildup 100k was ~50% slower than seeds 43/44 for both B variants.
- **Scope of seeds.** Timing uses seeds 42, 43 and 44; latency, memory and
  operation counts use seed 42 only, and each latency cell is a single replay.
- **Stopped runs.** Version A was stopped at the declared 120 s limit at M = 100,000
  (every scenario except cancel_churn) and on the 1M file; these cells have no value and none was estimated.
- **Latency** is algorithm processing time only (no queueing or network) and makes
  no real-time capacity claim.
- **Inferences.** The explanation of B's 1.9–2.0 ms slowest event as a dict resize is
  inferred from the memory curve, not measured directly.
- **Measured vs current code.** The timing benchmark ran at commit `4b9df5f`;
  latency and memory were rerun at `ade26d1` (per-event-type latency, memory
  sampled with the event's output retained). Commits in between only changed the
  file reader (`replay.py`), the test export, the benchmark scripts and added
  robustness tests. The engines are unchanged (same checksums), and the rerun's
  2,667 timing-relevant rows match the full run.
- **Not production.** No fees, balances, hidden orders, self-trade prevention,
  multiple venues, persistence or concurrency.
