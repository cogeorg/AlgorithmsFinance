# Short report

## 1. Specification and model boundary

The engine processes one strictly ordered event stream for one synthetic BTC venue.
Prices are positive integer cents per BTC; quantities are positive integer units of
10^-8 BTC. Limit orders use continuous matching at resting maker prices. Better
prices execute before worse prices, and orders at one price execute by original
arrival sequence. A market sell consumes bids and never rests a residual.

The model excludes fees, balances, hidden liquidity, self-trade prevention, network
delay, simultaneous execution, strategic behavior, and multi-venue liquidity. The
results therefore describe an algorithmic teaching model, not production capacity.

## 2. Correctness reasoning

After every accepted event:

1. every active order has positive remaining quantity and appears exactly once;
2. the highest resting bid is below the lowest resting ask;
3. a price queue remains in arrival order, including after a partial fill;
4. each fill removes exactly its quantity from the incoming and maker residuals;
5. a cancellation removes exactly the target's remaining quantity;
6. a market residual is returned but never stored.

The matching loop chooses the best eligible price and then the earliest maker at
that price. A fill either exhausts the incoming order or reduces/removes that maker.
Thus each iteration makes progress and the finite active book guarantees termination.
If the loop stops, no eligible maker remains. Independent expected-result tests cover
empty books, boundary quantities, multiple prices, FIFO, partial fills, cancellation,
crossing limits, invalid events, and long queues. The two versions are also compared
after every event in generated streams; this comparison supplements rather than
replaces independent expectations.

## 3. Implementations and complexity

Let `B` be the active-order count, `P` the occupied price-level count, `M` incoming
events, and `F` makers filled by one incoming order.

### Version A: unsorted lists

- A noncrossing insertion appends in O(1), after an O(B) live-ID validation scan.
- Cancellation scans active orders: O(B).
- Every next-maker selection scans one whole side, and exhausted-order removal can
  also scan: market selling is O(FB) in the worst case.
- Active storage is O(B); canonical inspection sorts in O(B log B).

### Version B: ID index, price levels, FIFO queues

- Live-ID validation and lookup are expected O(1) using a dictionary.
- Adding at an existing price is expected O(1). A new price is inserted into a sorted
  price list in O(P).
- Cancellation is expected O(1) unless it removes the last order at a price, when
  removing that price from the sorted list is O(P).
- Selecting the best maker and advancing within one queue are O(1). A sell touching
  `F` makers and removing `L` levels costs O(F + LP) in the shown list-based price
  index; this is still materially better than rescanning all `B` orders per fill.
- Active storage is O(B + P).

The chosen Version B avoids lazy deleted orders, so cancellation churn does not leave
an unbounded stale heap or queue. The trade-off is extra dictionary/queue overhead and
O(P) insertion/removal when a price level is created or destroyed.

## 4. Measurement design

Inputs are generated before timing. Every replay starts from a fresh empty book,
uses `time.perf_counter`, follows an untimed warm-up, keeps five raw repeats, and
reports their median. Primary timing excludes validation tests, printing, profiling,
dashboard work, heavy counters, and memory tracing. Instrumented latency and operation
counts run separately. Per-event p95 and p99 use nearest-rank percentiles.

`tracemalloc` runs separately and excludes the pre-generated event list. It includes
the live book and current returned event result but does not retain full fill history.
The measurement is traced Python allocation, not total process memory or theoretical
auxiliary space.

The five workload families isolate active-book growth, queue concentration, mixed
flow, depth sweeping, and cancellation churn. Fixed-book liquidations independently
sell 10%, 100%, and 200% of available bid quantity from a fresh book and report
construction separately from matching.

## 5. Measured revision effect and bottleneck

Version A is expected to spend increasing time in repeated best-maker scans as the
active book and fill count grow. Version B removes those scans by indexing IDs and
grouping FIFO orders by price. It may not win for very small books because its
dictionaries and ordered queues have larger constant costs and memory overhead.
Saved operation counts (`maker_scans`, fills, and visited prices) connect observed
timing to this explanation. The dashboard must be interpreted together with the raw
repeats and stopped-run labels; empirical agreement supports but does not prove the
complexity claims.

For the mixed workload with M = 10,000 and seed 42, Version A processed 8,810.05
events per second, while Version B processed 269,382.95 events per second, giving a
median replay speedup of 30.58x. The instrumented p95 processing latency was 699.33
microseconds for Version A and 8.50 microseconds for Version B. Both versions
produced 3,926 fills and recorded 3,853 price-level visits, but Version A performed
2,794,748 maker scans while Version B performed none. This supports the predicted
list-scanning bottleneck. The revision used more peak traced allocation: 0.74 MiB
versus 0.26 MiB, showing the memory-for-speed trade-off of the added indexes.

A separate latency run classified events and compared the first and last 10% of each
stream. For mixed M = 10,000, Version A's median rose from 8.605 microseconds early
to 100.833 microseconds late; Version B remained nearly flat at 3.542 and 3.583
microseconds. In buildup, Version A rose from 89.854 to 1,660.938 microseconds,
whereas Version B changed from 4.042 to 3.917 microseconds. For mixed Version B,
median latencies were 1.459 microseconds for cancellation, 3.709 for limit orders,
and 3.833 for market sells. These are engine-processing measurements, not network or
queueing latency.

In the fixed-book experiment, 2,000 initial bids were distributed over either 4 or
1,000 available prices. With four prices, a 10% sale filled 192 makers while visiting
one price level. With 1,000 available prices, 855 were occupied for seed 42 and the
10% sale filled 194 makers across 86 price levels. A 100% sale filled all 2,000 makers
and left no residual in both settings; a 200% sale filled the available book and
returned the original book quantity as unfilled. These results confirm quantity
conservation and show how queue concentration changes price-level work.

## 6. Limitations

The generator is stylized and not calibrated to an exchange. Sequential replay omits
network and queueing delay and cannot establish live overload capacity. Python object
overheads and interpreter behavior affect measured constants. The sorted-list price
index is appropriate for the supplied range but is not a claim of a production-optimal
matching engine. One-million-event runs were not attempted under the declared
three-second per-replay limit and available assignment time; no missing result is
extrapolated or imputed.
