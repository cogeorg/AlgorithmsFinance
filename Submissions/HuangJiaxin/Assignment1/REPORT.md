# Report: a limit order book, a baseline and a revision

Huang Jiaxin · Algorithms in Finance · Assignment 1

Notation: **M** incoming events, **B** active orders, **P** occupied price levels (both
sides), **F** maker fills of one event, **L** price levels emptied by one event.

## 1. Specification

Input: a stream of events in `seq` order, starting from an empty book (LIMIT, MARKET_SELL,
CANCEL; fields and units as in the assignment README). Prices are integer ticks of 0.01 USD
per BTC, quantities integer units of 1e-8 BTC; all matching and conservation checks use
integers.

Output per event: the fills in execution order (`maker_id`, `taker_id`, `price_ticks`,
`qty_units`) and a status (`filled`/`resting` for limits; `filled`/`partial`/`unfilled` for
market sells; `cancelled`/`not_found` for cancels; `rejected` with a reason for invalid
events). `snapshot()` returns the active orders in canonical order.

Rules: better price first; FIFO by arrival at equal prices; trades at the resting order's
price; partial fills keep their priority; a limit residual rests with its own `seq` as
arrival rank; a market-sell residual is discarded; a rejected event changes nothing, not
even the last accepted `seq`. Model boundaries: one venue, sequential, all orders eligible,
no fees, balances, hidden orders, self-trade checks or delays. Not a production system.

## 2. Correctness

### Invariants (hold after every accepted event)

1. **Price-time order.** Version A: among all orders of one side, the matching loop always
   picks the best price and, at that price, the smallest `seq`. Version B: each price
   level's deque holds its active orders in increasing `seq`, because orders are only ever
   appended (with strictly increasing `seq`) and removed from the front or lazily marked
   inactive; the heap top, after skipping prices that have no level, is the best price.
   So both versions take the same next maker.
2. **Quantity conservation.** Each trade subtracts the same amount `min(q_in, q_rest)` from
   the incoming and the resting order, so incoming quantity = sum of its fills + returned
   residual, and each maker loses exactly its fills. A cancel removes exactly the
   remaining quantity. Proceeds are the integer sum of price × quantity.
3. **Book shape.** No crossed book: an incoming order stops trading only when it is
   exhausted or the best opposite price no longer crosses its limit, so anything it leaves
   resting is below the best ask (bids) or above the best bid (asks). No resting quantity
   ≤ 0: exhausted makers are removed in the same step. No order stored twice: an order
   enters the book only once, and the duplicate-live-id check rejects reuse.
4. **Version B bookkeeping.** `index` holds exactly the active orders; `live[side][p]`
   equals the number of active orders in that deque; a level exists iff it has an active
   order. Stale deque entries and stale heap prices never affect results, because they are
   skipped before they could be used.

Termination: every iteration of a matching loop either removes a maker, reduces the
incoming quantity to zero, or stops.

### Evidence

* Tests were written first and failed on empty stubs (`evidence/step3_...`).
* 207 tests pass on both versions (`evidence/final_tests.txt`): the course example
  (359,400 USD), hand-calculated cases for every situation listed in the assignment,
  28 kinds of invalid events, invariant and conservation checks after every event of 20
  random streams, and agreement of A and B after every event on 30 random streams and the
  five supplied 10,000-event samples.
* The benchmarks re-check correctness: A and B give identical liquidation results, and a
  full liquidation of concentrated and spread-out books fills in price-time order.
* Agreement between two versions is only extra evidence: on the empty stubs, the
  equivalence tests passed trivially.

## 3. Two versions: pseudocode and cost

### Version A (baseline): one list of all active orders

```
AddLimitOrder(e):
    validate e                         # duplicate-id check: scan the list, O(B)
    while e.qty > 0:
        m = best opposite order        # scan the list, O(B)
        if m is None or m.price does not cross e.limit: break
        trade min(e.qty, m.qty) at m.price
        if m.qty == 0: list.remove(m)  # O(B)
    if e.qty > 0: append e             # O(1) amortized
FillMarketSell(e): same loop on the bids without a limit; residual discarded
CancelOrder(e):    find target by scanning, O(B); list.remove, O(B)
```

| Operation | Time | Notes |
|---|---|---|
| non-crossing insertion | Θ(B) | two scans: duplicate check and best opposite order |
| market sell / crossing limit | Θ((F + 1) · B) | one scan and possibly one removal per fill |
| cancel | Θ(B) | scan and removal |
| inspection | Θ(B log B) | sort for the canonical order |
| space | Θ(B) + Θ(F) output | no history; inactive orders are removed at once |

A stream of M non-crossing submissions therefore costs Θ(M²).

### Version B (revision): price levels, FIFO deques, heaps, an id index

```
AddLimitOrder(e):
    validate e                         # duplicate check: dict lookup, O(1)
    while e.qty > 0:
        p = best opposite price        # heap top; pop stale prices first
        if p is None or p does not cross e.limit: break
        q = deque at p
        while e.qty > 0 and q has a live order:
            m = q.front; if m is inactive: popleft; continue      # lazy cancel
            trade min(e.qty, m.qty) at p; if m.qty == 0: popleft, delete from index
        if level p has no live order: delete level (and maybe rebuild the heap)
    if e.qty > 0: append to deque at e.limit (new level: heap push), add to index
CancelOrder(e):
    m = index.pop(target) or return not_found       # O(1)
    mark m inactive; live -= 1
    if live == 0: delete the level; elif the deque is mostly stale: rebuild the deque
```

| Operation | Time | Notes |
|---|---|---|
| non-crossing insertion | O(1), or O(log P) for a new level | dict check, deque append, heap push |
| market sell / crossing limit | O(F + L log P) plus amortized O(1) per stale entry | each fill O(1); each emptied level one heap pop |
| cancel | O(1) amortized | lazy; level deletion O(1); compaction amortized |
| inspection | O(B + P log P) | sort the price levels, walk the deques |
| space | O(B + P) after compaction | without compaction: grows with all cancels |

**Lazy cleanup and the amortized claim.** Cancel does not search the deque; the entry is
removed when it reaches the front, or when its level loses its last live order. Two rules
bound the leftovers: a deque is rebuilt when it holds more than 2·live + 8 entries, and a
heap when it holds more than 2·(levels) + 16 prices. A rebuild of size k is triggered only
after more than k/2 cheap operations created garbage, so the cost per operation is
**O(1) amortized** (not worst case: a single cancel can trigger an O(k) rebuild).

## 4. Runtime

All numbers: medians of 5 repeats, seeds 42, 43 and 44 pooled, measured on my MacBook Air
(Apple Silicon, 8 cores) inside Docker (Python 3.12.16, Linux aarch64), code `6ad1919`,
declared limit 30 s per run. Raw repeats: `results/timing_raw.csv`.

### Full-stream replay (engine only, fresh empty book)

| Workload | M | A (s) | B (s) | A / B |
|---|---|---|---|---|
| buildup | 1,000 | 0.074 | 0.0029 | 25 |
| buildup | 10,000 | 7.01 | 0.028 | 248 |
| buildup | 100,000 | stopped | 0.265 | |
| crowded | 10,000 | 8.07 | 0.028 | 289 |
| mixed | 10,000 | 1.20 | 0.027 | 45 |
| sweep | 10,000 | 9.73 | 0.030 | 320 |
| cancel_churn | 10,000 | 0.015 | 0.021 | **0.70** |
| cancel_churn | 100,000 | 0.145 | 0.206 | **0.70** |

* **Scaling.** From 1,000 to 10,000 events, A's buildup time grows 95 times (close to the
  100 times expected for Θ(M²) when the book grows with M); B grows about 10 times per
  10 times more events (linear). B processes about 380,000 events per second at
  M = 100,000; A about 1,400 per second at M = 10,000 (buildup).
* **Stopped runs.** A exceeded the 30 s limit at M = 100,000 in every workload except
  cancellation churn: after about 19,000 to 21,000 events (buildup, crowded, sweep) and about
  49,000 events (mixed, where the book stays smaller). These runs are recorded as stopped;
  no times are extrapolated.
* **Where the revision loses.** Under cancellation churn the book holds at most one order,
  so A's scans are almost free, while B pays for dictionary, deque, heap and compaction
  bookkeeping: A is about 30 % faster (A / B = 0.70 at every size).
* **Input versus engine.** Reading and parsing the gzip JSON Lines file takes 0.28 to
  0.32 s for 100,000 events, slightly more than B's replay (0.21 to 0.30 s). For B, the full
  application time (parse + replay) is therefore dominated by input handling; for A, by the
  engine.

### Large liquidation (one fresh bid book from `buildup`, seed 42)

| Book from M events | Sale | Fills | Price levels | A sale | B sale | B per fill |
|---|---|---|---|---|---|---|
| 10,000 (5,025 bids) | 10 % | 522 | 97 | 708 ms | 0.57 ms | 1.1 µs |
| 10,000 | 100 % | 5,025 | 988 | 4,798 ms | 4.98 ms | 1.0 µs |
| 10,000 | 200 % | 5,025 | 988 | 4,810 ms | 5.04 ms | 1.0 µs |
| 100,000 (49,988 bids) | 10 % | 4,990 | 102 | stopped | 6.0 ms | 1.2 µs |
| 100,000 | 100 % | 49,988 | 1,000 | stopped | 55.7 ms | 1.1 µs |
| 100,000 | 200 % | 49,988 | 1,000 | stopped | 55.6 ms | 1.1 µs |

Construction of the book is reported separately (`construction_s`): 8.1 to 9.1 s for A
and 0.026 to 0.027 s for B at 10,000 events. B's sale time is proportional to the number of fills,
about 1 µs per fill, as O(F + L log P) predicts. A's sale costs a full scan per fill, so the
100 % sale is about 960 times slower than B's. The 200 % sale is not slower than the 100 %
sale: once the bids run out, the loop stops and the remainder is discarded in constant
time. A and B returned identical fills in every configuration that A finished
(`liquidation_versions_agree.csv`), and every repeat used a freshly built book.

### Queue concentration (same number of events, 4 vs 1,000 price levels per side)

| M | Levels | A (s) | B (s) |
|---|---|---|---|
| 10,000 | 4 | 8.67 | 0.0261 |
| 10,000 | 1,000 | 7.01 | 0.0282 |
| 100,000 | 4 | stopped | 0.268 |
| 100,000 | 1,000 | stopped | 0.265 |

A scans the same number of list elements however many price levels there are (99,990,000
at M = 10,000 in both `buildup` and `crowded`, which also uses 4 prices), but is about
24 % slower with 4 levels: almost every scanned order has the same
price as the current best, so `_best` also has to compare arrival ranks. B creates 8 price
levels instead of about 2,000 and is about 7 % faster at 10,000 events, but the difference
disappears at 100,000 events, because heap pushes are a small part of B's work. In all 12
configurations, a full liquidation of the resulting bid book filled in price-time order,
and A and B held identical books (`concentration_correctness.csv`).

### Cancellation churn: lazy cleanup with and without compaction (extra)

`B_nocompact` is version B with both compaction rules switched off. It is about 3 % faster
than B (0.205 vs 0.211 s at 100,000 events), because it never rebuilds a heap, but it
leaves 50,000 stale heap entries behind with zero active orders (section 6).

### 4a. One million events (separate run, seed 42, same 30 s limit)

Run with `python -m bench.experiments --million-only` (code `cc1f338`;
`results/timing_million_raw.csv`). The datasets are not uploaded; their generation commands
and SHA-256 checksums are in `data/generated_manifest.json`.

| Workload | Peak active orders / levels | Parse (s) | A replay | B replay (s) | B events per second |
|---|---|---|---|---|---|
| buildup | 1,000,000 / 2,000 | 2.78 | stopped after 24,577 events (30.4 s) | 3.01 | 332,000 |
| mixed | 150,832 / 907 | 2.39 | stopped after 60,929 events (30.0 s) | 1.98 | 506,000 |
| cancel_churn | 1 / 1 | 2.27 | 0.96 s | 1.39 | 722,000 |

B stays close to linear: buildup takes 11.4 times as long as at 100,000 events for 10 times
as many events, with a book of one million active orders. A again only finishes
cancellation churn, where it is still about 30 % faster than B. Memory was not traced at
one million events; the preloaded input alone is about 0.9 GB by the 890 bytes per event
measured in section 6, which is why streaming input would be needed beyond this size.

## 5. Latency (separate instrumentation run, seed 42)

Per-event engine time in microseconds; nearest-rank percentiles; no queueing or network
delay (`results/latency_summary.csv`, raw times for M = 10,000 in `latency_raw_10000.csv.gz`).

| Workload, M | Version | p50 all | p99 all | p50 first 10 % | p50 last 10 % |
|---|---|---|---|---|---|
| buildup, 10,000 | A | 713 | 1,450 | 75 | 1,329 |
| buildup, 10,000 | B | 2.5 | 5.8 | 2.9 | 2.5 |
| buildup, 100,000 | B | 2.8 | 10.7 | 2.5 | 2.8 |
| crowded, 100,000 | B | 2.5 | 9.9 | 2.4 | 2.6 |
| sweep, 100,000 | B | 2.8 | 13.1 | 2.7 | 1.6 |
| cancel_churn, 100,000 | A | 1.8 | 2.2 | 1.8 | 1.8 |
| cancel_churn, 100,000 | B | 2.5 | 3.0 | 2.5 | 2.5 |

A's median latency grows 18 times from the first to the last 10 % of a buildup stream,
because every order scans a longer list. B's overall median stays between 2.5 and 2.8 µs at every
book size; at 100,000 events its late events are about 10 % slower than its early ones,
not faster. Only in `sweep` are the last events faster, because they are market sells
against an almost empty bid book. Market sells have the highest tail in B (p99 about 16 to
17 µs at 100,000 events) because one event can produce many fills. A failed the 30 s limit at
M = 100,000 for all workloads except churn (`latency_stopped.csv`).

## 6. Memory (tracemalloc, separate run, seed 42)

Tracing starts after the events are preloaded; each result is dropped after its event; no
history is kept (`results/memory.csv`, `memory_growth.csv`).

| Workload, M | Input (preloaded) | A book after | B book after | B peak |
|---|---|---|---|---|
| buildup, 10,000 | 8.9 MB | 1.93 MB | 2.71 MB | 2.71 MB |
| crowded, 10,000 | 8.9 MB | 1.93 MB | 1.10 MB | 1.10 MB |
| sweep, 10,000 | 8.4 MB | 0.76 MB | 1.42 MB | 2.54 MB |
| buildup, 100,000 | 89 MB | stopped | 14.6 MB | 15.5 MB |
| cancel_churn, 100,000 | 73 MB | 0.001 MB | 0.002 MB | 0.005 MB |
| cancel_churn, 100,000, B_nocompact | 73 MB | | 2.05 MB | 2.05 MB |

* **Orders and levels.** B stores each order as a slotted object and each price level as
  its own deque. With many levels and short queues (buildup: 1,977 levels) the per-level
  cost makes B 41 % larger than A; with 8 long queues (crowded) B is 43 % smaller, because
  a slotted object is smaller than A's dictionary per order.
* **Output.** The sweep peak (2.54 MB) is larger than the book afterwards (1.42 MB) because
  a large sale's fill list is alive while it is returned.
* **Stale entries.** With compaction, churn leaves 0 stale deque entries and 3 stale heap
  entries. Without compaction, the heap grows by about 200 KB per 10,000 events, linearly
  with the number of submissions, although the book is empty: unbounded growth that the
  compaction rule prevents. In `mixed` at 100,000 events, B holds 5,814 stale deque entries
  next to 15,113 active orders, within the rule's bound of 2 × live + 8 per level.
* **Input.** The preloaded events (about 890 bytes per event) are larger than any book;
  streaming (`iter_events`) would remove that from memory, at the cost of mixing parsing
  into the replay time.

Traced allocations count Python objects only. They are neither auxiliary space (they
include the book itself) nor total process memory (they exclude the interpreter and
allocator overheads).

## 7. Profiling and the main bottleneck

cProfile, 10,000 buildup events (`results/profile_*.txt`; profiling slows the code, so
these numbers are only used for shares):

* **Version A, 7.24 s:** `_best` 5.27 s (73 %) and `_find` 1.84 s (25 %). Every LIMIT
  event scans the list twice: once to reject a duplicate live identifier, once for the best
  opposite order. The operation counts confirm it: 99,990,000 list elements scanned for
  10,000 events, which is 2 × (0 + 1 + … + 9,999) = M(M − 1), so the cost is Θ(M²) for a
  growing book. That is the bottleneck behind A's stopped runs.
* **Version B, 0.145 s:** the largest item is now the shared validation, `check` with
  0.084 s cumulative (58 %), followed by Python call overhead; matching (`_match`) and
  heap work (`_best_price`) take only a few milliseconds. After the revision, the
  bottleneck moved from data organization to per-event Python work that both versions share.

## 8. The revision

| | Version A | Version B |
|---|---|---|
| Find best opposite order | scan all B orders | heap top, skipping stale prices |
| Duplicate-id check, cancel | scan all B orders | dictionary lookup |
| Remove an order | `list.remove`, O(B) | pop from the front of its deque, or mark inactive |
| FIFO at a price | compare arrival ranks during the scan | the deque order itself |

**Why:** the profile and the operation counts showed that A spends almost all of its time in
two full-list scans per event. **Effect:** 45 to 320 times faster at 10,000 events (all workloads except churn); linear
instead of quadratic scaling; flat latency; every run finished within the limit.
**Where it does not win:** cancellation churn with a tiny book (A about 30 % faster), and
memory when orders spread over many price levels (B 41 % larger in buildup). All earlier
tests stayed unchanged and pass; 12 tests for B's lazy cleanup were added.

**Bug found in a final review.** Replaying every event of A, B and B without compaction
against a separate brute-force reference (written only from the assignment rules) on 430
random streams with malformed fields found one bug: a `type` or `side` given as a JSON list
or object crashed validation (`TypeError: unhashable type`) instead of rejecting the event,
so one bad line stopped a whole replay. Fix: check that both are strings before the set
lookup. Three invalid-event cases were added to `tests/test_validation.py` (they failed
first, `evidence/review_fix_tests_before.txt`); no existing test changed. The fix only
affects malformed events, so the measurements (code `6ad1919`, all valid streams) still apply.

## Predictions compared with the results

My predictions (`PREDICTIONS.md`, committed before the full run):

| # | Prediction | Result | Verdict |
|---|---|---|---|
| 1 | A does not finish 100,000 events in 30 s; about 700 s | stopped after about 20,000 events in every growing-book workload | correct (the 700 s is not checked: no extrapolation) |
| 2 | A: about the same for 4 and 1,000 levels. B: 4 levels faster | A scans the same number of elements but is 24 % slower with 4 levels (extra tie-break comparisons). B 7 % faster at 10,000, equal at 100,000 | A: partly wrong; B: right direction, small effect |
| 3 | 200 % sale slowest, slightly slower than 100 %, because the unfilled half needs extra work | 200 % and 100 % take the same time; the remainder is discarded at once | wrong reason: no extra work |
| 4 | Parsing takes longer than B's replay | 0.28 to 0.32 s vs 0.21 to 0.30 s at 100,000 events | correct |
| 5 | B does not slow down; last 10 % faster than first 10 % | B's median stays at 2.4 to 2.8 µs, but the last 10 % is about 10 % slower in buildup; faster only in sweep | first half correct, second half wrong |

## 9. Extras

1. **Price impact of a large sale**: average fill price and its distance from the best bid
   for 10 %, 100 % and 200 % sales (dashboard tab "Large liquidation").
2. **Lazy cleanup with and without compaction** (`B_nocompact`): time and memory under
   cancellation churn, and the number of stale entries left behind.
3. **Docker and one-command reproduction** (`run_all.sh`).

## 10. Limitations

* Synthetic, uncalibrated data; sequential replay of one venue. Processing latency excludes
  queueing and network delays and cannot tell when a live venue would overload.
* Timings come from one laptop inside Docker; they vary between runs and machines.
* Version A could not finish the largest workloads within the declared limit; those runs
  are reported as stopped, not extrapolated.
* tracemalloc sees Python allocations only; it is neither auxiliary space nor total
  process memory.
* The liquidation, latency and memory experiments use seed 42 only, to keep the total
  run time manageable; the replay grid uses seeds 42, 43 and 44.
* One-million-event streams were run for three workloads and seed 42 only, without memory
  tracing (section 4a).

## 11. Use of AI

I used Claude (Anthropic) as a coding assistant throughout this assignment.

**What the AI did.** It drafted most of the code: both order book versions, the tests, the
benchmark and instrumentation scripts, the dashboard, the Docker setup, and first drafts of
the README and this report.

**What I did myself.**
* I wrote the predictions in `PREDICTIONS.md` myself and committed them before any full
  results existed. I then asked the AI to check my reasoning. Its feedback helped me find my
  own mistake: I first estimated 49 s for A at 100,000 events, then understood that a cost
  growing with M² means about 100 times more time for 10 times more events, so about 700 s.
* I practised hand traces of binary and linear search in the lab, then traced the worked
  example through version B by hand (`TRACE.md`) and compared it with the code.
* I ran every measurement on my own laptop in Docker and checked the dashboard against the
  saved results.
* After the core requirements were done, I asked the AI for possible extensions, chose three
  of them (price impact, lazy cleanup versus compaction, Docker) and asked for the dashboard
  myself.
* Before writing my predictions, I asked the AI to explain dictionaries and hashing, Big O
  notation and the data structures of both versions in plain terms, so that I could explain
  the differences in speed and memory myself.

**Accepted.** The design of version B (one FIFO queue per price level, heaps, an id index,
lazy cancellation with compaction). I accepted it after the profile and the operation counts
showed that version A spends almost all of its time scanning the list.

**Corrected.** Checking the AI's output against the data found several mistakes:
* the README gave the wrong number of tests failing on empty stubs (157 instead of 152);
* a missing import in `bench/experiments.py`;
* the dashboard's liquidation tab filtered for a status that never appears, so it would
  have shown nothing;
* several numbers in the first report draft did not match `results/` (construction time,
  the speed-up range, the number of price levels), so they were recomputed from the CSV files;
* a final review against a separate brute-force reference found that a malformed `type` or
  `side` crashed validation (section 8).

**Rejected.** The AI pointed out that the Docker image would be more reproducible in the long
term if every dependency and the exact Python version were pinned. I kept only the direct
dependencies pinned (`requirements.txt`) and the `python:3.12-slim` base image, because the
project only needs to be reproducible while it is being graded. I had made the same decision
in the lab.

**What I learned.**
1. **Estimating run time from complexity.** A scans the whole list for every order, and the
   list grows with the number of events, so its total time grows with M². From 7 s at
   10,000 events, I could estimate about 700 s at 100,000, far beyond the 30 s limit.
2. **Price levels and memory.** Which version uses more memory depends on how orders are
   spread over prices. With many short queues (buildup, about 2,000 levels), B's per-level
   queues make it 41 % larger than A. With a few long queues (crowded, 8 levels), B is 43 %
   smaller, because its slotted order objects are smaller than A's dictionaries.
3. **How Python dictionaries use memory.** Deleting entries does not shrink a dictionary at
   once; space is only given back when the table is resized later. It also grows in large
   jumps, so measured memory rises in steps.
4. **A better algorithm does not win everywhere.** With a tiny book (cancellation churn), A
   was 30 % faster than B: scanning one order is almost free, while B updates a dictionary,
   a deque and a heap every time. Complexity decides at scale; constant costs decide at
   small sizes.
5. **Agreement is not proof.** A and B always agreed, but a separate reference still found a
   bug that both shared, because they use the same validation code.
