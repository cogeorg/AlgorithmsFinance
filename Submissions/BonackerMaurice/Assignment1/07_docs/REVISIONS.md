# REVISIONS.md: algorithm changes (Assignment 1)

Every change to the engine: what changed, why, and the evidence.
Version A (`03_code/lob_a.py`) stays unchanged and is kept for comparison.

Notation used for costs:

| Symbol | Meaning |
|---|---|
| B | active (live) orders in the book |
| P | occupied price levels on the side being touched (P ≤ B) |
| F | fills produced by the current event |
| L | price levels emptied by the current event (L ≤ F) |
| D | dead (cancelled) queue entries skipped by the current event |
| H | entries in one side's heap, live plus stale (B-heap only) |
| M | events in a stream (totals only; per-event costs do not depend on M) |

---

## Revision 1: Version A → Version B (two variants)

**Status: design approved by Maurice on 22 Nov 2026 with four decisions
(below). Implementation follows this design.**

Maurice's decisions on the first draft:

1. Compaction accepted: rebuild a side's heap when its entries exceed
   2 × live levels + 16; rebuild a level's deque when more than half its
   entries are cancelled. Tested under cancel_churn (heap) and by repeated
   cancels behind a live FIFO head (deque).
2. Shared core accepted: `lob_b_common.py` holds matching and
   cancellation; `validation.py` stays shared with Version A. The variants
   differ only in the price index.
3. Ask removal fixed: B-sorted stores BOTH sides so the best price is at
   the END of its list, and removes an exhausted best level with `pop()`.
4. Cost wording corrected: linear heap rebuilds are distinguished from
   O(log H) stale pops; submission costs include residual-limit insertion;
   compaction bounds retained entries, not Python dict allocations.

### Why: evidence from Version A

The cProfile run of Version A (`05_results/profile_version_a.txt`, one replay
per supplied 10,000-event file) shows two full-list scans doing almost all
the work:

| Scenario | total (s, cProfile) | `_best_index` (best-price scan) | `_is_live` (duplicate-id scan) |
|---|---|---|---|
| buildup | 7.04 | 74.4% | 24.1% |
| crowded | 5.33 | 71.7% | 26.7% |
| sweep | 6.83 | 77.2% | 21.3% |
| mixed | 0.78 | 58.3% | 27.1% |
| cancel_churn | 0.04 | 2.4% | 2.4% |

- Both scans are O(B) per call. `_best_index` runs F + 1 times per incoming
  order, `_is_live` once per submission. Version A therefore costs about
  B · (F + 2) per event.
- Cost depends on B, not on P: crowded (8 levels) and buildup (1,977 levels)
  take the same time (`05_results/replay_summary.csv`).
- Scaling (`05_results/scaling_version_a.csv`): log-log slope about 2 for
  buildup, crowded, sweep and mixed between 10k and 30k events, because their
  book grows with M. cancel_churn (B ≤ 1) is linear. Four of five 100k runs
  were stopped at the 600 s limit.

### What stays the same

- `validation.py` is shared unchanged; the duplicate-live check is passed in
  as `is_live = self.orders.__contains__`.
- Same interface and outputs: `AddLimitOrder`, `CancelOrder`,
  `FillMarketSell`, `process_event`, `inspect_book`, `assert_invariants`,
  attribute `last_seq`; identical result dicts and canonical book.
- All existing tests run unchanged against both variants.

### Data organisation (both variants)

```
orders      : dict  order_id -> Order          # live orders only
levels[side]: dict  price    -> Level          # occupied levels only
Order       : order_id, side, price_ticks, qty_units, arrival_seq
              qty_units == 0 means "dead" (cancelled, still sitting in a queue)
Level       : queue      deque of Order, arrival order (FIFO)
              live_count number of live orders in queue
              live_qty   sum of their qty_units (aggregate depth)
```

Price-time priority comes from the structure: the best level comes from the
price index (below), and inside a level the deque front is the earliest
arrival. A new order is appended at the back; a partially filled maker stays
at the front, so it keeps its priority. No seq comparisons are needed.

The two variants differ ONLY in the price index, the structure that answers
"what is the best occupied price on this side?". Each uses a signed key per
side so that one rule serves bids and asks.

| | B-sorted (`lob_b_sorted.py`) | B-heap (`lob_b_heap.py`) |
|---|---|---|
| Key | bids `p`, asks `-p` (best = LARGEST key) | bids `-p`, asks `p` (best = SMALLEST key) |
| Index per side | ascending list of keys; best at the END | `heapq` list; best at `heap[0]` |
| Best price | `keys[-1]`, O(1) | `heap[0]` after dropping stale tops |
| Level created | `bisect.insort(keys, key)` | `heappush(heap, key)` |
| Best level exhausted by matching | `keys.pop()` | nothing now (lazy) + compaction check |
| Any level emptied by a cancel | `del keys[bisect_left(keys, key)]` | nothing now (lazy) + compaction check |

### Pseudocode

Shared core in `lob_b_common.py` (identical for both variants; `INDEX_*` are
the variant parts):

```
MATCH(taker_id, taker_side, qty, limit):          # limit None = market order
    maker_side = opposite(taker_side)
    fills = []; remaining = qty
    while remaining > 0:
        p = INDEX_BEST(maker_side)
        if p is None: break                                     # side empty
        if limit is not None and not crosses(taker_side, limit, p): break
        level = levels[maker_side][p]
        while remaining > 0 and level.live_count > 0:
            maker = level.queue[0]
            if maker.qty == 0:                                  # dead entry
                level.queue.popleft(); continue
            t = min(remaining, maker.qty)
            fills.append(fill(maker.order_id, taker_id, p, t))  # resting price
            maker.qty -= t; level.live_qty -= t; remaining -= t
            if maker.qty == 0:                                  # maker exhausted
                level.queue.popleft(); del orders[maker.order_id]
                level.live_count -= 1
        TIDY(maker_side, p, level, best=True)
    return fills, remaining

TIDY(side, p, level, best):
    if level.live_count == 0:                       # level empty: remove it
        del levels[side][p]                         # drops its dead entries too
        if best: INDEX_REMOVE_BEST(side, p)         # matching empties the best level
        else:    INDEX_REMOVE(side, p)              # a cancel can empty any level
    elif len(level.queue) > 2 * level.live_count:   # more than half cancelled
        level.queue = deque(o for o in level.queue if o.qty > 0)   # compaction
```

```
AddLimitOrder(event_id, order_id, side, price, qty, seq):
    fills, remaining = MATCH(order_id, side, qty, limit=price)
    if remaining > 0:                               # residual-limit insertion
        order = Order(order_id, side, price, remaining, seq)
        orders[order_id] = order
        level = levels[side].get(price)
        if level is None:
            level = Level(); levels[side][price] = level
            INDEX_ADD(side, price)
        level.queue.append(order)
        level.live_count += 1; level.live_qty += remaining
    status = "resting" if remaining > 0 else "filled"
    return {event_id, order_id, status, unfilled_qty_units: remaining, fills}

CancelOrder(event_id, target_order_id):
    order = orders.pop(target_order_id, None)
    if order is None:
        return {event_id, target_order_id, "not_found", cancelled_qty_units: 0}
    level = levels[order.side][order.price]
    q = order.qty
    order.qty = 0                         # mark dead; stays in the deque (lazy)
    level.live_count -= 1; level.live_qty -= q
    TIDY(order.side, order.price, level, best=False)
    return {event_id, target_order_id, "cancelled", cancelled_qty_units: q}

FillMarketSell(event_id, order_id, qty):
    fills, remaining = MATCH(order_id, "SELL", qty, limit=None)   # never rests
    status = "filled" if remaining == 0 else ("partial" if fills else "unfilled")
    return {event_id, order_id, status, unfilled_qty_units: remaining, fills}
```

Price index, B-sorted (`skey(BUY, p) = p`, `skey(SELL, p) = -p`):

```
INDEX_BEST(side)            = price_of(keys[side][-1]) if keys[side] else None
INDEX_ADD(side, p)          : bisect.insort(keys[side], skey(side, p))
INDEX_REMOVE_BEST(side, p)  : keys[side].pop()                     # last element
INDEX_REMOVE(side, p)       : del keys[side][bisect_left(keys[side], skey(side, p))]
```

Price index, B-heap (`hkey(BUY, p) = -p`, `hkey(SELL, p) = p`; lazy
deletion plus compaction):

```
INDEX_BEST(side):
    heap = heaps[side]
    while heap and price_of(heap[0]) not in levels[side]:   # stale top
        heappop(heap)                                       # O(log H) each
    return price_of(heap[0]) if heap else None
INDEX_ADD(side, p):    heappush(heaps[side], hkey(side, p))
INDEX_REMOVE(side, p) = INDEX_REMOVE_BEST(side, p):         # nothing removed now
    if len(heaps[side]) > 2 * len(levels[side]) + 16:       # compaction
        heaps[side] = [hkey(side, q) for q in levels[side]]
        heapify(heaps[side])                                # O(P), linear
```

A level that empties and is later re-created gets pushed again, so a price
can appear twice in a heap. That is harmless: a copy counts as valid only
while the level exists, and compaction removes duplicates.

### Compaction: what it bounds and what it does not

Without compaction, lazy deletion could grow without bound while the live
book stays small:

- **Deque dead entries:** a long-lived live order at the front of a level
  with many cancels behind it would keep every cancelled entry. Rule: when
  more than half of a level's entries are cancelled
  (`len(queue) > 2 · live_count`), rebuild the queue from its live entries.
  After every event each level holds at most 2 × its live orders, so total
  queue entries ≤ 2B.
- **Heap stale prices:** in cancel_churn (one BUY, then its cancel) the bid
  heap is never asked for its best price (BUYs look at the ask side), so
  without compaction every emptied level's price would stay: H would grow
  with M (about 5,000 entries at 10k events) while B ≤ 1. Rule: when a level
  is removed and `H > 2 · (live levels on that side) + 16`, rebuild. Then
  H ≤ 2P + 16 after every event, so log H = O(log P).

What compaction does NOT guarantee: it bounds the retained queue and heap
entries, but not Python's own allocations. CPython dicts (`orders`,
`levels[side]`) do not shrink their hash tables when keys are deleted, and a
rebuilt deque or list may keep spare capacity. Memory measured after a large
book has been cancelled down can therefore still reflect the peak book, not
the current B. The memory experiment must report this, not assume it away.

### Costs per operation

Claim types:

- **Worst-case:** always holds.
- **Expected:** average over hash behaviour. This assumes Python's
  randomised string hashing spreads the ids; a pathological set of colliding
  keys can make one dict operation O(B).
- **Amortized:** averaged over the whole stream. A single event can cost
  more, but the extra work is charged to earlier cancels or level removals,
  each of which pays for it at most once.

Building blocks:

| Step | Version A | B-sorted | B-heap |
|---|---|---|---|
| Duplicate-live check (validation) | O(B) worst (list scan) | O(1) expected (dict) | O(1) expected (dict) |
| Best-price lookup | O(B) worst (full scan) | O(1) worst (`keys[-1]`) | O(1) when `heap[0]` is live. Each stale top popped costs O(log H) worst; a stale entry is popped at most once, so amortized O(log H) per level removal. |
| One fill | O(B) worst (rescan for the next maker) + O(B) list delete if the maker is exhausted | O(1) (`popleft` worst O(1); `orders` delete expected O(1)) | same as B-sorted |
| Dead entry skipped (each of D) | none (A has no dead entries) | O(1) each; each is created by one cancel and skipped at most once → amortized O(1) per cancel | same |
| Best level exhausted by matching | inside the O(B) scans | O(1) amortized (`pop()` at the end; amortized because the list may occasionally shrink its allocation) | O(1) now (dict delete, lazy) + compaction check. A triggered rebuild is O(P), linear (`heapify`). It needs more than P + 16 stale entries first, so amortized O(1) per removal. |
| Residual-limit insertion | O(1) amortized (`list.append`) | `orders` insert O(1) expected (amortized for table resizes) + `deque.append` O(1) worst. If the price level is new: O(log P) search + O(P) list shift worst (`insort`). | same, but a new level costs O(log H) worst (`heappush`) |
| Level emptied by a cancel | – | O(log P) search + O(P) shift worst (`del` at any index; O(1) shift if it is the best level) | O(1) expected (lazy) + linear rebuild when triggered, amortized O(1) |
| Deque compaction | – | O(len(queue)), linear, when triggered; triggered only when dead entries outnumber live ones, so amortized O(1) per cancel | same |

Operations (F fills over L emptied levels, D dead entries skipped; since
H ≤ 2P + 16, log H = O(log P)):

| Operation | Version A | B-sorted | B-heap |
|---|---|---|---|
| AddLimitOrder = validation + matching + residual-limit insertion + output | O(B · (F + 2)) worst | O(F + D + L) for matching, + insertion: O(1) expected if its level exists, O(log P + P) worst if the level is new. Amortized (D charged to cancels): O(F + L) + insertion. | O(F + D) + O(log P) per stale top popped + insertion: O(1) expected (existing level) or O(log P) (new level) + compaction share. Amortized: O(F + (L + 1) · log P). |
| CancelOrder, not_found | O(B) worst | O(1) expected | O(1) expected |
| CancelOrder, level stays | O(B) worst (scan + list delete) | O(1) expected + amortized O(1) deque compaction | same as B-sorted |
| CancelOrder, level emptied | O(B) worst | O(log P + P) worst | O(1) expected + amortized O(1) heap-rebuild share |
| FillMarketSell = validation + matching + output (never inserts) | O(B · (F + 2)) worst | O(F + D + L); amortized O(F + L) | O(F + D) + O(log P) per stale top popped; amortized O(F + (L + 1) · log P) |
| inspect_book (checks only, not the hot path) | O(B log B) | O(B + P) (walks the levels via the key list) | O(B + P log P) (sorts the level keys) |
| Space (retained entries) | O(B) | O(B + P): ≤ 2B queue entries, P keys | O(B + P): ≤ 2B queue entries, H ≤ 2P + 16 |

Totals over a stream of M events with F_tot fills:

- Version A: about Σ over events of B_t · (F_t + 2), which is quadratic in M
  whenever B grows with M.
- B-sorted: O(M + F_tot) expected/amortized, plus O(P) list shifting for
  each new level and each cancel that empties a non-best level.
- B-heap: O((M + F_tot) · log P) amortized.
- For a fixed price range (the generator's `levels` = 1,000 per side), both
  B variants should be close to linear in M.

### Hypotheses for the measurements (to be tested, not claimed)

1. buildup, crowded, sweep and mixed, which are quadratic in Version A,
   become close to linear in M for both B variants.
2. crowded (P = 8): levels are almost never created or removed, so the two
   variants should be nearly equal; the time goes into dict and deque work.
3. buildup (P up to 2,000): each price level is created once and then
   reused, so index work is rare. Expect B-sorted ≈ B-heap.
4. sweep: many best-bid levels are exhausted. B-sorted removes each with an
   O(1) `pop()`; B-heap does a lazy O(log P) `heappop` on the next lookup.
   Expect B-sorted slightly faster, possibly within noise.
5. cancel_churn: every event creates or removes a level of a 0–1-level book.
   Both should be cheap. B-heap does a little extra work (stale entries,
   periodic compaction). Retained entries must stay flat as M grows; check
   with the compaction tests and later with tracemalloc.
6. Memory per order is higher in B than in A (dict entry, deque slot and an
   Order object instead of one list slot). Measure it; do not assume.

### Implementation

- `03_code/lob_b_common.py`: Order, Level and the shared core
  (process_event, AddLimitOrder, CancelOrder, FillMarketSell, MATCH, TIDY,
  inspect_book, shared invariant checks).
- `03_code/lob_b_sorted.py`, `03_code/lob_b_heap.py`: `OrderBook`
  subclasses that implement only the price index (INDEX_BEST, INDEX_ADD,
  INDEX_REMOVE_BEST, INDEX_REMOVE, ordered prices for `inspect_book`, index
  invariants).
- `--version` choices become `a`, `b_sorted`, `b_heap` (module `lob_<version>`)
  in replay.py, scaling.py and liquidation.py.
- `assert_invariants()` for B also checks: every live order sits in its
  level's queue in arrival order, `live_count` and `live_qty` match the live
  entries, no empty level exists, dead entries are not in `orders`, queue
  length ≤ 2 · live_count, the index matches the occupied prices exactly
  (sorted) or covers them with H ≤ 2P + 16 and a valid heap order (heap),
  and the book is not crossed.

### Evidence after implementation (22 Nov 2026)

**Correctness**

- Tests first: with stub `OrderBook`s for both variants, the unchanged
  suite gave 22 failed (every B case), 12 passed (every A case):
  `05_results/tests_fail_first_version_b.txt`.
- After implementation: 40 of 40 pass (`05_results/tests_by_case.csv`).
  That is all 12 hand-calculated and JSON test cases for A, B-sorted and
  B-heap, plus the differential test and the three compaction tests.
- Differential test (`05_results/differential_tests.csv`): 300 seeded
  streams, 52,287 events. After every event, the result dicts,
  `inspect_book()` and `last_seq` were identical across the three versions,
  and invariants and conservation held: 0 mismatching events, 0 failures.
  Planted bugs in throwaway copies were caught: a LIFO queue in 295 of 300
  streams, a wrong cancelled quantity in 297 of 300.
- Compaction tests fail when compaction is switched off (throwaway copies):
  the heap reached 17 entries with 0 levels at seq 34 of cancel_churn, and
  the deque bound broke.
- Replay of the five supplied 10k files with `--check`: invariants OK after
  every event for both variants. Fills, rejects, not_found cancels, peaks
  and final book sizes are identical to Version A
  (`05_results/replay_summary.csv`).

**Performance** (`05_results/scaling_version_*.csv`; single runs, engine
time only, seconds)

| scenario | A 30k | A 100k | B-sorted 30k | B-sorted 100k | B-heap 30k | B-heap 100k | B slope 10k→100k (sorted / heap) |
|---|---|---|---|---|---|---|---|
| buildup | 51.9 | stopped | 0.088 | 0.273 | 0.071 | 0.296 | 0.83 / 1.05 |
| crowded | 57.5 | stopped | 0.067 | 0.296 | 0.068 | 0.257 | 1.00 / 1.07 |
| mixed | 11.5 | stopped | 0.078 | 0.298 | 0.080 | 0.305 | 0.89 / 1.08 |
| sweep | 91.0 | stopped | 0.095 | 0.347 | 0.104 | 0.297 | 1.08 / 1.00 |
| cancel_churn | 0.023 | 0.184 | 0.059 | 0.220 | 0.072 | 0.212 | 0.86 / 1.08 |

Large liquidation (`05_results/liquidation_version_*.csv`, 4,062 bids on
981 levels):

| | 10% sale | 100% sale | 200% sale |
|---|---|---|---|
| A | 0.377 s | 2.390 s | 2.545 s |
| B-sorted | 0.0003 s | 0.0033 s | 0.0042 s |
| B-heap | 0.0005 s | 0.0043 s | 0.0044 s |

Book build (8,000 events) took about 5 s in A and 0.015–0.022 s in either
B variant.

**Hypotheses checked against these single runs**

1. Supported: all five scenarios are close to linear in M for both B
   variants (log-log slopes 0.83–1.08 between 10k and 100k). A's slope is
   about 2 on four of them.
2. and 3. Consistent: on crowded and buildup the two variants differ by
   15% and 8% at 100k, within the noise below.
4. Not supported, inconclusive: on sweep, B-sorted was faster at 30k (by
   9%) but B-heap was faster at 100k (by 14%).
5. The compaction tests pass and fail when compaction is off. Note:
   Version A is FASTER than both B variants on cancel_churn up to 30k
   (0.023 s vs 0.059 / 0.072 s). With B ≤ 1, A's scans are trivially short,
   while B creates an Order, a Level, a deque and an index entry for every
   submission and removes them on the cancel.
6. Not measured yet (tracemalloc run still to do).

**Noise.** For each variant there are two independent single runs of the
same code on the same 10k files: the 10k row in `replay_summary.csv` and
the 10k row in `scaling_version_*.csv`. They differ by 16–64% for B-sorted
and 8–36% for B-heap. The two variants differ from each other by 2–17% at
100k, which is inside that band. **The single runs cannot identify a winner
between B-sorted and B-heap on any scenario.** The final benchmark (warm-up,
5 repeats, medians, raw repeats kept) has to decide, and may still find
them equal.

### Final benchmark (22 Nov 2026, commit 4b9df5f)

This replaces the single runs above as the evidence for Revision 1.

The latency and memory numbers below come from the rerun of 24 Nov 2026
(commit `ade26d1`, see "Benchmark change" at the end). Everything else is
from this run.

**What was run**

- Command: `python 04_benchmarks/run_benchmark.py`, from `Assignment1/`.
- Measured commit: `4b9df5f`, clean. The source fingerprint was the same at
  the start and the end of the run.
- Tests: 40 of 40 passed before the run.
- Time: 20:30 to 21:45 UTC (74 minutes).
- Machine: Intel Core Ultra 5 228V, Python 3.13.15, Windows 11, on AC power.
- Output: everything is in `05_results/benchmark_*.csv` and the dashboard
  `06_dashboard/dashboard.html`.
- Rows:
  - 2,409 timing rows ok and 258 stopped. Every stopped row is Version A:
    either M = 100,000, the 1,000,000-event file, or a repeat or sale skipped
    after a stop.
  - 26 memory rows ok and 4 stopped (Version A at M = 100,000).
- Correctness:
  - Every timed replay, build and sale was checked against the dataset
    manifest: 2,190 of 2,190 measurements agree. (Corrected on 24 Nov 2026
    from 2,216, which wrongly included the 26 memory rows; the memory runs
    are not checked this way.)
  - The concentration check passed 18 of 18 streams.

**Limitations**

- Timing uses three seeds (42, 43, 44). Latency, memory and operation counts
  use seed 42 only.
- One machine.
- The repository sits in a OneDrive folder, and syncing was not paused.
- The data is synthetic (the course generator).
- Timings below about 1 ms have the widest repeat spreads, up to 108% for one
  0.3 ms sale. Full-stream replays have a median spread of 8% and a maximum of
  43%.
- One unexplained outlier: at buildup M = 100,000, seed 42 was about 50%
  slower than seeds 43 and 44 for both B variants (191 / 187 ms vs
  126–130 ms). It was the first 100k cell of the run.

**Main result** (engine replay of preloaded events, in seconds. Each value is
the median over seeds 42–44 of the 5-repeat medians; parsing is excluded.)

| scenario | M | A | B-sorted | B-heap | A / B-sorted |
|---|---|---|---|---|---|
| buildup | 10,000 | 4.82 | 0.0140 | 0.0144 | 344× |
| crowded | 10,000 | 4.95 | 0.0114 | 0.0120 | 434× |
| mixed | 10,000 | 0.705 | 0.0141 | 0.0143 | 50× |
| sweep | 10,000 | 5.44 | 0.0138 | 0.0148 | 394× |
| cancel_churn | 10,000 | 0.0074 | 0.0100 | 0.0108 | **0.73×** (A faster) |
| buildup | 100,000 | stopped | 0.126 | 0.130 | – |
| mixed | 100,000 | stopped | 0.132 | 0.143 | – |
| sweep | 100,000 | stopped | 0.144 | 0.146 | – |
| cancel_churn | 100,000 | 0.069 | 0.104 | 0.106 | **0.67×** (A faster) |
| mixed, 1M events (seed 43) | 1,000,000 | stopped | 1.376 | 1.398 | – |

#### (a) The measured bottleneck: Version A scans the whole order list

**The code.** Version A keeps every resting order in one Python list,
`self.orders`. Two functions walk that list from start to end:

- `_is_live` (`03_code/lob_a.py:184`) is called by validation
  (`lob_a.py:130`) to check that a new order id is not already active. A new
  id never matches, so the loop always runs to the end of the list.
- `_best_index` (`lob_a.py:191`) finds the best opposite order. `_match`
  (`lob_a.py:220`) calls it once before the first fill and again after every
  fill, because A has no structure that remembers the next-best order.

So one event costs about B · (F + 2) list steps, where B is the number of
resting orders and F the number of fills.

**The operation counts** (`05_results/opcounts.csv`, seed 42). These come
from a counting subclass; the engine is unchanged.

- buildup, M = 1,000: 999 list elements visited per event.
- buildup, M = 10,000: 9,999 list elements visited per event, half in each
  scan.
- sweep, M = 10,000: 10,795 per event on average, and 102,777 in a single
  event (an order that trades through many makers rescans the list after
  every fill).
- cancel_churn: 0.5 per event, because that book never holds more than one
  order.

**The complexity, measured.** Ten times more events means ten times more
events, each scanning a list ten times longer, so the work grows about
100 times.

- Measured on buildup: 48.9 ms at M = 1,000 and 4,822 ms at M = 10,000, which
  is 99 times. That is a log-log slope of 2.0. Mixed grows 111 times and
  sweep 101 times.
- Dividing time by elements visited gives about 48 ns per element (4.82 s
  over 10,000 × 9,999 elements): one Python loop step with a dict lookup and
  a comparison.
- At M = 100,000 the same rule means about 100 times the work at 10,000. All
  three seeds were stopped at 120 s, as was the 1M file. No value is
  recorded or estimated for them.

**The latency shows it event by event.** In buildup at M = 10,000, Version
A's median event takes:

- 42 µs in the first 1,000 events, when the book is small;
- 1,024 µs in the last 1,000 events, with about 9,000–10,000 resting orders,
  which is 24 times slower.

B takes 1.4–1.5 µs and then 1.2–1.4 µs, so it does not slow down as the book
grows.

**Why Version B removes the bottleneck.**

- The duplicate check is a dict lookup.
- The best price is the last element of a sorted list (B-sorted) or the top
  of a heap (B-heap).
- The next maker at a price is the front of that price's FIFO deque.

The operation counts stay flat as M grows: at most 1.3 best-price lookups
and 0.41 queue pops per event, at both M = 1,000 and M = 10,000.
Throughput stays between 0.56 and 1.00 million events per second from
M = 1,000 to the 1,000,000-event file (B-sorted 0.73 M/s there).

**The next cost after the revision is reading the file, not the engine.**

- Parsing (gzip plus JSON) costs 1.6 µs per event at M = 100,000.
- The B engine costs 1.3–1.5 µs per event at the same size.
- On the 1M file, parsing took 1.55–1.58 s and the replay 1.38–1.40 s.

So in an end-to-end run, reading the input is now about half the time.

#### (b) B-sorted vs B-heap: which one wins, judged by the spread

**The rule.** Take one cell (a workload, M and seed). Each variant has 5
timed repeats, which give a range from fastest to slowest. A variant counts
as faster only when its slowest repeat beats the other variant's fastest
repeat. If the ranges overlap, there is no reliable difference.

**Result.** There were 136 comparisons:

- the ranges overlap in 100;
- B-sorted is faster in 31;
- B-heap is faster in 5.

The dashboard table "B-sorted vs B-heap" lists every workload.

- **Full streams (45 cells: 5 scenarios × 3 sizes × 3 seeds): no reliable
  difference.**
  - The ranges overlap in 36 cells. B-sorted is faster in 8 and B-heap in 1.
  - Median ratios (heap / sorted) are 0.96–1.08.
  - Mixed is the only scenario that leans one way: B-sorted is faster in 4
    of 9 cells, and on the 1M file (1.366–1.378 s vs 1.395–1.401 s, which is
    1.6%).
  - Mixed empties the most price levels: 3,045 levels emptied by matching in
    10,000 events (opcounts).
- **Large sales over many price levels: B-sorted wins reliably.**
  - A 100% sale on the 10k sweep book (4,062 fills over 981 levels) takes
    1.68 ms on B-sorted and 2.02 ms on B-heap. B-sorted is faster in 3 of 3
    seeds (ratio 1.21).
  - A 10% sale at M = 1,000 is also faster in 3 of 3 seeds (ratio 1.23).
  - Concentration sales on the 1,000-level book: ratio 1.28 at M = 1,000
    and 1.15 at M = 10,000.
  - Concentration sales over only 4 levels: ratio 0.99–1.07, and every
    range overlaps.

**Why.**

- When matching empties the best level:
  - B-sorted removes it with `keys.pop()` (`lob_b_sorted.py:40`), which is
    O(1).
  - B-heap leaves the key in the heap. The next `_best_price` finds the key
    is stale and removes it with `heappop` (`lob_b_heap.py:40`). That costs
    O(log H), about 10 sift steps for 1,000 levels.
- The operation counts show exactly one stale heap pop per emptied level
  (sweep 10k: 981 and 981).
- The measured gap follows the number of emptied levels, not the number of
  fills:
  - (2.02 − 1.68) ms / 981 levels ≈ 0.35 µs per level;
  - concentration at 10k: (2.58 − 2.20) ms / about 995 levels ≈ 0.38 µs per
    level;
  - with 4 levels there is no gap.
- At M = 100,000 the sale has about 40,000 fills but still only 1,000 levels.
  The per-fill work then dominates, the ratio drops to 1.04–1.07 and the
  ranges mostly overlap.

**Where B-heap would win in theory, and why it does not show here.**

- B-heap adds a new level in O(log P) with `heappush`. B-sorted uses
  `insort`, which shifts up to P keys.
- In these files P ≤ 1,000 per side, so the shift moves at most 1,000
  references inside one C memmove. That is cheap.
- B-heap's 5 wins all come from pure insertion work: the buildup replay or a
  book build, at M = 1,000 or 10,000. There, most events create a new level
  (805 levels in 1,000 buildup events).
- Even there, its advantage is 4–5% at M = 1,000 and gone at 100,000.

**Verdict.**

- On full streams, no reliable winner.
- B-sorted is reliably faster when one event empties many price levels.
- B-sorted is never reliably slower except in 5 small insertion-only cells.
- It is also the simpler index.

#### (c) Where Version B does not win, and why

1. **cancel_churn: Version A is faster at every size.**
   - Times: 0.76 vs 1.06 ms at M = 1,000; 7.4 vs 10.0 ms at 10,000; 69 vs
     104 ms at 100,000 (A vs B-sorted). B-heap is similar to B-sorted.
   - Median latency is 0.8 µs vs 1.1 µs per event.
   - **Why:** this book never holds more than one order. The opcounts show A's
     cancel scan visits at most 1 element, and the duplicate and best-order
     scans visit none. So A's O(B) scans cost O(1).
   - B does a fixed amount of extra work instead. Each submission creates an
     Order, a Level with its deque, a dict entry and an index key (`insort`
     or `heappush`). Each cancel removes all of them again.
   - At M = 10,000 that is 5,000 levels created and 5,000 removed by cancels;
     B-heap also rebuilt its heap 294 times.
   - Better complexity gains nothing when B stays at 1; the constant factor
     decides. This also confirms that the single-run observation (A faster
     up to 30k) holds up to 100k.
2. **Memory, when orders are spread thinly over many price levels.** Bytes
   per live order at the end of the replay, M = 10,000 (tracemalloc, input
   excluded):
   - buildup: B 273 vs A 193;
   - sweep: B 357–365 vs A 205;
   - mixed: B 578–591 vs A 194;
   - crowded: B **102** vs A 193 (B is smaller here).

   **Why:**
   - A B order is a `__slots__` object, smaller than A's dict per order.
   - Each occupied price level costs B a Level object, a deque and an index
     key. crowded and buildup at 10k both hold 10,000 orders, but on 8 vs
     1,977 levels. B uses 1.6 MiB more for buildup, which is about 850 bytes
     per extra level.
   - So B uses less memory than A when there are more than about 9 orders per
     level, and more when there are fewer.
   - Mixed is the worst case: 1,587 live orders on 747 levels, plus 213
     cancelled entries still waiting in deques. Those are bounded by
     compaction to at most twice the live count.
   - A's memory runs at M = 100,000 were stopped. A's bytes per order were
     193–205 in every measured case.
3. **Single slow events.** At buildup M = 100,000, B's p99 is 1.9 µs but its
   slowest single event is 1.9 ms (B-heap) and 2.0 ms (B-sorted).
   - The memory curve jumps at about 22k, 44k and 87k orders. Those are the
     points where a Python dict enlarges its table (2/3 of 32,768, 65,536 and
     131,072 slots).
   - So the slowest event is most likely the `orders` dict resizing: O(1)
     amortized, but one event pays O(B). This is an inference from the
     memory curve, not a separate measurement.
   - It does not change the comparison: Version A's typical event in
     buildup at M = 10,000 already takes 0.48 ms (median of all events) to
     1.02 ms (median of the last 1,000).
4. **Small books gain less.** At M = 1,000, B is 4.8 times faster than A on
   mixed, against 50 times at M = 10,000. The gain grows with the book,
   because A's cost does.

**Hypotheses checked against the final benchmark**

1. **Confirmed.** Both B variants are linear in M. For example, B-sorted
   mixed takes 1.32 ms, 14.1 ms and 132 ms at M = 1,000, 10,000 and 100,000.
   Throughput is flat up to 1M events. A grows about 100 times per 10 times
   M.
2. **Confirmed.** crowded: B-heap / B-sorted ratios of 1.01–1.02; ranges
   overlap in 8 of 9 cells.
3. **Confirmed.** buildup: ratios of 0.96–1.01; ranges overlap in 8 of 9
   cells, and B-heap is faster in 1 cell at M = 1,000.
4. **Partly confirmed.**
   - On the full sweep stream, no reliable difference (overlap in 8 of 9):
     at M = 10,000 only about one event in ten empties a level.
   - The predicted effect (B-sorted faster because `pop()` is O(1)) does
     appear where many levels are emptied at once: the large sales,
     ratio 1.13–1.35 at M ≤ 10,000.
5. **Confirmed, and stronger than expected.**
   - Retained memory stays flat over 100,000 cancel_churn events (about
     2 KiB traced at every sample, peak 3.9 KiB; B-heap keeps 2–3 stale keys
     at the end).
   - Version A is faster at every size, not only up to 30k.
6. **Partly confirmed.** B uses more memory per order when orders are spread
   over many levels (1.4–3.0 times A at M = 10,000), but about half of A's
   memory on crowded, where many orders share each level.

---

## Revision 2: replay input robustness (`03_code/replay.py` only)

**Status:** requested by Maurice on 22 Nov 2026, after the final benchmark.

**Unchanged:**

- the engines (`lob_a.py`, `lob_b_common.py`, `lob_b_sorted.py`,
  `lob_b_heap.py`);
- `validation.py` and the matching logic;
- every expected test value.

**What changed**

- `load_events` now reads the file as bytes and parses it line by line.
  - A line that cannot be parsed becomes a placeholder, `MalformedLine(n)`.
    This covers invalid JSON, invalid UTF-8 and nesting too deep to parse.
  - The replay turns that placeholder into
    `{"event_id": null, "status": "rejected", "reason": "malformed JSON line <n>"}`
    and continues. `n` is the 1-based line number in the decompressed file.
    The book is not touched.
  - Empty lines are skipped, as before.
- `--print-book` prints the final book after the summary line, one JSON
  order per line.
- With `--check`, the first-error label no longer calls `.get` on events that
  are not dicts.

**Why.** Before this change, one bad line stopped the whole replay with an
exception, and no result was written. Worse, a single invalid UTF-8 byte
anywhere in the file failed the read before the first event was processed
(text-mode decoding works on blocks, not lines). A Phase 2 auditor would try
exactly this.

**Evidence**

- **Tests first.** `02_tests/test_robustness.py` was written before the
  change. Its output on the old code is saved in
  `05_results/tests_fail_first_robustness.txt`:
  - 15 failed. 12 were malformed-line cases (`UnicodeDecodeError` while
    reading). 3 were `--print-book` cases (unknown option).
  - 127 passed. These are the adversarial-event cases, so `validation.py`
    already handled all of them and no engine change was needed.
- **The adversarial events cover** (each in all three versions):
  - string, float and bool prices and quantities;
  - zero and negative values;
  - a lowercase or unknown side, an unknown or lowercase type;
  - missing fields, a missing or non-integer `seq`, a repeated or decreasing
    `seq`, a missing `event_id`;
  - non-object events (list, string, number, null);
  - a still-live duplicate id;
  - huge quantities (10^30) in a limit order and a market sell;
  - a cancel of a market-sell id;
  - reuse of an id after its order was filled or cancelled;
  - extra fields.
- **What they check:**
  - no exception;
  - status `rejected` and a reason that names the cause;
  - the book, `last_seq` and the event itself unchanged on a reject, and the
    next `seq` still free;
  - normal results for the valid edge cases;
  - identical results and books in A, B-sorted and B-heap on one combined
    adversarial stream, with invariants and `check_event` after every event.
- **The malformed-line test** builds a `.jsonl` file and a `.jsonl.gz` file
  containing empty lines, a cut-off line, plain text, invalid UTF-8, a line
  nested 100,000 levels deep and a valid non-object. It runs both the timed
  and the checked pass. The valid lines give exactly the results they give in
  a clean file.
- **After the change:** 142 of 142 new tests pass, and the full suite has 182
  passed (`python -m pytest`).

**Effect on the benchmark.**

- The committed results were measured at `4b9df5f` with the previous
  `load_events`. The benchmark's parse phase calls `load_events`, so a rerun
  would time the new reader. Parse times from a rerun are therefore not
  directly comparable with the committed ones.
- Engine timings are unaffected, because the generated files are
  checksum-verified and contain no malformed lines.
- The dashboard's provenance row now names the files that differ from the
  measured code, instead of a bare "NO".

## Benchmark change: latency per event type, memory with retained output (24 Nov 2026)

**Status:** requested by Maurice on 24 Nov 2026. This is a change to the
measurement scripts, not to an engine.

**Unchanged:** the engines (same checksums as at `4b9df5f`), `validation.py`,
the tests, all expected values, the datasets, and all 2,667 timing rows.

**What changed**

- `bench_latency.py` gives every timed event one type and writes
  `latency_by_type.csv`: count, median, p95, p99 and max per type, version and
  scenario (nearest rank). The types are `LIMIT resting`, `LIMIT traded` (at
  least one fill, also if a residual rests), `MARKET_SELL`, `CANCEL found`,
  `CANCEL not_found` and `rejected`.
- The type is recorded in the untimed warm-up replay of the same events, so
  the timed loop is the same as before. Checks: both replays end with the same
  book, and the counts agree with the dataset manifest.
- `bench_memory.py` keeps the result of the current event while a memory
  sample is read, and releases it before the next event. New column
  `traced_with_output_bytes`: the end value with the last result still
  referenced. `traced_current_bytes` is still the value after its release.
- `run_benchmark.py --latency-memory` runs only these two phases. A run of
  selected phases now writes its own record
  (`benchmark_run_latency_memory.json`) instead of overwriting the record of
  the full run, and it checks the event files against their sha256.

**Why.** The slides ask to separate event types and compare early with late
events, and to retain the returned output while reading the memory.

**The rerun**

- Command: `python 04_benchmarks/run_benchmark.py --latency-memory`.
- Commit `ade26d1`, clean; the source was the same at the start and the end.
- 24 Nov 2026, 11:42 to 11:55 UTC. Latency took 160 s, memory 571 s.
- The machine, power state (AC), Windows, Python and package versions are the
  same as in the full run. The first check found the laptop on battery, so
  Maurice plugged it in before the start.
- The same cells were stopped as before: Version A at M = 100,000 (latency:
  buildup; memory: every scenario except cancel_churn).
- Tests re-exported at `ade26d1`: 182 of 182 pass, code clean.

**What changed in the numbers**

| Measure | 22 Nov (`4b9df5f`) | 24 Nov (`ade26d1`) |
|---|---|---|
| A, buildup 10k, median of the first 1,000 events | 44.0 µs | 41.9 µs |
| A, buildup 10k, median of the last 1,000 events | 894.5 µs | 1,023.9 µs |
| A, buildup 10k, median / p99 of all events | 457 / 950 µs | 481 / 1,224 µs |
| B-sorted, buildup 10k, median first → last 1,000 | 1.4 → 1.1 µs | 1.5 → 1.4 µs |
| B-heap, buildup 10k, median first → last 1,000 | 1.5 → 1.2 µs | 1.4 → 1.2 µs |
| B, buildup 100k, p99 (both variants) | 1.8 µs | 1.9 µs |
| B-sorted / B-heap, buildup 100k, slowest event | 1.94 / 1.93 ms | 2.02 / 1.94 ms |
| Traced bytes at the end, all 26 cells | – | identical |
| Traced peak, all 26 cells | – | identical, except +28 bytes for B on sweep |
| Process peak memory (context only) | 31–150 MB | 30–148 MB |

- **Latency.** The engines and the timed loop are the same, so these
  differences are run-to-run variation. Each latency cell is one instrumented
  replay and is not repeated. A's late events came out 14% slower and B's medians
  moved by at most 0.3 µs; the conclusions do not change.
- **Memory.** 126 of 2,600 samples are larger, all in mixed and sweep (the
  streams that trade), by at most 1,232 bytes (0.23%). That is the retained
  output, and it is small because an event's fill list is small next to the
  book.
- The end value with the last output still referenced is equal to the value
  after its release in all 26 cells. The last event of these files has no
  fills, and CPython keeps the freed dict and list in its free lists, which
  tracemalloc still counts.

**What the event types show** (M = 10,000, median in µs)

| Scenario | Event type | Count | A | B-sorted | B-heap |
|---|---|---|---|---|---|
| mixed | LIMIT resting | 5,089 | 60.5 | 1.4 | 1.4 |
| mixed | LIMIT traded | 986 | 94.1 | 1.9 | 2.1 |
| mixed | MARKET_SELL | 1,487 | 69.4 | 1.4 | 1.5 |
| mixed | CANCEL found | 617 | 10.9 | 1.1 | 1.0 |
| mixed | CANCEL not_found | 1,821 | 27.7 | 0.5 | 0.5 |
| sweep | LIMIT resting | 8,000 | 389.9 | 1.2 | 1.2 |
| sweep | MARKET_SELL | 2,000 | 365.7 | 0.8 | 0.8 |
| cancel_churn | LIMIT resting | 5,000 | 0.9 | 1.2 | 1.3 |
| cancel_churn | CANCEL found | 5,000 | 0.6 | 0.8 | 0.8 |

- **In A, a trading event is the slowest type**, because the best order is
  searched again after every fill. In sweep, a MARKET_SELL has a median of
  366 µs but a p99 of 4.9 ms and a maximum of 7.4 ms.
- **In A, a cancel that finds nothing is slower than one that finds its
  target** (mixed: 27.7 vs 10.9 µs). A `not_found` cancel always walks the
  whole list, while a found one stops at its target.
- **In B it is the other way round** (0.5 vs about 1.0 µs). A `not_found`
  cancel is one failed dict lookup, while a found one also has to update its
  price level.
- **In B every type has a median between 0.5 and 2.1 µs**, whatever the size
  of the book. Trading events cost most, because they build fills.
- In cancel_churn, A is faster than B on both event types.
- No generated file contains a rejected event, so the `rejected` row has
  count 0 everywhere. Rejection is covered by the tests, not by the benchmark.
