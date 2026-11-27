# Assignment 1 — Limit order book: report

Bejoy Padamadan · Algorithms in Finance · 26 November 2026

The assignment is to build an order book in two versions: Version A, a transparent baseline, and Version B, an improved version with faster performance on large books. The test cases were written before the versions were implemented. Matching rules are specified for three event types: LIMIT, MARKET_SELL and CANCEL. Both versions pass the same tests; Version B was up to 276× faster when the book grows large, but slightly slower when the book stays tiny (cancel_churn), and it uses more memory.

## 1. Specification and modelling boundaries

A sequential, single-venue BTC limit order book in Python with two implementations (Version A, Version B) that accept the same event files and return identical results.

- Events: `LIMIT` (BUY/SELL), `MARKET_SELL` (SELL), `CANCEL`, replayed in `seq` order on an empty book.
- Units: integer prices in ticks (0.01 USD per BTC) and integer quantities in units of 0.00000001 BTC. All matching and conservation checks use integers; dollars only for display (divide Σ price × qty by 10,000,000,000).
- Price-time priority: best price first, then earliest arrival (`seq`) at that price (FIFO). Trades execute at the resting (maker) order's price.
- Market-sell residuals are discarded, never rested: unfilled market-sell quantity does not remain in the order book. Limit-order residuals rest at their limit price.
- **Out of scope (modelling boundaries):** fees, account balances, hidden orders, self-trade checks, network delay, simultaneous execution, several venues. Event data are synthetic teaching data, not exchange records. This is an academic project, not a production trading system.

**Interface (both versions):** `OrderBook().process_event(event) -> dict` dispatches to `AddLimitOrder(event)`, `FillMarketSell(event)` and `CancelOrder(event)`; `snapshot()` returns active orders (bids high→low then by arrival, then asks low→high then by arrival). Replay a file with `python3 replay.py <file> [--version A|B]`.

## 2. Correctness

### Invariants (hold after every valid event)

1. **No crossed book:** best bid < best ask. An incoming order matches before it rests, and only rests when no eligible opposite order is left.
2. **Positive quantities:** an order whose remaining quantity reaches 0 is removed immediately.
3. **Each active order stored once:** A keeps one list; B keeps each order in exactly one price queue plus one index entry, and the index keys equal the orders in the queues.
4. **FIFO within a price:** orders join the back of their price queue in `seq` order; a partial fill changes quantity in place and never moves the order, so it keeps its original priority.
5. **Rejected events change nothing:** validation runs before any state change and `last_seq` is not advanced.

### Conservation

For every submission, submitted quantity = Σ fill quantities + `unfilled_qty_units`. Each maker loses exactly its fill quantity, a cancel removes exactly the residual, and proceeds = Σ `price_ticks` × `qty_units`.

### Evidence

- 19 hand-calculated tests. 15 were written **before** implementation and first failed with `NotImplementedError`: empty book, one order (buy and sell), sell smaller / equal / larger than depth (partial maker fill keeps its remaining quantity and priority), multiple makers at one price, multiple price levels, a limit sell stopping at its limit, partial fill then cancel and repeat cancel, crossing and non-crossing limit sells, and the worked example. 4 more were added after implementation: invalid input, identifier order ≠ arrival order, a 50-order queue, and a crossing limit buy. Partial fills followed by further trades are also exercised many times by the randomised comparison below.
- The same tests pass unchanged on both versions (`ORDERBOOK_VERSION=B python3 -m pytest -q`).
- Randomised comparison: 20 seeds × 300 generated events; results **and** full books of A and B compared after **every** event.
- Benchmark correctness table: A and B identical on every event of all 30 files with 1,000 and 10,000 events (5 workloads × 3 seeds), and both reproduce the worked example (proceeds 359,400.00 USD; 4 BTC left on `b4`).

The tests were validated with manually calculated results to ensure correctness: two versions that agree could still share the same mistake, so agreement alone is not proof.

## 3. Implementations, pseudocode and cost

Symbols: **B** active orders, **P** occupied price levels, **M** events, **F** maker fills produced by one event, **k** length of one price queue.

### Version A — one list of orders

```
match(incoming, remaining, limit):
    while remaining > 0:
        best = scan all B orders for best eligible opposite order   # O(B)
        if none: stop
        qty = min(remaining, best.qty); record fill at best.price
        best.qty -= qty; remaining -= qty
        if best.qty == 0: remove best from list                      # O(B)
add_limit:   validate (duplicate check scans B) → match → append residual
market_sell: validate → match with no limit → discard residual
cancel:      scan list for id (O(B)) → remove
snapshot:    split + sort all orders (O(B log B))
```

### Version B — price levels with FIFO queues, sorted prices, order index

- `levels[side][price]` → `deque` of orders in arrival order
- `prices[side]` → sorted list of occupied prices (best bid = last, best ask = first)
- `index[order_id]` → order (active orders only)

```
match(incoming, remaining, limit):
    while remaining > 0:
        price = best opposite price (end/start of sorted list)       # O(1)
        if none or not acceptable for limit: stop
        maker = front of levels[price]                               # O(1)
        qty = min(remaining, maker.qty); record fill at price
        maker.qty -= qty; remaining -= qty
        if maker.qty == 0: popleft, delete index entry               # O(1)
            if queue empty: delete level, remove price from list     # O(P)
rest residual: new price → insort into sorted list (O(P)); append to deque (O(1)); index (O(1))
cancel:  index lookup (O(1) expected) → deque.remove (O(k)) → empty level removed (O(P))
```

### Cost per operation

| Operation | Version A | Version B |
| --- | --- | --- |
| Validation (incl. duplicate-id check) | O(B) scan | O(1) expected (dict) |
| Limit insert, no cross | O(B) (validation + matching scan) | O(1); O(P) if new price level |
| Market sell / crossing limit, F fills | O(F × B) (rescan per fill) + O(F) output | O(F) + O(P) per emptied level + O(F) output |
| Cancel | O(B) | O(1) expected + O(k) + O(P) if level emptied |
| Snapshot | O(B log B) | O(B) |
| Space | O(B) | O(B + P) |
| Replay of M events (growing book) | ≈ O(M × B), ~quadratic | ≈ O(M + ΣF + P × new levels) |

No delayed cleanup is used: empty levels are removed immediately, so the costs above are worst-case per operation (dictionary operations are expected O(1)). Fill lists are built per event and returned; no trade history is stored.

## 4. Runtime results

Setup: MacBook Air (Apple silicon, arm64), macOS 26.4, Python 3.14.7, standard library only. 5 workloads × M = 1,000 / 10,000 / 100,000 × seeds 42, 43, 44; files generated outside timing; JSON/gzip parsing timed separately; 1 warm-up + 5 repeats on a fresh book, every repeat saved; median over repeats, then over seeds. **Declared limit: 30 s per replay; slower runs are stopped and recorded.** Raw data: `results/timing.csv`.

| Workload | M | Version A (s) | Version B (s) | A / B |
| --- | --- | --- | --- | --- |
| buildup | 1,000 | 0.034 | 0.0013 | 27× |
| buildup | 10,000 | 3.37 | 0.012 | 276× |
| buildup | 100,000 | stopped > 30 s | 0.129 | — |
| crowded | 10,000 | 3.40 | 0.012 | 295× |
| mixed | 10,000 | 0.55 | 0.013 | 43× |
| sweep | 10,000 | 4.39 | 0.019 | 237× |
| cancel_churn | 10,000 | 0.0072 | 0.0109 | 0.7× (A faster) |
| cancel_churn | 100,000 | 0.072 | 0.093 | 0.8× (A faster) |

Version A was stopped at M = 100,000 on buildup, crowded, mixed and sweep for all three seeds. Version B's throughput stays at about 0.5–1.1 million events per second at every size. Parsing (JSON + gzip) takes about 0.19 s at M = 100,000, more than Version B's replay itself.

**Per-event latency** (separate instrumentation run, seed 42, nearest-rank percentiles; processing time only, excludes queueing and network): buildup, M = 10,000:

| | p50 first 10% | p50 last 10% | p99 all |
| --- | --- | --- | --- |
| Version A | 38 µs | 624 µs | 652 µs |
| Version B | 1.4 µs | 1.2 µs | 2.2 µs |

**Large liquidation** (book built from 10,000 buildup events, rebuilt for every repeat):

| Sell size | Fills | Levels visited | Unfilled units | A sell | B sell |
| --- | --- | --- | --- | --- | --- |
| 10% | 522 | 97 | 0 | 353 ms | 1.1 ms |
| 100% | 5,025 | 988 | 0 | 2,340 ms | 6.8 ms |
| 200% | 5,025 | 988 | 255,929,000,000 | 2,388 ms | 6.8 ms |

**Interpretation.** On buildup every order rests, so the active book grows with M. Version A scans the whole book on every event, so its work per event grows with B and its total time grows roughly with M × B: 10× more events gave about 100× more time (0.034 s → 3.37 s). Version B's work per event does not depend on book size, so 10× more events gave about 10× more time. Version A's cost therefore depends on the size of the **active book**, not on the number of events: mixed, whose book peaks at about 1,600 orders, shows a much smaller gap (43×) than buildup with 10,000 active orders.

**Queue concentration.** With the same number of resting orders, crowded (8 price levels, long queues) and buildup (about 2,000 levels) give almost the same times in both versions. Version A scans every order regardless of how they are spread over prices. Version B reads the best price and the front of its queue directly; extra levels only cost when a new price is inserted into the sorted list, which is cheap at P ≤ 2,000. Price-time correctness with long queues is covered by the 50-order queue test and the A-vs-B comparison on the crowded files.

**Liquidation.** A 200% sell does exactly the same matching work as a 100% sell: once all bids are used up the loop stops and the remaining quantity is reported as unfilled and discarded, so fills, levels and time are equal. Version A rescans the whole book for every one of the 5,025 fills, so its sell takes seconds; Version B takes each next maker from the front of a queue.

## 5. Memory

`tracemalloc` in a separate run, seed 42. Events are preloaded before tracing starts, so input is **excluded**; book structures and the per-event result dictionaries are included; no trade history is kept. Raw data: `results/memory.csv`.

| Workload, M = 10,000 | A peak | B peak |
| --- | --- | --- |
| buildup (≈2,000 levels) | 1.9 MB | 3.6 MB |
| crowded (8 levels) | 1.9 MB | 2.1 MB |
| mixed | 0.29 MB | 1.0 MB |
| cancel_churn (after 10,000 events) | 616 B peak / 336 B final | 1,256 B peak / 264 B final |

At M = 100,000, Version B peaks at 24.9 MB (buildup, 100,000 active orders); `cancel_churn` stays at a few hundred bytes after 100,000 events, so neither version accumulates stale entries or history.

Traced allocation is not total process memory: it excludes the Python interpreter, memory allocated before tracing started (the loaded events), and allocator overhead and memory not returned to the operating system.

**Interpretation.** Version B uses more memory than A because, besides the order dictionaries both versions keep, it stores one `deque` and one dictionary entry per occupied price level, a sorted price list, and an index entry per active order. With about 2,000 levels (buildup) this nearly doubles the traced memory; with only 8 levels (crowded) the difference is small. Version B trades memory for speed.

## 6. Profiling: the measured bottleneck

**Bottleneck: Version A's full-book scans.** Two loops in Version A scan the whole book on every event: `is_live` (the duplicate-id check in validation) and the "find best order" loop in `_match`. In buildup every order rests, so the book grows from 0 to 10,000 orders and the number of order checks is about 2 × (0 + 1 + … + 9,999) ≈ 100 million, which matches the measured 3.37 s (roughly 34 ns per check). The per-event latency shows the same cause directly: Version A's median rises from 38 µs in the first 10% of events to 624 µs in the last 10% as the book grows, while Version B keeps prices sorted on insertion and reads the best price and earliest order directly, staying around 1.2 µs. Version B removes both scans with the order index (O(1) duplicate check and cancel lookup) and the price levels (O(1) best order).

**Exception: cancel_churn.** In cancel_churn every order is cancelled right after it arrives, so the book never holds more than one order and Version A's scan is almost free. Version B still pays fixed bookkeeping on every event (creating and removing a price level, its deque, a sorted-list entry and an index entry), which makes it slightly slower (0.7–0.8× A's speed) when the book stays tiny.

## 7. Revision: what changed and why

| Step | Commit | Change | Why |
| --- | --- | --- | --- |
| Version A | `e2a5a74` | list of orders, scan to find the best order | simple, obviously correct baseline |
| Validation | `1ccf24c` | shared `validation.py` used by both versions | rule 6; guarantees identical rejections in A and B |
| Version B | `dfc4322` | price → deque levels, sorted price lists, order index | remove the O(B) scans found in A |
| Tests | later commits | arrival vs id priority, long queue, crossing buy | complete the specified test list |

All existing tests were run unchanged after each revision; none was weakened.

**Possible further improvement (not implemented):** removing an emptied price with `list.remove` costs O(P); for bids the best price is always the last element, so `pop()` would make that O(1).

### Use of AI

Claude (Anthropic) was used as a guided tutor throughout.

- **My own work:** all expected outcomes in the hand-written tests (calculated by hand before implementing), several test scenarios (e.g. a limit sell that stops at its own limit), the trade step of Version A's matching, the `AddLimitOrder`, `FillMarketSell` and `CancelOrder` status logic with guidance, the predictions and explanations of the benchmark results, and the introduction and specification sections.
- **Provided by the AI, then read, run and explained by me:** project structure and stub, the "find best order" loop in Version A, the validation module, Version B, the randomised comparison test, `replay.py`, `benchmark.py`, `dashboard.py`, the result tables, and the final wording of the interpretation paragraphs in sections 4–6 (based on my own explanations of the results, due to time constraints). All factual statements were checked against the saved results.
- **Corrected:** the AI pointed out my mistakes in expected values (units, `0` vs `[]`, exact status words, fills belonging only to the current event); I corrected an unclear instruction from the AI ("none" meant "leave the key out").
- **Rejected / not used:** VS Code's built-in code generation.

## 8. Limitations

- Pure Python, measured on one laptop; absolute times depend on the machine. Each configuration was repeated 5 times, but other programs running at the same time can add noise.
- Version A could not be measured at M = 100,000 within the 30 s limit (except cancel_churn); its results there are reported as stopped, not estimated.
- Synthetic, uncalibrated workloads; no strategic behaviour or realistic timing.
- Latency is algorithm processing time per event, not end-to-end exchange latency, and cannot show real-time overload capacity.
- Validation of historical identifier reuse is out of scope (only live duplicates are rejected).
- Some cancel variants (cancel before any fill, after a full fill) and partial fill followed by another trade are covered by the randomised comparison test but not by separate hand-calculated tests.
