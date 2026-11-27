# Phase 1 report — sequential BTC order book

## Scope and interfaces

The assignment requirements describe a single-venue, sequential continuous limit order book.
All orders are eligible. Fees, balances, hidden orders, self-trade prevention, network/queueing delays,
strategic agents and concurrent execution are excluded. Synthetic inputs are not calibrated exchange data.
Sequence numbers define arrival order, not elapsed market time. This is a teaching model.

Both versions expose process_event, AddLimitOrder, FillMarketSell, CancelOrder and inspect_book.
The external dispatcher reads JSON Lines or gzip files and delegates to process_event.
Inspection returns independent active orders under bids and asks in canonical price-time order.
Prices are positive built-in integers in USD cents/BTC; quantities are positive built-in integers in
10^-8 BTC units; accepted sequences increase strictly. Booleans, floats and invalid submitted values
are rejected atomically, including leaving the accepted sequence unchanged. A cancellation of an
unknown identifier is accepted as not_found. Historical submission-ID reuse validation is outside scope.

## Algorithms and conservation

~~~text
process_event(event):
    route LIMIT, MARKET_SELL or CANCEL to the corresponding public handler
    reject an unknown type or invalid container without mutation

public handler(event):
    validate every required field, exact integer type, live ID and sequence
    reject before changing any state if invalid
    execute the appropriate operation; advance accepted sequence

match(side, remaining, optional_limit):
    while remaining > 0:
        select best live opposite-side maker by price then original arrival
        stop if absent or outside the incoming limit
        q = min(remaining, maker.remaining)
        append fill(maker ID, taker ID, maker.price, q)
        subtract q from incoming and maker
        remove an exhausted maker; preserve a partial maker's position

limit(event):
    match eligible opposite-side orders
    rest residual on its side at its limit price and original event sequence
    return filled if residual is zero, otherwise resting

market_sell(event):
    match highest bids first without a price limit
    return filled, partial or unfilled and the unsold residual
    never rest the market residual

cancel(event):
    find the active target
    return not_found and zero if absent
    remove its remaining live quantity and return cancelled
~~~

The maker supplies the execution price, including for crossing limits and equal prices.
FIFO is original arrival sequence, independent of identifier spelling. Revised stores identical order
objects in an ID index and per-price deques; a maker partially filled at the head remains first.
Bids use negated heap keys, while orders, fills and snapshots retain positive original prices.
An inactive queue object is excluded by identity against the live ID index. Reusing an ID cannot
revive an old object. Stale prices are skipped or rebuilt; price recreation preserves new FIFO state.

For each submission: incoming units = executed units + returned residual.
For each maker: prior units = executed units + live remainder.
Cancellation returns only the remaining live quantity. A limit residual rests; a market residual does not.
Gross proceeds sum price_ticks * qty_units using integers, divided by 10000000000 for USD display.

The worked example fills b1, b2, b3, b4 in quantities 1, 1, 3, 1 BTC, yielding USD 359,400.
Four BTC remain on b4 and the two-BTC ask a1 is unchanged. This is checked against independent literals
and the supplied reference, not inferred from agreement between the implementations.

## Correctness evidence and its limits

The preserved suite includes independently calculated empty/small/exact/oversized sales, multiple makers,
multiple prices, partial-fill priority, noncrossing/crossing limits, cancellations, malformed inputs,
large exact integers, sequences and generated-stream invariants. ComparedOrderBook compares ordered
results and canonical books after every event, including rejection and direct handler calls.
Heap and lazy-cleanup regressions check internal index consistency and retained-storage bounds.

The matching loop and validation are shared between versions: the revision changes storage, indexing,
best-maker lookup and cleanup. Differential agreement therefore cannot detect a shared matching bug.
Independent expected outcomes, conservation checks and the worked example are necessary supplements.
No retained executable record establishes an initial failing TDD run for the complete implementation;
this report makes no claim that such a red phase was observed.

Final tests and verification evidence are recorded in results/phase1_final/verification.json.
Controlled sale auditing reconstructs the exact ordered fills independently from sorted source bids,
including their distinct executed prices, quantities and residual, and checks complete diagnostic
result/book digests. This avoids equating maker count with price-level count.

## Complexity of the measured implementations

Let B be live orders, P occupied side/price levels, M processed events, F maker fills in one operation,
R retained objects in an affected deque, H retained price-heap entries, and T skipped inactive heads.
Hash operations below have expected constant cost. Bounds treat integer operations as constant;
arbitrarily large integers add bit complexity.
Pathological hash collisions can make an individual dictionary lookup linear in retained table capacity; the expected
index bounds below are not deterministic worst-case hash-table guarantees.

Baseline stores a list. Duplicate-ID validation, active-ID lookup and cancellation scan up to B orders.
Appending itself is amortized O(1), but a submitted limit including validation/matching is not.
Matching and removals cost O((F+1)B); cancellation costs O(B).
Growing passive insertion can require O(M^2) work when B grows with M.
Inspection sorts/copies in O(B log B) time and O(B) output space.

Revised ID lookup is expected O(1). A new price may push a heap key in O(log(H+1)).
Same-price insertion appends to a deque. Best-maker lookup reads a live heap root and head, with
additional work for stale roots and inactive heads. F fills require O(F) output allocation and
state updates; traversing exhausted levels adds heap maintenance.

Logical cancellation removes the ID and updates a live count in expected O(1), without searching
the deque. Queue clearing/compaction and heap rebuilding cost O(R+H+P) in the dense-map abstraction;
with sparse retained CPython price dictionaries, a conservative complete cleanup cost is O(R+H+P_max).
It is not guaranteed O(1). A queue with L live entries is compacted when R > 2L+32 and deleted when
L=0. Stable filtering preserves FIFO. A heap is rebuilt when H > 2P+32 per side and cleared at P=0.
Retained-key sets prevent duplicate keys during price recreation.

Queue compaction work is amortized across accumulated inactive entries; each inactive object is eventually
released. Heap rebuilding can be charged to stale keys in the dense-map abstraction, but retained sparse
dictionary capacity can add work not bounded by current stale-key count. No general amortized O(1)
claim is made for complete cancellations. An individual cleanup pause remains linear.
Popping S stale heap roots costs O(S log(H+1)).
Total matching work includes validation, F outputs, skipped heads, level maintenance and any rebuild,
rather than only a logarithmic best-price lookup. Sorting the B live inspection rows costs O(B log(B+1));
enumerating a sparse CPython dictionary can additionally reflect retained entry-table capacity.

Baseline live storage is O(B). Revised retained queues satisfy sum R <= 2B+32P; heaps satisfy
the per-side bounds, so live/stale entry counts are O(B+P+1). A current fill list adds O(F).
This entry bound does not guarantee allocated bytes track current B: CPython dictionaries do not
shrink on every deletion. The ID/price/count dictionaries can retain capacity associated with prior
peaks B_max and P_max, even when their logical length is zero. Allocated container capacity may
therefore require O(B_max+P_max+1) space. No dictionary-capacity optimization is added here.
Conservatively, Revised inspection can take O(B_max+B log(B+1)) time after a large depth reduction,
rather than promising a bound solely in current live orders.
The anchored churn experiment keeps peak depth small and does not test shrinking a previously huge
ID table. Traced current bytes include retained container capacity; zero live entries do not imply zero bytes.
Preloaded inputs add O(M) outside the reported incremental engine trace. Neither implementation
saves result history in the primary runner; the external dispatcher optionally retains returned results.

## Measurement protocol

The unchanged runner preloads inputs and uses perf_counter, a full untimed warm-up and five repetitions
with fresh books. Binary reading, gzip decompression and UTF-8/JSON parsing have separate clocks.
Initialization and controlled construction are separate from replay/sale, and per-repeat compute total
is initialization + construction + operation. Its median is taken after summing each repeat.

Primary timing excludes canonical inspection, comparison wrappers, counters, JSON output and tracing.
Throughput is processed events / replay seconds; a single-sale case processes one event, not its setup.
Latency uses a separate instrumentation pass. Median averages the middle pair; P95/P99 use nearest
rank sorted[ceil(p*n)-1], without interpolation or clock-overhead subtraction. First/last 10% latency
describes the same uninterrupted pass. It is processing latency, not overload capacity or network latency.

Tracemalloc runs in a separate process. Input/imports/warm-up are excluded from tracing; book construction,
temporary results and cleanup are included. Current allocations are sampled after GC with the book alive.
No saved result history is included. Python allocation bytes differ from RSS, native reservations and
algorithmic auxiliary space. Existing input objects referenced by orders remain excluded.

Limits remain 60 seconds per worker (including loading and warm-up), 900 seconds per measurement
campaign (excluding preparation), 128 MiB payload and 512 MiB traced allocations checked between events.
There is no OS RSS hard cap. One case per controlled command avoids starving unrelated cases.
Stops retain completed raw repetitions and null incomplete medians. A timeout is not a replay duration.

## Measured findings, profiling and limitations

The required matrix contains 99 workload cases and 891 phase groups: 759 completed and 132 stopped,
with no failed, missing or unattempted required groups. Baseline timeouts are retained as outcomes,
not estimated durations. There are 72 matching required diagnostic pairs and 27 unavailable pairs;
67 required primary-timing pairs satisfy all comparison conditions. Earlier count-120 validation
adds six cases to the broader saved-data index and is excluded from those required-coverage counts.

Representative complete Revised medians for seed 42 are:

| Experiment | Requested count | Construction, seconds | Replay/sale, seconds | Observation |
| --- | ---: | ---: | ---: | --- |
| Buildup replay | 1,000 | n/a | 0.0028594 | 349,724 events/s |
| Buildup replay | 10,000 | n/a | 0.0255001 | 392,155 events/s |
| Buildup replay | 100,000 | n/a | 0.3149348 | 317,526 events/s |
| Full sale, four levels | 100,000 | 0.2471712 | 0.1437330 | 100,000 maker fills, four executed prices |
| Full sale, 1,000 levels | 100,000 | 0.2530663 | 0.1470448 | 100,000 maker fills, 1,000 executed prices |

The last two cases have identical quantities/arrival order and zero residual. They compare price
concentration within Revised, not a large-book cross-version speedup: Baseline did not complete.
These single-seed examples do not establish that every scaling ratio is stable.
In the anchored 100,000-pair churn case (200,002 actual events), Revised retained seven queue entries
before final cancellation (one live, six inactive) and one heap key; both structures were empty after.
Traced current bytes fell from 5,024 to 1,704, with a 10,816-byte peak. This is not total process memory.
The separate large-then-empty ID-table diagnostic retained 26,032 shallow dictionary bytes after all
1,000 orders were cancelled, confirming the capacity caveat above.

See results/phase1_final/coverage.md for the regenerated measured tables, comparisons and actual counts.
The replay audit confirms all available completed cross-batch diagnostic pairs; Revised-only completion
does not establish a cross-version correctness comparison. Historic Baseline stops remain valid stops.

Passive growth exposes Baseline's repeated list scans; crowded FIFO queues do not remove its ID-validation
scan. Revised's per-price queues and index avoid these scans, but allocate additional structures.
The supplied alternating-cancel stream keeps only one order live, so it cannot establish performance
for long cancellation queues. The controlled anchored stream maintains an old live head while younger
orders churn, and records retained queue/heap objects and memory before and after final cancellation.
Its generator is deterministic and does not use the seed, so its three seed labels are not three
independent random workloads. Concentration cases deliberately share their nonprice input fields.

profile_diagnostic.py runs a separate small cProfile and operation-count experiment. Unique passive
submissions perform B ID probes per Baseline insertion versus one indexed lookup in Revised:
1000 inserts imply 499500 list-ID comparisons versus 1000 dictionary lookups; 2000 imply
1999000 comparisons versus 2000 dictionary lookups. The dictionary counter measures get calls,
not internal hash-slot probes.
Matching scans are additional. Profile overhead and counters are never included in primary data.

Comparisons require full case identity, identical input hashes, compatible measured code/Python/machine/
limits and completed groups with matching diagnostics. Documentation/report changes do not imply a
change in measured engine code. Background load and thermals were not controlled; seed variation and
stylized order mix limit inference. Single-sale percentiles have only five observations per case.
No general claim that Revised always wins is made. Stopped values are not extrapolated into results.

The optional million-event mixed-workload limit probe is separate from mandatory coverage;
its decision, actual outcomes and declared limits are recorded in coverage.md and optional_audit.json.
It took 376.529 command-wall seconds: shared I/O and all four Revised phases completed, while all
four Baseline workers stopped. Revised replay median was 2.905142 seconds; the separate latency
median/P95/P99 were 2.700/6.400/11.100 microseconds. Peak traced allocation was 49,267,992 bytes and
the diagnostic active-order peak was 150,832. No million-event cross-version speedup or diagnostic
agreement is claimed. The input had 118,012,377 decoded bytes, within the unchanged 128 MiB cap.
No generated million-event file is included in the submission.

## AI assistance

Available code/history and the development conversation document accepted AI help with the ID index,
FIFO deques, heaps, lazy deletion, tests, benchmark orchestration and saved-data reporting.
Corrections included routing through book.process_event, distinguishing maker fills from executed
price levels, keeping integer units exact, and separating expected logical cancellation lookup from
total cleanup cost. Unqualified O(1) cancellation and completed-result claims from partial groups are
rejected by the implementation/reporting checks. Python availability was established by executing
the actual interpreter rather than assuming the editor supplied it.
AI assistance and agreeing implementations do not substitute for independent correctness evidence.

