# Results report

## Scope and model

This project implements a sequential, single-venue synthetic BTC limit order
book. Prices and quantities are positive integers. Matching uses resting-order
prices, best price first, and FIFO within a price. There are no fees, balances,
hidden orders, self-trade checks, network delays, concurrency, or claims about
production exchange capacity. The streams are teaching data, not calibrated
historical records.

## Correctness

The final suite contains 226 passing tests under Python 3.12.10. Independent
hand-calculated expectations cover validation, conservation, FIFO and price
priority, partial fills, cancellations, crossing limits, market residuals, and
the worked example. Small deterministic streams compare each event and
canonical book with a separate test-only reference model. Version A and Version
B also agree after every event. Ten saved diagnostic replays have zero rejected
events and finish with unique identifiers, positive quantities, and uncrossed
books. Agreement is supporting evidence, not the independent oracle.

## Implementations and revision

Version A stores active orders in one list. Each event rebuilds an active-ID
set; matching scans and sorts eligible makers; cancellation scans the list; and
removing an exhausted maker shifts later elements. Its direct matching bound is
`O(B + K log K + F B)` for `B` active orders, `K` eligible makers, and `F`
fills.

Version B uses an active-order dictionary, an `OrderedDict` FIFO queue for each
side-price level, and sorted occupied-price lists maintained with `bisect`.
Existing-level insertion, identifier lookup, FIFO access, and maker deletion
are expected `O(1)`. Creating or deleting a price level costs `O(P)`. Matching
that fills `F` makers and empties `L` levels is expected `O(F + L P)`.
Persistent state is `O(B + P)` and contains no stale cancelled entries.

The revision was selected from Version A measurements: buildup latency grew
with active depth, while 100,000-event cancellation churn completed quickly
with almost no active orders. A lazy-heap suggestion was rejected because
cancelled price entries could accumulate with history rather than live state.

## Runtime and latency

The formal matrix uses five workload families, 1,000/10,000/100,000 events,
seeds 42/43/44, one warm-up, five fresh-book repeats, and a 60-second child
limit. Version A completed 82 of 114 formal tasks and timed out on 32; Version B
completed all 114. There were no failed tasks.

For completed level-1,000 throughput pairs, the median speedup across seeds was:

| Workload | 1,000 events | 10,000 events |
|---|---:|---:|
| buildup | 19.55x | 176.14x |
| crowded | 13.34x | 190.16x |
| mixed | 6.54x | 53.57x |
| sweep | 24.20x | baseline stopped |
| cancel churn | 0.79x | 0.75x |

At 100,000 events the baseline completed only cancellation churn; its matched
median speed ratio was 0.82x, so the revision was slower there. Dictionary and
queue bookkeeping can cost more when `B` never exceeds one and the baseline's
linear scans are effectively constant.

Buildup latency identifies the active-depth bottleneck. Version A's median
early/late windows rose from 10.4/123.7 microseconds at 1,000 events to
42.68/1,751 microseconds at 10,000 events (two completed seeds). Version B was
2.9/3.2, 4.0/4.2, and 4.9/5.1 microseconds at 1,000, 10,000, and 100,000
events. These are processing measurements, not network latency.

Queue concentration exposes the data-structure trade-off. With 10,000 seed-42
buildup events, Version B processed 256,703 events/s at four available prices
versus 174,893 at 1,000; repeated insertion into existing levels avoids
sorted-price-list changes. Version A measured 1,151 versus 1,306 events/s.

## Large liquidation

Each 10%, 100%, and 200% sale rebuilds the same fresh 1,000-maker, 100-level bid
book. The 10% sale touches 101 makers and 11 prices; the full and oversized
sales touch 1,000 makers and 100 prices. The oversized request executes all
1,999,000,000 available units and returns the same quantity unfilled.

Version B's median sell-time speedups were 74.72x, 39.33x, and 54.88x for the
10%, 100%, and 200% sales. Fresh-book construction improved by 18.06x, 17.90x,
and 31.59x respectively. Matching, mutation, and fill-list construction are
inside sale time; book construction is separate.

## Memory

`tracemalloc` runs are separate from timing and exclude preloaded input. They
include book construction, live state, matching temporaries, the current
result, and checkpoint bookkeeping; final inspection is outside tracing.

The indexed revision pays a memory cost. At 10,000 buildup events, median final
state was 2.303 MiB for Version B versus 1.077 MiB for Version A. At 1,000 it
was 0.437 versus 0.111 MiB. Version B reached 21.471 MiB at 100,000; no baseline
comparison exists because those memory tasks stopped.

After 100,000 cancellation-churn events, both books were empty and small:
Version A retained 2,484 bytes and Version B 3,260 bytes. With all returned
event results deliberately retained, each used about 22.0 MB instead. This
demonstrates output-history cost rather than stale book entries.

## Optional one-million-event extension

The post-hoc extension used seed 42, throughput only, and identical 60-second
limits. Version A completed cancellation churn at 281,050 events/s and stopped
on the other four workloads. Version B completed cancellation churn at 332,035
events/s (1.18x matched speedup), crowded at 141,623, and mixed at 161,741
events/s; buildup and sweep stopped. No comparative speedup is assigned where
Version A stopped.

## Profiling, limitations, and interpretation

Bottleneck attribution uses controlled workload profiles rather than timing
alone: active-order/price-level peaks, event-type and fill counts, early/late
latency, queue concentration, liquidation maker/price counts, and
cancellation-churn cleanup. These observations agree with the complexity
difference: Version A repeatedly performs work proportional to `B`, while
Version B shifts work toward `F`, emptied levels, and `P`.

Measurements are from one Windows machine and Python environment. Python
hash-table operations are expected, not worst-case, `O(1)`. `tracemalloc` is
not resident-set size. Timeout results are censored observations, not timings,
and speedups are computed only for completed matched pairs. Synthetic sequence
numbers are ordering keys, not elapsed market time, so the results cannot
establish live-venue throughput or overload capacity.
