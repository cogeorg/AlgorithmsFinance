# Phase 1 report — Garv Sharma

## 1. Specification and financial behavior

The engines implement a sequential single-venue BTC limit order book. Prices
are positive integer cents; quantities are positive integer 1e-8 BTC units.
Limit buys cross the cheapest eligible ask; limit sells cross the highest
eligible bid. Within a price the original accepted sequence determines FIFO,
independently of identifier spelling. Trade price is the resting maker's
price. A partially consumed maker retains priority; a residual incoming limit
rests at its submitted price. Market sells consume bids and discard any
unfilled residual. Cancels remove exactly the remaining quantity or return
`not_found`. Validation finishes before mutating state, and rejection does not
advance the accepted sequence. There are no fees, balances, hidden orders,
self-trade prevention, concurrency or network effects. These synthetic streams
are teaching workloads, not calibrated exchange behavior.

The worked six-BTC liquidation yields four fills at 60000, 60000, 59900 and
59700 USD/BTC for 1, 1, 3 and 1 BTC, giving USD 359400. Four BTC remain on b4;
the two-BTC ask is unchanged. Both versions return the supplied exact objects.

## 2. Correctness, tests and invariants

The initial tests were written before the engines; the saved first run fails
because `orderbook` is absent. The baseline and revised engine then pass the
same hand-calculated contract cases. Regressions were added without weakening
expected outcomes. The final suite has 20 test methods, with subcases for
smaller/equal/oversized sales, both crossing directions, invalid numeric
values including booleans, identifiers, sequences and cancellation histories.
A 1000-order single-price queue tests identifier order versus arrival order.

Invariants: every active identifier denotes exactly one positive-quantity
order; best prices reflect occupied levels; each price queue preserves
accepted arrival sequence; a live book never rests crossed bids and asks.
For each match q=min(incoming,maker) is removed from both quantities and one
fill is emitted. No operation can consume more than either quantity. An
incoming limit residual is indexed once, whereas market residual is never
indexed. Cancel removes only the live residual. The generated test suite
checks both versions after every event across 15 scenario/seed streams,
including exact ordered fills, order identity, conservation, noncrossing and
positive remaining quantities. Agreement supplements independent expectations;
it does not replace them. The shared validation/dispatcher is a common-mode
risk mitigated by the explicit contract cases.

Version B's extra invariant is that heap roots identify live best prices and
per-price `OrderedDict` heads identify earliest live makers. Deleted price
entries may remain below a heap root, but cleanup removes invalid roots.
Rebuilding when H > 2P+32 bounds heap storage. A persistent-best cancellation
regression prevents an otherwise easy-to-miss stale-entry accumulation case.

## 3. Runtime and algorithmic costs

Let B be active orders, P occupied price levels, M input events and F makers
filled by one submission. State the cost at current sizes, rather than
substituting M for B. Hash-table operations use expected/amortized O(1), with
adversarial hashing outside these claims. No trade history is retained.

Both engines share this matching pseudocode:

```text
validate entire event; reject without mutation if invalid
advance accepted sequence
if cancel: remove live residual if any; return status
while incoming remains and best opposite price is eligible:
    choose earliest maker at that best price
    q = min(incoming remainder, maker remainder)
    decrement both; append maker-price fill
    remove exhausted maker and update price indexes
if residual limit: append to its own price queue at original arrival rank
return current event result and ordered fills
```

Version A stores arrival-ordered individual-order lists, an active-ID map,
price counts and cached best prices. A noncrossing addition appends and updates
indexes in expected amortized O(1). It need not scan an opposite side whose
cached best price proves noncrossing. Matching scans an opposite list for the
first maker at the cached best price; each exhausted maker also requires a
list search and shifting removal. Removing the last order at a price scans
the remaining price-count keys to recompute best. With K depleted prices, a
crossing submission costs O(1 + F*B + K*P + F), bounded by O(1+F*B) for P<=B
at meaningful nonempty states. Cancellation is O(B+P) worst-case, including
list shifts and best-price rescan; unknown cancellation is expected O(1).
The O(F) fill-list construction is included. Keeping a cached best price makes
passive buildup intentionally cheaper than a baseline that sorts every time.

Version B uses two price heaps, one FIFO OrderedDict per live price and an
active-ID map. Joining an existing queue is expected amortized O(1). A new
price pushes its heap key in O(log(P+1)); cleanup may also remove stale roots
and occasionally rebuild. Matching obtains each FIFO maker in expected O(1),
deletes it in expected O(1), and performs heap work on depleted prices.
Amortized insertion/cancellation is O(log(P+1)), and selling is
O(1+F+K*log(Pmax+1)) amortized, charging delayed cleanup to earlier insertions
and deletions. Across a stream heap pushes/pops cost O(M log(Pmax+1)); stale
keys and compactions must be included in this accounting. One cleanup may
pop O(P) stale keys or rebuild O(P) entries, so **one-operation worst case can
be O(P log(P+1))**, not O(log P). Unknown cancellation remains expected O(1).
Occupied-level lookup, validation and output dictionary creation are included
in these bounds. Full `inspect()` sorts and copies in O(B log(B+1)) time.

For a full replay, sum event costs at evolving B_i, P_i and F_i. Noncrossing
builds can be linear even with large M; cancellation churn keeps B tiny.
Neither throughput nor one plot alone proves a universal asymptotic bound.

## 4. Memory and workload measurements

Both engines retain O(B+P) engine state plus O(F) transient fills. The caller
may request an O(B) detached inspection snapshot. Baseline lists/map/counts
hold references to the same order dictionaries. Revised queues/map reference
the same dictionaries; heaps are bounded by O(P+1) after compaction. No output
history grows with M. More events do not necessarily mean more live orders:
the cancellation-churn stream alternates insert/remove and ends empty.

The experiment grid covers five workload families, M=1000/10000/100000 and
seeds 42/43/44. Input construction and five read/decompression/JSON repeats
are separate from five engine replays; each replay starts empty after warmup.
Separate runs capture per-event medians/p95/p99, begin/end batch latency,
latency histograms, active/price peaks and traced allocations at checkpoints.
Fresh-book liquidation holds B fixed while varying price ranges 4 versus
1000, with sales 10%, 100%, 200% of initial bid depth. Five repeats separately
record construction, sale, maker touches, levels visited and residuals.

Every raw repeat remains saved. Only five-success groups have summary medians.
The same three-second phase budget applies to both engines; process watchdogs
are 90 seconds for normal workers and 45 seconds for the million-event
attempt. Timing checks occur every 256 replay events; an individual sale is
uninterruptible until its worker watchdog. Completed sales beyond the phase
budget are labelled `over_limit`, excluded from complete medians, and retained.
One-million-event buildup is attempted for both engines; missing phases are
censored, not fabricated. No byte-based memory limit is claimed.

`tracemalloc` starts after input preloading. It includes live book structures,
transient fill/result objects, samples and runner allocations; the input
array, native allocations and process RSS are excluded. It measures Python
allocation behavior rather than an exact mathematical auxiliary-space count.
Checkpoint current/peak bytes show growth and post-cancellation state. Memory
runs are never used for primary timing. The dashboard loads saved JSON and
shows scaling, throughput, latency, allocation growth, correctness and stopped
runs; it does not execute the engine.

## 5. Profiling, revision and interpretation

The revision replaces list-based maker search and shifting removals with
per-price FIFO queues, direct ID deletion and best-price heaps. Small diagnostic
runs count scanning entries, queue-head lookups, heap pushes/pops and rebuilds
outside timing. Separate `cProfile` runs cover 3000-maker liquidation. These
provide code-level explanations for the measured sale bottleneck rather than
assuming that a revised structure must always win.

We retain A's cached-best passive insertion optimization: it is a useful
counterexample to claims that heap-based B must always improve buildup. B
allocates queue objects and performs heap maintenance, so it can trade memory
and passive-insertion time for faster liquidation and cancellation at scale.
High fill count still entails unavoidable O(F) output work in either version.
Short cancellation-churn books reduce the list baseline's scan penalty.

During review, malformed `type=[]`/`type={}` inputs exposed a dispatch lookup
that could throw before validation. A type guard and regression cases correct
this for both versions. The first benchmark was interrupted; its exploratory
raw file is clearly excluded. The full primary grid was restarted against the
final source fingerprint. This revision history and the accepted/corrected AI
suggestions are disclosed in `AI_USAGE.md`.

The following values are five-repeat replay medians for M=100000, seed 42,
in seconds. Complete seed 43/44 observations are in the saved tables.

| Workload | A median seconds | B median seconds |
|---|---:|---:|
| buildup | 0.263036 | 0.343112 |
| crowded | 0.263376 | 0.322692 |
| mixed | stopped | 0.305415 |
| sweep | stopped | 0.414331 |
| cancel_churn | 0.206202 | 0.247650 |

B is about 30% slower on buildup here, consistent with extra queue/heap work;
it completes mixed/sweep within the same budget where the list baseline does
not. These are workload-specific observations, not a universal speed ranking.
At M=100000, buildup occupies 100000 orders and 2000 price levels; crowded
occupies 100000 orders but only eight levels. Cancellation churn peaks at one
order/level and ends empty despite the same event count. This directly shows
why M alone does not characterize active depth.

For seed 42, buildup traced peaks are 23218312 bytes for A versus 30640944 for
B, roughly 32% more for B. After 100000 cancellation-churn events, current
traced bytes are 10360 for A and 10872 for B, including sampling/runner
overhead. These end-empty observations and the persistent-best regression
support bounded retained state; they are not a proof about process RSS.

Separately measured seed-42 buildup p95 processing latencies are approximately
2.90 microseconds for A and 4.40 for B. B's mixed p95 is 6.20 microseconds and
sweep p95 11.80 microseconds. These samples are independently timed, not
computed from throughput; instrumented values include timing overhead.

Settings, source fingerprints, checksums and profiles are the traceable
evidence; no historical or production-load claim is made.

For B=10000, seed 42, the revised full-sale median is 0.015454 seconds with
four available prices and 0.016431 seconds with 1000. A's five observed full
sales all exceed the three-second limit: their observed duration medians are
3.248881 and 4.105883 seconds respectively. These A durations describe
over-budget observations, not successful summary medians. Every completed
sale's conservation and FIFO diagnostic is true, including the 200% requests.

At B=1000, four prices, diagnostic A scans 174820 maker entries and 174820
removal entries for 1000 fills; B performs 1000 queue-head lookups and four
heap pops. At a 1000-price range, 637 prices are actually occupied: A scans
241846 entries in each of its maker/removal passes and 202566 best-price keys;
B performs 1000 queue-head lookups and 637 heap pops. These measured counts
explain why individual-order scanning is a liquidation bottleneck. Profiling
results separately identify those list-scan methods in cumulative runtime.

There are **1838 primary raw records**: 1725 successful, 56 stopped and 57
completed over budget, with no worker errors. Both million-event buildup
attempts hit the phase budget in all five replays: A completes about
880896–918784 events before stopping, B about 616960–638464. Their million-event
latency and allocation runs also stop. Parsing completes, but **no complete
million-event engine replay or median is claimed**. This bounds the experiment
and preserves the failed-scale evidence rather than concealing it.

## Limitations

This is one machine and interpreter with five repeats, synthetic event mixes
and a bounded experiment budget. We report wall-clock noise without statistical
significance claims. Latency instrumentation adds overhead and excludes
network/queueing, so it cannot establish real-time overload capacity. Finite
tests do not prove all Python dictionary inputs or executions correct. No
exchange calibration, concurrent matching, process-memory accounting, peer
audit or Phase 2 work is claimed. The million-event attempt is only buildup
seed 42, not an exhaustive million-event sweep. There is no byte-based memory
watchdog. See stopped runs instead of extrapolating censored measurements.
