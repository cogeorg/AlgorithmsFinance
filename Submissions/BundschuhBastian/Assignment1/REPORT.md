# Assignment 1: limit order book, Version A against Version B

Bastian Bundschuh. Algorithms in Finance, Frankfurt School. All numbers come from files in `results/`
(the dashboard shows the same files). Code version: commit `23b6e74` (see the end of `README.md`). Notation: **M** events, **B** active (resting) orders, **P** price
levels, **F** fills.

## 1. Specification and model limits

One venue, one instrument (BTC/USD), events one at a time in `seq` order, continuous matching at the
resting order's price, price-time (FIFO) priority. All numbers are integers (price in ticks of 0.01 USD,
quantity in 10^-8 BTC); `bool` and floats are rejected (`type(x) is int`). The decisions D1-D19 and 11
fixed reject reasons are in `SPEC.md`; both versions share one validation function.
Out of scope, by assignment: fees, balances, hidden orders, self-trade checks, network delay, market buys,
order changes. The data are synthetic, not exchange records. This is a teaching model, not a trading system.

**Invariants** (checked after every event by `tests/helpers.py::step()`): I1 the book is not crossed; I2
every resting quantity is positive; I3 every active order is stored exactly once; I4 incoming quantity =
fills + residual; I5 each maker loses exactly its fills; I6 a cancel removes exactly the remaining
quantity; I7 proceeds = sum of price x quantity of the fills.

## 2. The two versions

**Version A** (baseline): one Python list of `[id, price, qty, seq]` per side, in arrival order.

```
validate: scan both lists for the id                      O(B)
add:      best = scan opposite side (price, then seq)     O(B)   # even if nothing crosses
          while crossing: fill best, list.pop(i)          O(B) per fill
          append rest to own list                         O(1)
cancel:   scan both lists, list.pop                       O(B)
```

**Version B** (revision): per side `dict price -> [deque of [qty, seq, id], live, dead]`, a sorted price list
(bisect; asks stored negated, so the best price is always the last element), and one index
`order_id -> (side, price, record)`.

```
validate: id in index                                     O(1)
add:      if crosses best opposite price: take from the front of the best queue, pop emptied levels
          else append to the level's deque (new level: insort into the price list)
                                                          O(1) at a known price, O(P) for a new price
cancel:   index lookup, qty = 0 (lazy), live -= 1; drop the level if live == 0;
          compact the queue if more than half of it is dead   O(1) amortized
sell:     F fills, each O(1) + one pop per emptied level
```

| Operation | A | B |
|---|---|---|
| validate / id live? | O(B) | O(1) |
| best price | O(B) | O(1) |
| add order | O(B) | O(1), O(P) for a new price |
| cancel | O(B) | O(1) amortized |
| market sell, F fills | O(F·B) | O(F) + O(1) per emptied level |
| replay of M events | O(M·B) | O(M) + O(P) per new price level |

The amortized cancel cost: each compaction removes more than half of a queue, and each removed record was
created by one cancel, so a cancel pays for a constant number of record moves; one single cancel can cost
O(queue length). Revisions and the 10 optimization steps (kept 1, 2, 4, 9; rejected 3, 5-8, 10) are in
`REVISIONS.md`, each with before and after timings.

## 3. Correctness

454 tests pass. Hand-calculated cases for matching and validation; invariants after every event; A and B
compared after **every** event on small adversarial streams (4 profiles x 40 seeds) and on the generated
generated streams of 1,000, 5,000 and 10,000 events (`results/correctness.csv`: 36 streams, 195,000 events, no difference). Planted bugs (mutation
checks) make the matching, equivalence and structure tests fail. Limits: validation is shared by A and B, so
only the hand tests guard it; streams of 100,000 and 1,000,000 events are not compared event by event (A is too slow
for a comparison with a full book check after every event). At 100,000 events A and B were compared only through
the fill hashes of the liquidation trials, which are equal.

## 4. Results (replay seconds, median over seeds 42-44, 5 repeats after a warm-up, gc on)

Parsing is not included. A ran under the same 600 s limit as B. A run that reached it is `stopped`, and a
run skipped by the rule "A needs < 60 s at 100,000 events to run 1,000,000" is `not_run`; no value is
estimated for either.

| Scenario | M | A (s) | B (s) | A / B |
|---|---|---|---|---|
| buildup | 10,000 | 2.548 | 0.0073 | 350 |
| buildup | 100,000 | 270.9 | 0.0912 | 2,970 |
| crowded | 100,000 | 283.0 | 0.0866 | 3,266 |
| mixed | 100,000 | 32.9 | 0.0805 | 409 |
| sweep | 100,000 | 230.5 | 0.0919 | 2,510 |
| cancel_churn | 100,000 | 0.0767 | 0.0675 | 1.1 |
| B only, 1,000,000 events | | stopped / not run | buildup 1.43, crowded 1.38, mixed 0.93, sweep 1.53, cancel_churn 0.67 | |

The fitted slope on a log-log plot (sizes 1k, 10k, 100k) is about 2.0 for A and 1.0 for B on buildup,
crowded, mixed and sweep. A on mixed 1,000,000 was stopped at 600 s. On `cancel_churn` the book is almost
empty and A and B are within about 10%; the revision does not win everywhere by much. B is 12% slower there
than the OrderedDict version before step 9 (step 9 won on the other scenarios; see `REVISIONS.md`).

**Why A is slow** (`results/counters.csv`, 10,000 events, buildup): `scan_is_live` = 49,995,000 = n(n-1)/2
exactly, plus about 25 million comparisons from scanning the opposite side for the best price on every new
order. B does no order scans; its work is one list insert per new price (492,152 elements shifted).

**Large sales** (buildup book, only the sell timed): selling 100% of 100,000 bids takes A 207.6 s and B
0.044 s; 10% takes 38.7 s and 0.0059 s. Fills and hashes of the fill lists are equal.

**Queue concentration** (100,000 buildup orders on 4 to 4,000 prices): A 269-285 s at every level count; B 0.0865
s at 4 levels to 0.0996 s at 4,000.

**Latency** (separate instrumented run, per event, nearest rank, 100,000 events, ns): B buildup p50 708, p95 959,
p99 1,583; B mixed p50 750, p99 2,958. A mixed p50 257,375, p99 1,668,541. In buildup and crowded, B's first and
last 1,000 events have the same p50 (625-875 ns at 100,000 events); A's p50 on buildup rises from 24,167 ns (first 1,000)
to 430,959 ns (last 1,000) at 10,000 events, because its book grows.

**Flood**: in `buildup` and `crowded` the peak number of active orders B equals M; the peak price levels P are about
2,000 (buildup) and 8 (crowded) (`results/flood_peaks.csv`).

## 5. Run-1 incident

The first full timing run was discarded: B on buildup with 100,000 events took about 0.20 s for seeds 42 and 43
and about 0.09 s for seed 44, steady inside each run, with identical code and data. The machine was in a different
state (in use, maybe on battery); run 1 kept no power state, so the cause is not proven. Run 1 stays in
`results/time_raw_run1.csv` and no number comes from it. Run 2 (and every later run) logs start time and power
source, and a canary (B, mixed, 100,000 events) runs before and after every block: all 88 canaries were between
0.0764 and 0.0821 s, all on AC power. In run 1 A on buildup 100,000 stopped at 600 s; in run 2 it finished in 270 s.

## 6. gc and dict-resize latency

B's rare very long events (about 12 ms) are garbage-collector pauses: with gc off the maximum drops from 13.1 and
12.4 ms to 0.82 and 0.88 ms (two runs each, `results/latency_gc_test.csv`). The remaining gc-off peaks (events
10,922, 21,845, 43,690, 87,381) are order-index dict resizes at 2/3 of capacity; `sys.getsizeof` jumps at exactly
those insert counts. Each resize is one longer insert; the cost per insert is amortized O(1). The timing runs keep gc
enabled, so the gc pauses are part of the reported times.

## 7. Memory (tracemalloc; input events not counted)

At 10,000 events, bytes held after the replay, A against B: buildup 0.96 MB / 3.43 MB, crowded 0.96 / 1.74, mixed
0.16 / 1.05, sweep 0.39 / 1.85. B holds more: one deque and one list per price level, the order index, per-order
records. At 100,000 buildup B holds 21.1 MB (A not run).

**B's memory is O(peak B), not O(B).** The queues stay at most 2·B records, but the order-index dict never gives back
its table. After 100,000 inserts and 99,999 cancels one order is live; B holds 4.05 MB (3.84 MB is the index), A 5.5 KB.
The memory is reused if the book grows again. `cancel_churn` does not grow with M (A 988 bytes, B 1,284 bytes after
replay for M from 1,000 to 1,000,000). `REVISIONS.md` step 9 first claimed O(B); that claim was wrong and is corrected.

## 8. Fairness check

A's id check is a scan. `A_idset` (`bench/variants.py`, labeled, never used as Version A) adds a set of live ids and
changes nothing else (identical results after every event). At 10,000 events it removes about half of A's time
(buildup 2.33 -> 1.08 s, mixed 0.329 -> 0.161 s); it is still 100-200 times slower than B on buildup, crowded and
sweep (0.0074 s, 0.0064 s, 0.0082 s for B), because each new order still scans the opposite side for the best price.

## 9. Limitations

- One machine (MacBook Air, Apple M4, 16 GB), one Python (3.11.0, CPython), three seeds, 1,000,000 events only with
  seed 42. Timings depend on the machine state (see section 5).
- A ran on the 1,000,000-event files only for cancel_churn (finished) and mixed (stopped); no value exists for A on the
  other 1,000,000 files, and none is estimated.
- Synthetic streams generated by the course generator; real order flow may differ (for example more cancels).
- B pays for speed with memory (2-7 times A's at the sizes tested) and is not faster on an almost empty book.
- Step 9 (deque with lazy cancel) made `cancel_churn` about 11% slower than the OrderedDict version; if the evaluation
  data are cancel-heavy, reverting commit 38891d3 is the fallback.
- Validation is shared code; the A-vs-B comparison cannot see its bugs.
- Latency numbers are processing time per call, not queueing or network, and include 42 ns of timer overhead.

## 10. Use of AI

I used Claude (Opus 5.5 in phases 0 and 1, Sonnet 5.5 from phase 2) as tutor and coding assistant, and I stayed
responsible for every decision. **My decisions:** the specification choices D1-D19 in `SPEC.md`; the order of the
phases; the benchmark rules (600 s limit per replay, a first replay over 60 s as the only measurement, the rule for A on
the 1,000,000-event files, gc enabled); the extra optimization candidates (deque with lazy cancel, pool of levels); the
gc test and the fairness check; rejecting timing run 1 and asking for the canaries; and the correction of the memory
claim. **Claude's work:** the tests, both versions, the optimization experiments, the benchmark code, the dashboard and
the first draft of this report. Claude also found and fixed bugs in its own benchmark code, usually through the tests
(for example the counters restore bug and the empty-chunk error in the latency code). I reviewed every phase before the
next one started.

`AI_LOG.md` lists every suggestion as accepted, corrected or rejected, with the evidence. Four corrections matter for
reading this report: gc stays enabled in the timing runs (my decision); run 1 is not used (my decision); Claude's claim in
`REVISIONS.md` that B's memory is O(B) was wrong and is now O(peak B); and Claude's expectation that the id scan was
two thirds of A's cost was wrong, the measurement says about half. Claude read every number in this report from
`results/` (not from memory of earlier runs), and the dashboard shows the same files.
