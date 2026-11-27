# Report: limit order book, baseline and revision

Notation: **M** incoming events, **B** active resting orders (B<sub>s</sub> on one side), **P** occupied
price levels, **F** maker fills of one event, **L** price levels visited by one event.
All numbers below come from `results/` (machine, Python and commit in `results/env.json`);
the dashboard (`dashboard/index.html`) shows every raw repeat.

## 1. Specification and modelling boundaries

Sequential single-venue BTC book with price-time priority. Prices are integer cents per BTC and
quantities are integer 10⁻⁸ BTC, so all matching, conservation and proceeds arithmetic is exact
integer arithmetic. `format_usd` rounds only for display. Events are `LIMIT`, `MARKET_SELL` and `CANCEL`.
Execution is always at the resting (maker) price. A residual limit order rests with its own `seq` as its
arrival rank. A market-sell residual is reported as unfilled and discarded. There are no fees, balances,
hidden orders, self-trade checks, network delays or simultaneous events. The data is synthetic and not
calibrated. Interpretation decisions for underspecified validation cases are listed in README.md.

## 2. Correctness reasoning

**Invariants after every accepted event.** Each one is argued below and also checked by tests.

1. *Price-time order.* Version A keeps each side's list in arrival order: an order is appended
   exactly once, when it rests, and accepted `seq` values strictly increase. Removals keep the relative
   order, and a partial fill changes a quantity in place. The best order is the **first** order with
   the best price (strict `>` / `<` comparison during the scan), so it is the earliest arrival at the best
   price. Version B keeps a sorted key list (best price last), and inside a price level an
   `OrderedDict` whose insertion order is arrival order, for the same reasons. Partial fills mutate
   `qty` in place, so the order keeps its position.
2. *No crossed book.* An incoming order rests only after matching stopped, either because the best
   opposite price no longer crosses its limit or because the opposite side is empty. So it rests strictly
   inside the spread. Fills and cancels only remove liquidity and cannot create a cross.
3. *Positive resting quantities.* A maker is removed exactly when its quantity reaches 0, and a residual
   rests only if it is > 0.
4. *No order stored twice.* A: each order lives in exactly one list. B: `index` and the level queues are
   in one-to-one correspondence (`BookB.check_internal`, tested).
5. *Conservation.* Each fill subtracts the same `q = min(incoming, maker)` from both sides, so
   incoming = Σ fills + residual and every maker loses exactly its fills. A cancel returns and removes the
   current remaining quantity. Proceeds are Σ price·qty in exact integers.
6. *Validation.* Validation runs before any mutation, and `last_seq` is updated only after an accepted event.
   So a rejected event changes neither the book nor `last_seq`.

**Evidence.**

* `tests/test_spec.py` holds hand-calculated cases for every item in the assignment's list. These are:
  empty book, one order, smaller/equal/larger sales, several makers at one price, several prices,
  partial fill then another sale, cancel before/after partial and full fills, repeated and unknown
  cancels, crossing buys and sells, residual limits, identifier order ≠ arrival order, a 500-order queue,
  and 30+ invalid inputs with unchanged state. The worked example matches `worked_expected.json`
  exactly, including 359,400.00 USD.
* `tests/oracle.py` is an independent checker. From the book *before* each event it recomputes
  which makers must trade, in which order, how much, at which price and what the next book must be. It
  also re-derives validity. It runs after every event of:
  * the spec tests (for the long-queue build, rejection and typed-entry scenarios via
    `tests/test_added_checks.py`);
  * 60 random streams (1–5 prices, ~6 % invalid events);
  * all five supplied samples and fifteen 1,000-event generated streams.
* Identical canonical books also imply identical aggregate depth per price level. Comparing every order's
  id, price, quantity and arrival rank is strictly stronger than comparing depth.
* Version A and Version B return identical results and identical canonical books after every
  event (100 random streams plus the inputs above). As required, this is treated as supporting
  evidence only.
* Tests were written first. The failing run against stubs is saved in
  `results/tests_before_implementation.txt` and committed before any implementation (see `git log`).
  The same tests then ran unchanged on A and on B. `tests/test_spec.py` is still byte-identical to its
  tests-first version, and no expected value was ever changed (see `provenance/git_history.txt`). Tests
  added later only add checks:
  * B's internal structure;
  * snapshot restore;
  * fast path vs generic path;
  * the extra oracle coverage in `tests/test_added_checks.py`;
  * the Version C experiment in `tests/test_version_c.py`.

  The suite now has 124 tests: 85 cover Versions A and B, and 39 cover the Version C experiment.
* Mutation check: `bench/run_mutations.py` injects 20 deliberate bugs into a temporary copy of the code,
  one at a time, and runs the unchanged suite. 8 bugs target the engine and the shared code, 12 target
  Version B's fast path. **20 of 20 were detected** (`results/mutations.json`); the unmutated copy passes.

## 3. Implementations, pseudocode and complexity

Shared by both versions (`lob/common.py`):

```
process(event):
    reason ← validate(event)                       # field types, side, seq > last_seq, duplicate live id
    if reason: return rejected(reason)             # no state change
    dispatch on type → LIMIT / MARKET_SELL / CANCEL; last_seq ← event.seq; return result
```

Version A (`lob/book_a.py`), two Python lists in arrival order:

```
match(taker, side, qty, limit):                    # limit = None for a market sell
    book ← opposite list
    while qty > 0 and book not empty:
        i ← index of first order with best price   # linear scan, O(Bs)
        if limit given and book[i].price does not cross limit: break
        q ← min(qty, book[i].qty); emit fill(book[i], taker, book[i].price, q)
        qty -= q; book[i].qty -= q
        if book[i].qty = 0: delete book[i]         # list shift, O(Bs)
    return fills, qty
AddLimitOrder: fills, rest ← match(...); if rest > 0: append Order(rest, seq) to own list
CancelOrder:   scan both lists for id; delete it; return its qty, else not_found
```

Version B (`lob/book_b.py`): `index{id→order}`, `levels{price→OrderedDict}` per side, `keys` per side
(bids ascending, asks as negated prices ascending, so the best key is always `keys[-1]`). An order is a
4-item list `[qty, side, price, seq]`. Its `process()` validates well-formed events inline and falls
back to the shared validating code for anything else (section 8):

```
take(taker, qty, levels, keys, sign, min_key):     # min_key None for market sell
    while qty > 0 and keys not empty:
        key ← keys[-1]; if min_key given and key < min_key: break
        level ← levels[sign·key]
        while qty > 0 and level not empty:
            maker ← first item of level             # O(1)
            q ← min(qty, maker.qty); emit fill; qty -= q
            if maker exhausted: pop front of level; delete index[maker]   # O(1)
            else: maker.qty -= q                     # keeps its position
        if level empty: delete level; keys.pop()     # O(1): it is the last key
AddLimitOrder: take(...); if rest: index[id] ← order; append to level (create level: insort key)
CancelOrder:   order ← index.pop(id) or not_found; delete from its level  # O(1)
               if level empty: delete level, remove key by bisect          # O(log P + P) memmove

process(event):                                   # Version B's dispatcher (fast path)
    if event is a plain dict with seq:int > last_seq, event_id:str, type known, and all fields of
       that type present with exact types (int > 0, non-empty str, side BUY/SELL, id not live):
        apply LIMIT / MARKET_SELL / CANCEL inline as above; last_seq ← seq; return result
    else:
        return OrderBookBase.process(event)       # shared validating path: identical rejections
```

| Operation (incl. validation, output, index updates) | Version A | Version B |
|---|---|---|
| Validation incl. duplicate live id | O(B) scan | O(1) expected (hash lookup) |
| LIMIT that does not cross | O(B) (duplicate scan + best-opposite scan) + O(1) amortised append | O(1) at an existing level; new level O(log P) compare + O(P) memmove |
| LIMIT / MARKET_SELL with F fills | O((F+1)·B<sub>s</sub>) scans + O(F·B<sub>s</sub>) list deletions + O(F) output | O(F + L) + O(F) output |
| CANCEL | O(B) scan + O(B) list shift | O(1) expected; if the level empties O(log P + P) memmove (O(1) at the best level) |
| inspect_book | O(B log B) (sort) | O(B + P) |
| Space | O(B): one `Order` object (72 B) per order in a list slot | O(B + P): a 4-item list (88 B) + index-dict entry + `OrderedDict` node per order, plus one level per price |
| Inactive / stale entries | none (removed immediately) | none (removed immediately); no trade history |
| Replay of a growing book (B ≈ M) | O(M²) | ≈ O(M) (+ O(P) per new level, P ≤ 2,000 here) |

Hash-table bounds are expected and amortised (resizing). Nothing uses delayed cleanup, so no amortised
cleanup argument is needed. `bisect.insort` and `del keys[i]` are O(P) element moves done by a C
`memmove`, which is cheap for P ≤ 2,000.

## 4. Runtime

**Setup.** M ∈ {1,000; 10,000; 100,000} events × seeds 42, 43, 44 × all five scenarios, plus 1,000,000 events
for `mixed` and `buildup` (seed 42). Each configuration: 1 warmup and 5 timed replays on a fresh empty
book, median reported, fresh process, 120 s limit. Parsing is timed separately with the same protocol.
Machine: Apple M4 Pro, CPython 3.13.15. All raw repeats are in `results/timing.csv` and the dashboard.

*Replay (median seconds of 5 repeats, seed 42; throughput in events/s)* (from `results/summary.md`):

| scenario | M | peak B | peak P | fills F | A replay s | B replay s | A events/s | B events/s | B parse s | A/B |
|---|---|---|---|---|---|---|---|---|---|---|
| buildup | 1,000 | 1,000 | 805 | 0 | 0.01332 | 0.000501 | 75,064 | 1,996,008 | 0.001101 | 26.6 |
| buildup | 10,000 | 10,000 | 1,977 | 0 | 1.326 | 0.004878 | 7,542 | 2,050,021 | 0.009643 | 272 |
| buildup | 100,000 | 100,000 | 2,000 | 0 | stopped_time_limit | 0.0557 | – | 1,795,461 | 0.09826 | – |
| buildup | 1,000,000 | 1,000,000 | 2,000 | 0 | not_attempted | 1.426 | – | 701,260 | 0.997 | – |
| crowded | 1,000 | 1,000 | 8 | 0 | 0.0132 | 0.000393 | 75,769 | 2,544,529 | 0.000958 | 33.6 |
| crowded | 10,000 | 10,000 | 8 | 0 | 1.302 | 0.004174 | 7,680 | 2,395,783 | 0.009254 | 312 |
| crowded | 100,000 | 100,000 | 8 | 0 | stopped_time_limit | 0.05255 | – | 1,903,058 | 0.09723 | – |
| mixed | 1,000 | 140 | 126 | 374 | 0.002357 | 0.000516 | 424,268 | 1,937,984 | 0.00086 | 4.57 |
| mixed | 10,000 | 1,588 | 752 | 3,926 | 0.1858 | 0.005254 | 53,811 | 1,903,312 | 0.008656 | 35.4 |
| mixed | 100,000 | 15,118 | 894 | 38,988 | 18.12 | 0.05241 | 5,518 | 1,908,142 | 0.09024 | 346 |
| mixed | 1,000,000 | 150,832 | 907 | 390,558 | stopped_time_limit | 0.6512 | – | 1,535,624 | 0.9281 | – |
| sweep | 1,000 | 800 | 661 | 496 | 0.01152 | 0.000616 | 86,775 | 1,623,377 | 0.000882 | 18.7 |
| sweep | 10,000 | 8,000 | 1,959 | 5,035 | 1.189 | 0.00587 | 8,409 | 1,703,578 | 0.009004 | 203 |
| sweep | 100,000 | 80,000 | 2,000 | 50,035 | stopped_time_limit | 0.07259 | – | 1,377,657 | 0.09171 | – |
| cancel_churn | 1,000 | 1 | 1 | 0 | 0.000543 | 0.000388 | 1,841,621 | 2,577,320 | 0.000816 | 1.4 |
| cancel_churn | 10,000 | 1 | 1 | 0 | 0.005421 | 0.003803 | 1,844,678 | 2,629,503 | 0.008194 | 1.43 |
| cancel_churn | 100,000 | 1 | 1 | 0 | 0.05542 | 0.03809 | 1,804,338 | 2,625,154 | 0.08316 | 1.45 |

Seed spread (B replay median over seeds 42/43/44, M = 100,000): buildup 0.05534–0.0557 s, crowded 0.05149–0.05255 s, mixed 0.05241–0.05397 s, sweep 0.07001–0.07717 s, cancel_churn 0.03809–0.0386 s

Stopped / not attempted (version, scenario, M): A buildup 100,000; A buildup 1,000,000; A crowded 100,000; A mixed 1,000,000; A sweep 100,000

**Growing books (buildup, crowded, sweep).** Version A's replay grows about ×100 per ×10 events
(buildup: 0.0133 s → 1.33 s), as O(M²) predicts when the active book B grows with M. A therefore hit
the limit at 100,000 events, and those configurations are reported as stopped. Version B grows about ×10 from
10,000 to 100,000 events (4.9 ms → 55.7 ms). B is **272× faster** at buildup 10,000.

**One million events.** B needs 0.65 s for `mixed` and 1.43 s for `buildup`, while A was stopped or not
attempted. B's ×26 growth from 100,000 to 1,000,000 buildup events is not linear. A diagnostic
(`bench/run_gc_check.py`, `results/gc_check.json`) shows that Python's cyclic garbage collector explains
about 37 % of it: 1.33 s with GC vs 0.84 s with `gc.disable()`, 500 collections per replay. The rest
(×15 for ×10 events even without GC) is consistent with cache and allocation effects of a 1-million-order
book; this was not investigated further. All official measurements keep the default GC.

**Small books (mixed, cancel_churn).** In `mixed` the active book stays small (peak 15,118 orders at
100,000 events), yet A takes 18.1 s versus B's 0.052 s (×346). A's cost follows the active book, not the
event count. In `cancel_churn` the book never exceeds one order: both versions grow linearly, and B is
only about ×1.4 faster. More events do not imply a larger book.

**Seeds and noise.** B's medians at 100,000 events differ by at most about 5 % across seeds 42–44 (sweep
about 10 %). Some sweep repeats are bimodal (~76 ms vs ~95 ms in `results/revision_steps.csv`). The GC
diagnostic rules out the collector, which adds only ~2.5 ms there. Scheduling on the M4 Pro's efficiency
cores is a plausible but unverified cause. Medians of 5 cannot separate effects smaller than that.

**Parsing and total cost.** Reading + gzip + JSON takes about 0.09–0.10 s per 100,000 events
(`results/parse.csv`, median of 5). That is more than B's replay, so B's total application cost is
dominated by parsing, whereas A's is dominated by the engine.

**Latency per event** (separate run, `time.perf_counter_ns` around each `process()` call, resolution
41.7 ns, nearest-rank percentiles, timer overhead included):

*Per-event processing latency (ns, nearest-rank percentiles, seed 42)* (from `results/summary.md`):

| version | scenario | M | p50 | p95 | p99 | max | early p50 | late p50 | early p99 | late p99 |
|---|---|---|---|---|---|---|---|---|---|---|
| A | buildup | 10,000 | 119,458 | 225,416 | 239,041 | 591,084 | 12,333 | 224,791 | 28,125 | 254,500 |
| B | buildup | 10,000 | 458 | 667 | 1,084 | 50,583 | 542 | 459 | 833 | 792 |
| A | crowded | 10,000 | 127,834 | 236,666 | 251,792 | 324,125 | 12,583 | 235,959 | 27,917 | 272,000 |
| B | crowded | 10,000 | 417 | 542 | 667 | 67,292 | 417 | 458 | 1,500 | 583 |
| A | mixed | 10,000 | 15,625 | 52,792 | 79,250 | 212,667 | 2,291 | 30,833 | 7,708 | 119,125 |
| B | mixed | 10,000 | 542 | 1,291 | 2,250 | 110,417 | 542 | 500 | 2,208 | 2,083 |
| A | sweep | 10,000 | 99,334 | 275,458 | 541,916 | 1,264,209 | 12,750 | 49,167 | 30,667 | 60,500 |
| B | sweep | 10,000 | 459 | 1,792 | 2,750 | 62,625 | 541 | 291 | 917 | 417 |
| A | cancel_churn | 10,000 | 666 | 833 | 958 | 3,917 | 625 | 667 | 959 | 958 |
| B | cancel_churn | 10,000 | 458 | 625 | 750 | 8,208 | 542 | 417 | 1,041 | 667 |
| A | buildup | 100,000 | not attempted | | | | | | | |
| B | buildup | 100,000 | 583 | 1,250 | 5,208 | 1,940,042 | 459 | 667 | 958 | 5,709 |
| A | crowded | 100,000 | not attempted | | | | | | | |
| B | crowded | 100,000 | 500 | 792 | 1,000 | 3,832,292 | 459 | 500 | 833 | 1,375 |
| A | mixed | 100,000 | 136,500 | 486,083 | 765,666 | 13,372,625 | 15,209 | 286,917 | 73,417 | 1,137,459 |
| B | mixed | 100,000 | 500 | 1,250 | 2,083 | 126,583 | 583 | 500 | 2,167 | 2,125 |
| A | sweep | 100,000 | not attempted | | | | | | | |
| B | sweep | 100,000 | 542 | 2,667 | 4,167 | 1,540,500 | 542 | 292 | 959 | 1,125 |
| A | cancel_churn | 100,000 | 625 | 833 | 1,000 | 26,583 | 666 | 666 | 1,000 | 959 |
| B | cancel_churn | 100,000 | 458 | 584 | 708 | 16,459 | 459 | 417 | 750 | 708 |

* **A's latency grows with the book.** In buildup with 10,000 events its median rises from 12 µs in the first 10 % of events to
  225 µs in the last 10 %.
* **B stays flat.** Its median is 0.4–0.6 µs in every scenario and stays the same from early to late
  events. Its p99 is at most about 5 µs at 100,000 events (buildup: 1.0 µs early vs 5.7 µs late).
* **Rare outliers.** Single events reach a few milliseconds, consistent with GC pauses.
* **By event type** (B, mixed): cancel p50 0.29 µs, limit 0.54 µs, market sell 0.71 µs. The market-sell
  p99 is 3.3 µs because one sell can produce several fills.
* **Reciprocal throughput is not tail latency.** B's buildup throughput of ~1.8 M events/s would suggest
  0.56 µs per event, but the p99 is 5.2 µs.

**One large market sell** (fresh book restored from a snapshot before every trial; reset reported
separately):

*Large market sell (median seconds of 5 trials; reset reported separately)* (from `results/summary.md`):

| book | sale | requested units | fills F | levels L | unfilled | A sell s | B sell s | A reset s | B reset s | A work | B work |
|---|---|---|---|---|---|---|---|---|---|---|---|
| buildup_l1000 after 10,000 (5025 bid orders) | 10% | 25,592,900,000 | 522 | 97 | 0 | 0.04986 | 0.000157 | 0.002749 | 0.003454 | 2,487,069 | 619 |
| buildup_l1000 after 10,000 (5025 bid orders) | 100% | 255,929,000,000 | 5025 | 988 | 0 | 0.2503 | 0.001372 | 0.002771 | 0.003229 | 12,627,825 | 6,013 |
| buildup_l1000 after 10,000 (5025 bid orders) | 200% | 511,858,000,000 | 5025 | 988 | 255929000000 | 0.2497 | 0.001479 | 0.002746 | 0.003439 | 12,627,825 | 6,013 |
| buildup_l4 after 10,000 (4956 bid orders) | 10% | 24,647,800,000 | 486 | 1 | 0 | 0.04097 | 0.000119 | 0.001965 | 0.002554 | 2,290,761 | 487 |
| buildup_l4 after 10,000 (4956 bid orders) | 100% | 246,478,000,000 | 4956 | 4 | 0 | 0.2179 | 0.001115 | 0.001984 | 0.002312 | 12,283,446 | 4,960 |
| buildup_l4 after 10,000 (4956 bid orders) | 200% | 492,956,000,000 | 4956 | 4 | 246478000000 | 0.2198 | 0.001073 | 0.002066 | 0.002302 | 12,283,446 | 4,960 |
| buildup_l1000 after 100,000 (49988 bid orders) | 10% | 252,002,500,000 | 4990 | 102 | 0 | 5.041 | 0.003116 | 0.04193 | 0.06764 | 236,992,565 | 5,092 |
| buildup_l1000 after 100,000 (49988 bid orders) | 100% | 2,520,025,000,000 | 49988 | 1000 | 0 | stopped (3 of 5 finished) | 0.02228 | 0.04002 | 0.06594 | 1,249,425,066 | 50,988 |
| buildup_l1000 after 100,000 (49988 bid orders) | 200% | 5,040,050,000,000 | 49988 | 1000 | 2520025000000 | stopped (3 of 5 finished) | 0.02194 | 0.04162 | 0.06507 | 1,249,425,066 | 50,988 |
| buildup_l4 after 100,000 (49863 bid orders) | 10% | 251,196,700,000 | 4950 | 1 | 0 | 4.11 | 0.00183 | 0.02537 | 0.04348 | 234,573,075 | 4,951 |
| buildup_l4 after 100,000 (49863 bid orders) | 100% | 2,511,967,000,000 | 49863 | 4 | 0 | stopped (4 of 5 finished) | 0.01626 | 0.02573 | 0.04085 | 1,243,184,316 | 49,867 |
| buildup_l4 after 100,000 (49863 bid orders) | 200% | 5,023,934,000,000 | 49863 | 4 | 2511967000000 | stopped (4 of 5 finished) | 0.01717 | 0.02545 | 0.04207 | 1,243,184,316 | 49,867 |

* **Version B** sells the whole bid side of the 100,000-event book (49,988 bids on 1,000 levels) in
  **22 ms**: 49,988 fills, 1,000 levels visited, 50,988 steps.
* **Version A** needs 5.0 s for the 10 % sale. The 100 % and 200 % sales hit the limit after 3 of 5 trials
  (about 25–30 s per sale), and A scans about 1.25·10⁹ list entries for them. A 200 % sale does the same
  work as a 100 % sale and reports the rest as unfilled.
* **Total cost.** Restoring B's book (66 ms) costs more than B's sale itself, so B's total
  reset + sell is 88 ms. The snapshot is built once by replaying the buildup stream; that cost is the
  buildup replay time above.
* **Queue concentration.** Under the same order count, 4 instead of 1,000 prices per side make B's full
  sale cheaper (16 ms vs 22 ms, fewer level pops). A's cost barely changes because it scans orders, not
  levels. Replays behave the same way (crowded vs buildup: A 1.30 vs 1.33 s, B 4.2 vs 4.9 ms at 10,000
  events). Correctness at 4 prices is covered by the per-event checks of `crowded` and by identical A/B
  results in every liquidation trial where both ran.

## 5. Memory

`tracemalloc`, separate from timing, seeds 42–44; the tables show seed 42. What each value includes:

| Item | Replay peak | Book after (structures) | Book after (incl. parsed objects) |
|---|---|---|---|
| Preloaded event input | excluded (size shown separately) | excluded | only the ids/ints the book keeps from it |
| Book structures | included | included | included |
| Returned fills | the current event's result only | not included (dropped) | not included |
| Trade history | none is stored | none | none |

*Memory (tracemalloc, seed 42; input excluded from replay peak)* (from `results/summary.md`):

| version | scenario | M | input bytes | replay peak bytes | book after (structures) | book after (incl. parsed ids/ints) | stored orders | bytes/order (incl.) |
|---|---|---|---|---|---|---|---|---|
| A | buildup | 10,000 | 8,905,435 | 807,365 | 805,476 | 2,592,649 | 10,000 | 259 |
| B | buildup | 10,000 | 8,905,435 | 2,286,393 | 2,275,096 | 3,617,246 | 10,000 | 361 |
| A | crowded | 10,000 | 8,905,504 | 807,365 | 805,476 | 2,592,718 | 10,000 | 259 |
| B | crowded | 10,000 | 8,905,504 | 1,752,486 | 1,749,952 | 3,092,167 | 10,000 | 309 |
| A | mixed | 10,000 | 7,735,923 | 135,444 | 130,684 | 415,316 | 1,587 | 261 |
| B | mixed | 10,000 | 7,735,864 | 622,120 | 600,072 | 816,491 | 1,587 | 514 |
| A | sweep | 10,000 | 8,402,278 | 646,220 | 351,348 | 1,055,986 | 3,938 | 268 |
| B | sweep | 10,000 | 8,402,219 | 1,981,967 | 1,132,104 | 1,659,320 | 3,938 | 421 |
| A | cancel_churn | 10,000 | 7,265,350 | 3,710 | 1,828 | 1,078 | 0 | – |
| B | cancel_churn | 10,000 | 7,265,291 | 4,190 | 2,268 | 1,398 | 0 | – |
| A | buildup | 100,000 | not_attempted | | | | |
| B | buildup | 100,000 | 89,046,282 | 20,969,141 | 20,957,840 | 34,449,990 | 100,000 | 344 |
| A | crowded | 100,000 | not_attempted | | | | |
| B | crowded | 100,000 | 89,046,348 | 21,268,778 | 21,266,240 | 34,758,454 | 100,000 | 347 |
| A | mixed | 100,000 | 77,104,340 | 1,216,760 | 1,211,628 | 3,931,165 | 15,113 | 260 |
| B | mixed | 100,000 | 77,104,340 | 3,972,856 | 3,819,456 | 5,873,590 | 15,113 | 388 |
| A | sweep | 100,000 | not_attempted | | | | |
| B | sweep | 100,000 | 84,016,027 | 15,340,419 | 8,660,976 | 14,048,042 | 39,936 | 351 |
| A | cancel_churn | 100,000 | 72,646,160 | 3,711 | 1,828 | 1,078 | 0 | – |
| B | cancel_churn | 100,000 | 72,646,101 | 4,191 | 2,268 | 1,398 | 0 | – |

Latency seed spread (Version B, 100,000 events; p50 / p99 ns per seed): buildup s42 583/5208, s43 542/4375, s44 541/4333; crowded s42 500/1000, s43 500/1125, s44 500/1125; mixed s42 500/2083, s43 500/2083, s44 500/2083; sweep s42 542/4167, s43 542/4167, s44 542/4208; cancel_churn s42 458/708, s43 417/667, s44 417/708

Memory seed spread (Version B, 100,000 events, book incl. parsed objects, bytes): buildup s42 34,449,990, s43 34,434,823, s44 34,422,182; crowded s42 34,758,454, s43 34,758,454, s44 34,758,455; mixed s42 5,873,590, s43 5,955,088, s44 5,883,147; sweep s42 14,048,042, s43 14,111,970, s44 14,066,585; cancel_churn s42 1,398, s43 1,398, s44 1,398

* **Growth with the book.** Memory grows linearly with the resting orders, e.g. B buildup 34 MB at
  100,000 orders.
* **Bytes per resting order** (incl. parsed objects): about 260 B in A and 310–510 B in B (buildup 361 B).
  B pays for the order index and an `OrderedDict` node per order, plus per-level objects. This is where B is
  worse.
* **Cancellation churn.** Memory stays flat. After 10,000 and after 100,000 events A holds about 1.8 KB
  and B about 2.3 KB, with zero stored orders and levels. Nothing accumulates: no stale entries and no
  history. CPython dicts keep their capacity after deletions but reuse it, which the flat checkpoints
  confirm.
* **What tracemalloc does not show.** Traced bytes are neither pure auxiliary space (they include objects
  shared with the input) nor total process memory (interpreter, allocator slack and freed-but-cached
  arenas are missing).

Memory seed spread (Version B, 100,000 events, book incl. parsed objects, bytes): buildup s42 34,449,990, s43 34,434,823, s44 34,422,182; crowded s42 34,758,454, s43 34,758,454, s44 34,758,455; mixed s42 5,873,590, s43 5,955,088, s44 5,883,147; sweep s42 14,048,042, s43 14,111,970, s44 14,066,585; cancel_churn s42 1,398, s43 1,398, s44 1,398

## 6. Profiling and the measured bottleneck

cProfile (separate run, `results/profile.json`):
* **Version A.** In buildup with 10,000 events, A spends **57 %** of its own time in `_is_live` (the
  duplicate-id scan) and **39 %** in `_best_index` (the best-price scan). In mixed it is 39 % / 28 %, plus
  17 % in the cancel scan.
* **Version B.** It spends 82–92 % in its fused `process()` and about 20 % in `_take` on mixed flow.

Exact operation counts from instrumented subclasses (`bench/run_counts.py`, separate from timing):

*Operation counts per replay (seed 42)* (from `results/summary.md`):

| scenario | M | A list entries visited | A per event | B steps | B per event |
|---|---|---|---|---|---|
| buildup | 1,000 | 749,464 | 749.5 | 81,551 | 81.6 |
| crowded | 1,000 | 749,100 | 749.1 | 1,009 | 1.01 |
| mixed | 1,000 | 100,014 | 100 | 9,824 | 9.82 |
| sweep | 1,000 | 679,327 | 679.3 | 57,327 | 57.3 |
| cancel_churn | 1,000 | 500 | 0.5 | 1,000 | 1 |
| buildup | 10,000 | 74,994,375 | 7,499 | 502,152 | 50.2 |
| crowded | 10,000 | 74,993,064 | 7,499 | 10,009 | 1 |
| mixed | 10,000 | 10,204,537 | 1,020 | 240,114 | 24 |
| sweep | 10,000 | 68,079,381 | 6,808 | 500,641 | 50.1 |
| cancel_churn | 10,000 | 5,000 | 0.5 | 10,000 | 1 |
| buildup | 100,000 | not attempted | – | 605,052 | 6.05 |
| crowded | 100,000 | not attempted | – | 100,009 | 1 |
| mixed | 100,000 | 1,010,497,919 | 10,105 | 487,135 | 4.87 |
| sweep | 100,000 | not attempted | – | 655,087 | 6.55 |
| cancel_churn | 100,000 | 50,000 | 0.5 | 100,000 | 1 |

**Version A.** A visits on average 749 list entries per event in buildup with 1,000 events and 7,499 with
10,000 events. That is about B per event, ten times more per ×10 events, and therefore O(M²) in total.
In mixed with 100,000 events it still visits 10,105 entries per event, although the book is small,
because both scans run on every submission. This is the bottleneck in the code: `BookA._is_live` and
`BookA._best_index` loop over the lists on every LIMIT and MARKET_SELL, even when nothing crosses.

**Version B.** B replaces both scans with a dict lookup and `keys[-1]`. It does 1–7 steps per event at
100,000 events; the higher counts come from new price levels shifting the sorted key list.

**Revision steps of B:**

*Version B revision steps (100,000 events, seed 42, median ms of 5 replays)* (from `results/summary.md`):

| scenario | step 1 levels | step 2 + fast path | step 3 + list orders | step 3 vs 1 | identical |
|---|---|---|---|---|---|
| buildup | 99.6 | 67.5 | 59.6 | -40% | True |
| crowded | 96.1 | 60.4 | 55.2 | -43% | True |
| mixed | 84.6 | 57.8 | 53.6 | -37% | True |
| sweep | 111.6 | 81.1 | 93.3 | -16% | True |
| cancel_churn | 63.2 | 42.0 | 38.2 | -40% | True |


## 7. Revision: what changed, why, and its effect

The revision was done in three measured steps. Steps 1 and 2 are kept in `bench/variants/`, and the
submitted Version B is step 3. `bench/run_revision_steps.py` times all three on the same inputs and checks
that they return identical results.

**Step 1: data organisation (the main revision).** Version A stores orders in two arrival-ordered lists
and finds everything by scanning. Profiling and operation counts on Version A (section 6) show that
almost all of its time is spent in two linear scans, `_is_live` and `_best_index`. They run on every
submission, even when nothing crosses, which makes a growing-book replay O(M²) and a large sell O(F·B).
Step 1 keeps the same validation, dispatcher and result code and changes only the data organisation:
* an `order_id` dict for the duplicate-live check and for cancels;
* per-price `OrderedDict` FIFO queues;
* a sorted key list per side, arranged so that the best price is always the last element.

**Step 2: fused fast path and tighter matching loop.** Profiling step 1 showed about 60 % of its time in the *shared* generic
`validate`/`process` code: eight `dict.get` calls and five helper calls per event. The matching itself was
the smaller part. Version B therefore overrides `process()`. A well-formed event is checked against the same
rules inline and then matched, rested or cancelled directly. Any doubt sends the event to the shared,
fully validating code, so rejections and their reasons come from exactly the same code as in Version A. Such
doubts are a missing field, a wrong type, an unknown type or side, a nonincreasing `seq`, a duplicate live
id, or a `dict`/`str` subclass. Only field extraction sits inside `try`, so an internal error can never be
swallowed and processed twice. In the same step, the matching loop `_take` was tightened: it returns
as soon as the incoming quantity is exhausted, binds `fills.append` locally and no longer tests the quantity on
every iteration. The step-2 gain therefore comes from both changes. Most of it is the fast path, because
`_take` only runs for crossing events. Safeguards:
* a dedicated test compares the fast path with the generic path after every event, including invalid
  events and subclass edge cases;
* a mutation check injects 12 typical fast-path bugs, and all 12 are detected.

**Step 3: list orders.** An order object costs about 70 ns to create and a 4-item list about 16 ns, so B
stores orders as lists. This is roughly 9 % faster, at about +16 bytes per resting order.

**Not adopted.**
* A heap of prices with lazy deletion, and a `deque` with tombstone cancels (the latter was later built
  and measured as Version C, see below): both leave stale entries under
  cancellation churn unless an extra compaction rule is added. `OrderedDict` removes a cancelled order
  exactly in O(1).
* A batch `process_many()` API: it would speed up replay but change the measured interface, and both
  versions must be timed through the same per-event call.
* Popping every maker and re-inserting a partially filled one at the front: estimated (not measured) to save
  only ~20 ns per full fill while adding ~80 ns per partial fill, so not worth the extra code.

**Effect.** The effect is quantified in sections 4–6 and in the revision-steps table (section 6): about −40 % replay time, except on the noisy sweep. Steps 2 and 3 change
constant factors only, not the complexity in the table above.

### Version C: a further revision that was measured but not adopted

Version C (`bench/variants/book_c_deque.py`) keeps B's index, sorted key lists and fast path. It replaces
each level's `OrderedDict` with a `deque` of order objects and cancels lazily:
* **Cancel:** marks the order dead and decrements the level's live count. A level whose live count reaches 0
  is deleted at once.
* **Compaction:** runs when dead entries exceed live entries + 16, which is amortised O(1).
* **Order objects, not ids:** the deque must hold the orders themselves. Ids may be reused after an order is
  gone, so an id-based check could take a dead entry for a newer live order.

`tests/test_version_c.py` covers it: the full spec suite with the oracle, C vs B after every event, and a
cancel-heavy stress test with id reuse that triggers compaction. Measured with
`bench/run_version_c.py` (`results/version_c.json`) under the same protocol as the main runs:

| scenario (100,000 events) | B ms | C ms | C vs B | C/B per seed 42, 43, 44 |
|---|---|---|---|---|
| buildup | 55.4 | 46.0 | -17% | 0.78, 0.83, 0.84 |
| crowded | 53.6 | 44.6 | -17% | 0.86, 0.82, 0.81 |
| mixed | 51.8 | 49.5 | -4% | 0.96, 0.97, 0.95 |
| sweep | 66.5 | 61.9 | -7% | 0.92, 0.93, 0.94 |
| cancel_churn | 37.3 | 39.2 | +5% | 1.07, 1.05, 1.05 |

A 100 % sale on the 100,000-event book is -12% (1,000 prices) and
-13% (4 prices). Memory per resting order (incl. parsed ids/ints):

| book | B bytes/order | C bytes/order | C stale entries |
|---|---|---|---|
| buildup 10,000 | 362 | 415 | 0 |
| buildup 100,000 | 345 | 297 | 0 |
| mixed 100,000 | 389 | 425 | 5,814 |
| cancel_churn 100,000 | 2,089 B total | 2,089 B total | 0 |

**Why C was not adopted.**
* **Speed:** C is 4–17 % faster on four workloads but about 5 % slower under cancellation churn. There
  every order opens and closes its own level, and creating a deque costs more.
* **Memory is mixed.** C saves memory on long queues (buildup with 100,000 events) but uses more on short
  queues, because every deque allocates a fixed block. Under mixed flow it still holds 5,814 dead entries at the end of the replay.
* **Weaker guarantees.** C brings back stale entries and amortised bounds, which the assignment
  specifically asks to scrutinise.

The gain is a constant factor of at most ~1.2× (17 %), against ~300× for the data-structure revision. B stays
the submitted revision.

## 8. Limitations

* Timings are single-threaded CPython on one machine. Absolute numbers depend on hardware, Python version
  and background load; only the relative behaviour and the operation counts transfer.
* Version A runs that exceeded the declared 120 s limit are reported as stopped. Their missing values are
  not extrapolated.
* Per-event latency includes the overhead of two `perf_counter_ns` calls (tens of nanoseconds). It is engine
  processing time only: no parsing, no network and no queueing. A sequential replay cannot show at which
  arrival rate a live venue would overload.
* `tracemalloc` sees Python allocations only, not interpreter or allocator overhead and not freed-but-cached memory.
  When tracing starts after the input is loaded, strings and ints created during parsing are not counted even
  though the book keeps them (order ids, prices, seqs). The memory results therefore also report a variant
  traced from before loading (`book_after_incl_input_objects`), and bytes per order use that variant.
* Version A on `mixed` with 100,000 events needs about 110 s of the 120 s limit, so on a slower or busier machine it may be
  reported as stopped.
* The workloads are synthetic, uncalibrated and stylised (fixed reference price, uniform prices and sizes).
  They stress specific mechanisms rather than represent a real market.
* The model omits fees, balances, hidden orders, self-trade prevention, market buys, order amendments and
  multi-venue liquidity. It is a teaching implementation, not a production trading system.
* AI assistance was used. AI_LOG.md records the decisions, corrections and rejections.
