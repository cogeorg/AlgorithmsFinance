# Report: a limit order book in two versions

Tolgahan Yildirim · Algorithms in Finance, Assignment 1. All figures are from
the saved run described in [results/observations.md](results/observations.md)
(CPython 3.13.12, Windows 11, one laptop). Run commands and measurement
definitions are in [README.md](README.md).

## 1. Specification

One venue, one instrument (BTC), events processed strictly one at a time in
`seq` order. Prices are integer cents per BTC, quantities integer 1e-8 BTC, and
all matching and bookkeeping is integer arithmetic; dollars appear only when a
value is formatted for display.

- **Limit order.** A buy trades with asks priced at or below its limit, a sell
  with bids at or above its limit; best opposite price first, then earliest
  arrival; each trade is `min(incoming, resting)` at the **resting** order's
  price. A residual rests at its own limit with its own `seq` as arrival rank.
  Status `filled` if nothing rests, otherwise `resting`.
- **Market sell.** Trades with bids from the highest price down, same queue
  rule. The unfilled part is reported and discarded, never rested. Status
  `filled`, `partial` or `unfilled`.
- **Cancel.** Removes the target's remaining quantity if it is active; otherwise
  `not_found` with quantity zero. Unknown targets are valid events.
- **Rejection.** Unknown type or side, non-integer or non-positive price or
  quantity, missing or malformed identifiers, an identifier that is currently
  active, or a `seq` that does not exceed the last accepted one. A rejected event
  changes nothing, including the last accepted `seq`.

Boundaries of the model: every order is eligible; no fees, balances, hidden
orders, self-trade prevention, network delay or concurrency; continuous matching
at resting prices, not a batch auction; one venue's submissions, not combined
liquidity. Historical identifier reuse is not validated: only a currently active
identifier is a duplicate. The data are synthetic and not calibrated to any
exchange.

## 2. The two versions

All versions share `events.py` (validation, sequencing, result dictionaries) and
nothing else: each has its own storage and its own matching loop.

### Version A — baseline (`book_a.py`)

Two Python lists, one per side, holding a record
`[key, arrival_seq, remaining_qty, order_id]` per active order in arrival order,
where `key` is the price for asks and the negated price for bids. The smallest
record on a side is therefore its best price and, among equal prices, the
earliest arrival. A dictionary `order_id -> record` answers "is this identifier
active?" and locates a cancel target.

```
match(side, limit_key, taker, qty):
    while qty > 0 and side is not empty:
        best = min(side)                         # scan: O(B_side)
        if limit_key is given and best.key > limit_key: stop
        traded = min(qty, best.qty); best.qty -= traded; qty -= traded
        append fill(best.id, taker, |best.key|, traded)
        if best.qty == 0: side.remove(best); delete index[best.id]   # scan + shift: O(B_side)
    return qty

AddLimitOrder(buy at p):  qty = match(asks, p, ...);  if qty > 0: append [-p, seq, qty, id] to bids, index it
AddLimitOrder(sell at p): qty = match(bids, -p, ...); if qty > 0: append [ p, seq, qty, id] to asks, index it
FillMarketSell:           unfilled = match(bids, no limit, ...)      # never appended anywhere
CancelOrder(id):          record = index.pop(id) or return not_found; its side.remove(record)
```

### Version B — revision (`book_b.py`)

One dictionary `key -> OrderedDict(order_id -> record)` for both sides, where
`key` is the price for asks and the negated price for bids (so the smaller key is
always the better price); the OrderedDict is that price's FIFO queue and also
removes any order directly. A record is the list `[remaining_qty, key,
arrival_seq]`. Per side a binary heap of occupied keys, plus the set of keys
currently in a heap. Book-wide: a dictionary `order_id -> record`.

```
match(heap, limit, taker, qty):                   # limit: buy price, or -(sell price), or 0 for a market sell
    while heap not empty:
        key = heap top
        if key has no level: pop heap; forget key; continue      # stale entry left by a cancellation
        if key > limit: stop
        for maker in level[key] in queue order:   # O(1) per maker
            traded = min(qty, maker.qty); record fill at |key|; reduce both
            if maker exhausted: count it, delete it from the order index
            if qty == 0: break
        if every maker of the level was exhausted: delete level; pop heap top     # O(log P)
        else: remove the exhausted makers from the queue head
        if qty == 0: stop
    release table capacity, or rebuild the heaps, if a threshold is exceeded       # amortized O(1)
    return qty

AddLimitOrder(p): limit = p for a buy, -p for a sell; opposite = the other side's heap
                  if opposite not empty and opposite top <= limit: qty = match(opposite, limit, ...)
                  if qty > 0: key = -limit; append record to level[key]
                              (new level: push key unless it is still in the heap); index it
FillMarketSell:   unfilled = match(bid heap, 0, ...)             # never appended anywhere
CancelOrder(id):  record = index.pop(id) or return not_found
                  delete it from level[record.key]               # O(1)
                  if level empty: delete level; its heap entry goes stale;
                                  rebuild both heaps if they hold more than 2P + 32 entries
```

The passive-order test compares with the heap top without cleaning it first. A
stale top is a key that is no longer occupied; because the heap is ordered, the
true best key is at least as large, so "top > limit" already proves that nothing
crosses, and if the top is at or below the limit `match` cleans it and decides.

`book_b1.py` ("B1") is this revision as first written: two side objects with
their own level dictionaries and heaps, one object per order, and helper calls to
find the best price and a queue. It has the same asymptotic costs. It is kept,
runs through the same tests, and is compared with B in section 7.

## 3. Correctness reasoning

Invariants that hold after every accepted event, in both versions (they are also
executable: `check_invariants()` in each class, called after every event in the
small-stream tests):

1. **One place per order.** Every active order is stored once in its side's
   structure and once in the identifier index, and nothing else is stored there.
   A: both lists contain exactly the indexed records. B: every queue entry is
   the indexed record, and the index has no entry outside a queue.
2. **Positive quantity.** A record's quantity is a positive integer; an order
   reaching zero is removed in the same step that fills it.
3. **Arrival order is stored order.** `seq` strictly increases over accepted
   events and a residual is appended at the tail with its own `seq`, so each A
   list and each B queue is sorted by arrival. A partial fill only decreases a
   quantity in place, so the maker keeps its position.
4. **Best price is found exactly.** A: `min` over `(key, seq)` is the best price
   and, within it, the earliest arrival. B: every occupied key is in its side's
   heap (a key is pushed when its level is created unless an entry for it is
   still there), so after discarding tops without a level, the heap top is the
   best occupied price. After every event the heaps together hold at most
   2P + 32 entries.
5. **Uncrossed.** Matching continues while the incoming order has quantity and
   the best opposite price satisfies its limit, so when a residual rests, no
   opposite order at an acceptable price remains.

*Price-time priority.* By 4 the matching loop always takes the best eligible
price, and by 3 the earliest order at that price; by induction over fills the
fill list is in price-time order. *Conservation.* Each fill moves `traded` from
exactly one maker and from the incoming order, so incoming quantity equals the
sum of its fills plus the returned residual, each maker loses exactly its
fills, and proceeds are the sum of `price × quantity` over the fill list.
Cancellation removes the record and reports the quantity it held at that moment.
A market residual is returned and never appended to a structure.

Evidence, in order of independence:

- **Hand-calculated cases** (`test_orderbook.py`, written first; the run against
  placeholders is `results/test_before.txt`): the supplied worked example and
  every case listed in the assignment.
- **An independent specification model** inside the tests: a pure function that
  applies one event to a list of rows by filtering and sorting, sharing no code
  with the engines. Both versions are compared with it after **every** event
  (result, book, last accepted `seq`), together with quantity and value
  conservation derived only from the returned results.
- **Adversarial suite** (`test_adversarial.py`, added afterwards): all 20,736
  event sequences of length four over a twelve-symbol alphabet; fuzzing that
  reads the model's state to aim at the best level, queue heads, exact-size
  sales, dead and duplicate identifiers; the same streams "hands off", with no
  inspection between events, because inspecting a book discards stale heap
  entries and would otherwise hide that path from the matching loop;
  single-price and 10^18-unit streams; version B's rebuild and capacity-release
  thresholds; metamorphic properties (relabelling identifiers in reverse order,
  scaling quantities, shifting prices, rebuilding a book from its inspection);
  hostile types and damaged files.
- **Planted bugs.** 33 deliberately broken engines (last-in-first-out, trading
  at the taker's price, resting a market residual, strict crossing, ghost orders
  after cancel, a heap that forgets a price, a stale heap top taken for the best
  price, and others) are run through the same checks, and each one must be
  detected.
- **Agreement at scale.** In the benchmark, a SHA-256 digest over every event's
  result and over the final book is compared between versions for every stream
  both completed, and every completed single sale is compared with a fill plan
  computed by sorting the bids.

Agreement of two versions is supporting evidence only; the hand-calculated
cases, the model and the invariants are what the correctness claim rests on.
Passing tests are evidence, not proof.

## 4. Runtime

### Reasoning

Symbols: `M` events in a stream, `B` active orders (`B_side` on one side), `P`
occupied price levels, `F` maker fills of one incoming order, `L` levels that
order empties. Every operation also pays O(1) for validation, the sequence check
and its result dictionary, and O(F) for the fill list it returns. Dictionary
operations are taken as expected O(1).

| Operation | Version A | Version B |
|---|---|---|
| Passive insertion | O(B_opposite): one `min` scan to test for crossing | O(1); O(log P) if it opens a new level |
| Crossing limit / market sell with F fills | O(F · B_side): a `min` scan per fill and a `remove` per exhausted maker | O(F + L log P) |
| Cancellation | O(B_side): `list.remove` scans and shifts | O(1); amortized O(log P) if it empties a level |
| Not-found cancel, rejection | O(1) | O(1) |
| Space | O(B) | O(B + P) entries |

Version A's bounds are worst-case and are reached routinely: building a book of
`B` passive orders on both sides costs O(B^2) in total, and selling through a
book of `N` bids costs about N^2/2 record reads for the scans alone.

Version B's bounds are amortized where delayed cleanup is involved. A
cancellation that empties a level leaves one stale heap entry; that entry is
removed exactly once, by a pop (O(log P)) when it reaches the top or by a rebuild
(O(1) per entry), and the cost is charged to the cancellation that created it.
The operation that meets stale entries pays in real time: one match can pop up to
P + 32 of them, so a single operation is not O(1) in the worst case. After every
event the heaps hold at most 2P + 32 entries. Releasing table capacity copies
O(B) entries once the book has shrunk to an eighth of its peak, amortized O(1)
per removal.

Consequently replay time is not a function of `M` alone. `cancel_churn` has
`B = 1` at any `M`, so both versions are linear in `M` there; `buildup` has
`B = M`, so version A is quadratic and version B linear.

### Measured

Engine replay, median of five, seed 42 (all sizes and seeds are in
`results/observations.md`; "stopped" means the 60 s limit was reached):

| Workload | Peak B at M = 30,000 | A, M = 10,000 | B, M = 10,000 | A, M = 30,000 | B, M = 30,000 | A, M = 100,000 | B, M = 100,000 | B, M = 1,000,000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| buildup | 30,000 | 1.72 s | 33 ms | 18.9 s | 114 ms | stopped | 380 ms | 4.32 s |
| crowded | 30,000 | 2.34 s | 24.1 ms | 17.9 s | 72.2 ms | stopped | 300 ms | 6.41 s |
| sweep | 24,000 | 2.05 s | 40 ms | 23.8 s | 163 ms | stopped | 391 ms | 4.45 s |
| mass_cancel | 15,000 | 603 ms | 37.7 ms | 12.1 s | 81.8 ms | stopped | 280 ms | 3.33 s |
| mixed | 4,628 | 248 ms | 38 ms | 3.73 s | 160 ms | 36.7 s | 341 ms | 5.12 s |
| cancel_churn | 1 | 18.4 ms | 32.7 ms | 65 ms | 80.8 ms | 168 ms | 270 ms | 2.03 s |

- **Submission flood.** Tripling `buildup` from 10,000 to 30,000 events
  multiplies version A's time by 11 (quadratic growth would give 9) and version
  B's by 3.5. Version B stays between about 230,000 and 310,000 events per second
  from 1,000 to 1,000,000 events; version A falls from 52,000 events per second at
  1,000 events to 1,600 at 30,000. Inside one stream, version A's median latency
  rises from 32 µs in the first tenth of `buildup` (M = 10,000) to 448 µs in the
  last; version B's stays at 3.3 and 3.2 µs.
- **It is the book, not the stream length.** `mixed` reaches only 15,118 active
  orders at 100,000 events, and version A still finishes (36.7 s); `buildup`
  reaches 100,000 and version A is stopped after 44,000 events. On `cancel_churn`
  the book never exceeds one order and **version A is the faster one at every
  size** (168 ms against 270 ms at 100,000 events): its scans are free there,
  while version B still creates and removes a queue, a level and a heap entry
  for every order.
- **Large liquidation.** One market sell of 100% of a fresh 10,000-bid book
  takes 4.79 s in version A and 8.78 ms in version B (10,000 fills, 1,000 levels
  visited, identical fill lists). At 10% it is 1.03 s against 0.81 ms; at 200%
  the same 10,000 fills are produced and 5,116.94 BTC are returned unfilled and
  not rested. Version A did not finish a 100% sale of 30,000 bids, or any sale of
  100,000 bids, within 30 s; version B needed 35.1 ms and 137 ms. Constructing
  the book is cheap in both and reported separately (22.9 ms and 20.9 ms for
  10,000 bids).
- **Queue concentration.** With 10,000 bids offered on 1, 4, 32 or 1,000
  prices, version B's sale takes 8.0, 10.4, 7.4 and 8.8 ms and version A's 6.0,
  5.1, 5.8 and 4.8 s: neither depends visibly on concentration here, because
  the fill count is the same and B's extra cost per level (one heap pop) is
  small against the cost per fill. All eight sales equal the independently
  sorted fill plan.
- **Latency by event type** (`mixed`, M = 100,000). Version A's limits have a
  median of 22.2 µs and a 99th percentile of 3.7 ms, its cancellations 3.1 µs and
  668 µs; its market sells are fast (5.9 µs median) because this sell-heavy
  stream keeps the bid side short while asks accumulate. Version B's 99th
  percentiles are 13.1 µs (limit), 21.7 µs (market sell) and 6.9 µs (cancel).
- **Input cost.** Reading and parsing is version-independent and not small:
  687 ms for the 100,000-event `buildup` file and 7.6 s for the one-million-event
  file, more than version B's replay of the same events (380 ms and 4.32 s).

Seeds 42, 43 and 44 agree in every conclusion above; the spread between seeds
(for example 26 to 33 ms for version B on `buildup` at 10,000 events) is in
`results/observations.md`. 28 of 216 engine cells reached a declared limit, all
of them version A.

### Three follow-up experiments

After the benchmark I ran three small experiments of my own with
`experiments.py` (parameters chosen by me, two runs on 25 Nov 2026; the second
is `results/experiments.json`, the first `results/experiments_first_run.txt`).
They are outside the main benchmark, the dashboard and `verify_results.py`, and
the laptop was not idle: the same cell moves by about 1 µs between and within
runs, so only differences well above that are interpreted.

**1. From which book size on is version B faster?** Add-then-cancel pairs on
top of a book of D resting orders (second run, µs per event):

| Resting orders D | 0 | 5 | 10 | 20 | 30 | 50 | 100 | 500 | 2,000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Version A | 1.27 | 2.91 | 1.71 | 1.85 | 1.92 | 3.52 | 3.36 | 18.21 | 53.86 |
| Version B | 1.82 | 1.88 | 1.60 | 1.19 | 1.72 | 2.85 | 1.53 | 1.99 | 2.18 |

Below about 30 resting orders the two versions cannot be told apart: the faster
one changes from size to size and from run to run (at D = 25 version B was 11%
slower in the first run and 18% faster in the second). From about 30 orders on
version B was the faster one in every measurement of both runs, and the gap
keeps growing: version B stays between 1.2 and 2.9 µs at every size, version A
grows roughly linearly to about 50 µs at 2,000 orders. I first read D = 22 as
the break-even point because it was the last size at which B was slower; the
sign changes back and forth below it, so the honest answer is a range, not a
number. Version A is only the better choice where the book is certain to stay
tiny.

**2. Does the position in the queue matter for a cancellation?** N bids at one
price, 100 neighbouring orders cancelled at the front, middle or back (second
run, µs per cancellation):

| Queue length | A front | A middle | A back | B front | B middle | B back |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.81 | 1.26 | 2.69 | 0.86 | 1.41 | 1.13 |
| 1,000 | 1.18 | 19.86 | 42.81 | 1.12 | 2.02 | 1.18 |
| 10,000 | 34.34 | 237.13 | 465.21 | 2.04 | 3.25 | 1.76 |
| 30,000 | 89.91 | 821.05 | 1,819.53 | 1.61 | 1.75 | 1.41 |

Version B stays below 5 µs for every length and position in both runs.
Version A grows linearly with the queue, and the further back the order, the
longer `list.remove` searches: at 30,000 orders the back costs 9 to 20 times
the front. Up to 1,000 orders a cancellation at the front costs the same in
both versions. For longer queues it does not: the record is found at once, but
the rest of the list is moved up by one place, which is 90 µs (176 µs in the
first run) at 30,000 orders. Cancellation in version A is therefore O(n) at
every position, with a much smaller constant at the front.

**3. Do rejected events cost more or less than accepted ones?** 50,000 events
with 0% to 90% invalid ones (duplicate active id, zero quantity, stale `seq`,
unknown type) over a book of about 50 orders. All values of both versions in
both runs lie between 1.3 and 2.9 µs per event without a direction (second run,
version B: 1.65, 1.49, 1.71, 1.93, 1.32, 1.70 µs). Nothing can be concluded
from this beyond the fact that a rejection is not noticeably cheaper or dearer
than an accepted event on a small book; any difference is below what this
laptop can resolve.

## 5. Memory

`tracemalloc` in a separate pass, seed 42. Traced are the book, its indexes and
the most recent result; preloaded input is excluded, and neither version keeps
a trade history.

| Workload, M | Peak B | A peak | B peak | A at end | B at end | Active at end |
|---|---:|---:|---:|---:|---:|---:|
| buildup, 30,000 | 30,000 | 4.12 MiB | 6.74 MiB | 4.12 MiB | 6.74 MiB | 30,000 |
| buildup, 1,000,000 | 1,000,000 | stopped | 310 MiB | – | 310 MiB | 1,000,000 |
| mass_cancel, 30,000 | 15,000 | 2.01 MiB | 3.57 MiB | 449 KiB | 286 KiB | 300 |
| mass_cancel, 1,000,000 | 500,000 | stopped | 155 MiB | – | 7.3 MiB | 10,000 |
| cancel_churn, 100,000 | 1 | 5.27 KiB | 9.34 KiB | 5.02 KiB | 6.31 KiB | 0 |

Version B pays for its speed with about 1.6 times version A's traced memory on
a growing book (235 against 144 traced bytes per resting order at 30,000
orders): two dictionary entries, a queue node and a record per order
instead of one list slot, one dictionary entry and a record.

After cancellation nothing keeps growing. `cancel_churn` holds the same few
kilobytes at 1,000 and at 100,000 events in both versions, and version B ends
with at most 58 stored entries (stale heap entries below the rebuild threshold).
After `mass_cancel` has removed 99% of a 500,000-order book, version B holds
7.3 MiB, 5% of its peak, because it copies its tables once the book has shrunk
to an eighth of the peak; without that step the emptied dictionaries would keep
their peak-sized tables.

The one-million-event rows include up to 1,000 parsed events, because input is
then parsed in blocks inside the trace; the small rise of `cancel_churn` at that
size (337 KiB) is that block, not the book. Traced bytes count Python
allocations made while tracing. They are not auxiliary space (which would count
entries, not allocator behaviour) and not the memory of the process.

## 6. Profiling and the bottleneck

**The bottleneck of version A is finding the best order.** `match` calls
`min(side)` once per fill, and `_add_limit` calls it once per passive insertion
to test for crossing; each call reads every record on that side.

- *Code.* `book_a.py`, `_best` and `_remove`: a scan of the side per fill, and a
  second one when the maker is exhausted.
- *Operation counts* (separate counting pass, `instrumented.py`). Selling 100%
  of a 10,000-bid book: 10,000 `min` scans read 50,005,000 records, exactly
  N(N+1)/2, and `list.remove` reads another 25,038,778; 7,504 records per fill.
  Version B performs 1,000 heap pops (one per emptied level) and discards no
  stale entry for the same 10,000 fills.
- *Profile* (cProfile, `buildup`, 10,000 events): 93% of version A's own time
  is inside `min`; in `mixed` it is 59%, with `list.remove` next at 9%.
- *Timing.* The counts predict a quadratic sale: 3,000 bids take 377 ms and
  10,000 bids 4.79 s, a factor of 12.7 for 3.3 times the orders (11.1 would be
  exactly quadratic).

Version B has no comparable hot spot. In its profile of `buildup` the time is
spread over the dispatcher (31%), `AddLimitOrder` (25%), `_add_limit` (21%) and
dictionary lookups (20%): what remains is validation, bookkeeping and building
results, each O(1) per event. That is why the second revision step could only
remove constant factors, and why version A wins where the book stays tiny.
Profiler times are diagnostic only; the profiler slows Python-level calls far
more than C-level scans.

## 7. Revision and use of AI

### What changed, and why

1. **A to B1: the data organization.** Version A finds the best order by scanning
   and removes by scanning. The first revision (`book_b1.py`) gives every price
   its own FIFO queue, keeps the occupied prices of each side in a heap and
   locates any order through an index, so no operation looks at orders it does
   not trade with or cancel. This is the step that changes the growth rate.
2. **B1 to B: constant factors.** Profiling B1 showed the time spread over many
   small Python-level calls rather than one hot spot, and a book that does
   nothing behind the shared envelope still cost a large share of B1's time per
   event. The submitted `book_b.py` keeps the organization and removes overhead:
   signed price keys in one level dictionary instead of two side objects, a
   three-element list instead of an object per order, a passive order recognised
   from the heap top without a helper call, and the capacity peak updated when
   orders leave instead of when they arrive. The shared envelope now tests "is
   this an ordinary valid event?" in one expression before working out a
   rejection reason, which benefits version A equally.

`tuning.py` replays the same 100,000-event streams through three engines in
one process, interleaved repeat by repeat, after checking that all results are
identical: B1 behind the envelope as first written ("original"), B1 behind the
current envelope, and B. Time of B relative to the original, in three complete
runs (the last one is `results/tuning.json`, the others
`results/tuning_earlier_runs.txt`):

| Workload | Run 1 | Run 2 | Run 3 (saved) |
|---|---:|---:|---:|
| buildup | 0.77 | 0.64 | 0.62 |
| crowded | 0.68 | 0.87 | 0.68 |
| mixed | 0.78 | 0.69 | 0.89 |
| sweep | 0.79 | 0.85 | 0.91 |
| mass_cancel | 0.88 | 0.86 | 0.84 |
| cancel_churn | 0.95 | 0.93 | 0.96 |
| bid book + one 100% sale | 0.85 | 1.09 | 0.89 |

The tuned version is faster on every stream workload in every run, by roughly
5% (`cancel_churn`) to 35% (`buildup`). The size of the gain is not stable: the
same ratio differs by up to 0.2 between runs on this laptop, so only the
direction and the rough magnitude are claimed, and the single-sale row is
within that noise. The step changes no growth rate. Version B is not the
fastest possible order book in any absolute sense: it is pure Python, and
validation, dispatch and result dictionaries still account for most of an
event's cost.

### Tests through the revisions

`test_orderbook.py` was written before any engine and its expected results have
not been edited. Two mechanical changes were made when B1 was preserved: the
list of engines under test gained a third entry, and the cross-version check
compares every engine with the first instead of only the first two. One planted
bug (duplicate check) was rewritten because the hook it overrode no longer
exists. Everything else was added, not changed.

Defects found after the first tests passed, each with a test that fails without
the fix:

| Found by | Defect | Fix |
|---|---|---|
| Damaged-file tests | A file with a byte-order mark crashed the reader; a malformed line gave a bare traceback | Reader accepts a BOM and names the line |
| Measurement tests | Dollar formatting failed above about 10^18 dollars (decimal context limit) | Exact integer arithmetic |
| Review of the rebuild rule | B1's "at most 2P + 32 heap entries" was false when matching, not cancellation, removed the live levels (40 stale entries on an empty book) | Bound checked after matching as well, in B1 and B |
| A planted bug that survived | Inspecting a book after every event discards stale heap entries, so the matching loop never met one under test | "Hands-off" streams with no inspection between events |
| Independent review | Version B's operation counters under-counted when a match rebuilt the heaps and ignored discards made by inspection | Counters now wrap the real heap calls |
| Independent review | A line with an integer of more than 4,300 digits escaped without its line number | Any line the parser refuses is reported with its number |
| First full benchmark | The laptop suspended during a run; two sales were recorded as "stopped" although they had only been asleep | Run repeated; the benchmark now keeps the machine awake and records the power source |

The independent review (a second AI agent given only the assignment text and the
engine files, with the task of breaking them) found no input on which the
engines disagree with each other or with the specification.

### Use of AI

All code, tests and text in this folder were generated with Claude Code
(Anthropic). I set the direction and decided what to keep: to start from my
earlier lab submission, to demand deliberately hostile tests, to ask whether the
revision was as fast as it could be and have it tuned, and to have everything
audited before the final measurement.

The three follow-up experiments in section 4 are the part I carried out myself:
`experiments.py` was generated with Claude Code with the parameter lists left
empty; I chose the book sizes, queue lengths and reject shares, ran it twice,
refined the sizes for the second run and wrote the conclusions (in German;
translated by the tool). It checked my conclusions against the numbers and two
of them were corrected: a break-even point of exactly 22 orders, which is not
supported by the data, and the statement that a cancellation at the front of the
queue costs the same in both versions, which holds only up to about 1,000
orders.

**Accepted.** The specification model inside the tests (a sort-based function
sharing no code with the engines) as the reference for every event; planted bugs
to test the tests; one fresh child process per measurement cell with declared
limits; SHA-256 of the measured sources so that results cannot silently drift
from the code; keeping B1 instead of overwriting it.

**Corrected.** The first estimate of version A's speed was far too optimistic,
which would have made most large cells time out silently; the limits, an
intermediate size of 30,000 events and the "stopped" reporting came from that.
The documented cost of cancellation in version B was first "amortized O(1)";
with stale entries popped from a heap it is amortized O(log P) when a level is
emptied, and the per-operation bounds are amortized, not worst-case. The heap
bound, the counters and the reader were wrong as described in the table above.
A preliminary timing of the tuning step on battery power was discarded.

**Rejected.** A plain `dict` as the FIFO queue: repeatedly removing the head
leaves deleted slots that the next iteration must skip, which is quadratic for a
long queue. A deque with lazily deleted orders: slightly faster insertion, but
inactive orders in the queues, extra state and a second cleanup rule. Folding
the tuned engine into the main benchmark as a third version, or dropping B1:
the assignment asks for a baseline and a revision, so B1 is kept and compared
separately. Extrapolating version A's stopped runs. Disabling the garbage
collector during timing.

## 8. Limitations

- Timings come from one laptop running other background software; individual
  repeats of the same cell differ visibly (the raw repeats are saved). They are
  descriptive medians, not statistical guarantees, and absolute values will
  differ on other hardware and Python versions.
- Version A could not finish the larger growing-book workloads within the
  declared limits. Those cells are reported as stopped; no comparison is made
  for them and nothing is extrapolated.
- Six of the 282 cells were measured a second time. They had run while a web
  browser was being started on the laptop (once to look at the dashboard, once
  to render a preview), and one of them had been pushed over its limit by it.
  They were selected by that time window, not by their values: `crowded` and
  `mass_cancel` at 30,000 events (both versions, seed 42, and the `mass_cancel`
  parse cell) and version A on `mixed` at 100,000 events with seed 43. The log
  of the first pass is `results/benchmark_log_first_pass.txt`; the metadata
  timestamps are those of the second pass. Other cells may carry smaller
  disturbances of the same kind.
- Synthetic streams are stylized. They do not represent realistic order flow,
  timing or strategic behaviour, so the workload mix here says nothing about a
  real market.
- Latency is processing time inside one Python call measured with a clock of
  100 ns resolution. It excludes queueing and network delay and cannot establish
  the event rate at which a live venue would fall behind.
- `tracemalloc` reports Python allocations made while tracing. It is not
  auxiliary space in the complexity sense, and it is not the process's resident
  memory.
- Complexity statements for version B treat dictionary operations as expected
  constant time; adversarial hash collisions are outside the model.
- The engines are single-threaded and keep no persistence, audit trail or
  recovery; identifiers are validated only against currently active orders.
