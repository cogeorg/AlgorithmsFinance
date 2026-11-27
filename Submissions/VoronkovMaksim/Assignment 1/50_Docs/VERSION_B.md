# Version B — Optimization Rationale and Design

Version A scans its list for duplicate IDs, cancellation and each maker. The earlier diagnostic found buildup median event latency rising from 48 µs in the first 10% to 1,431 µs in the last 10% of 10,000 events. Sweep took a 33.27 s median replay versus 0.030 s for cancellation churn; the workloads have different active depths and event mixes. A controlled cancellation near the end of a 1,000-order list took a 72.9 µs median versus 3.2 µs with 10 orders. These results motivate indexing; they do not measure Version B.

`orders_by_id` points to active order objects. Separate bid and ask dictionaries map exact prices to insertion-ordered dictionaries of the same objects. This preserves FIFO and lets a middle order be removed without scanning a deque. Heaps identify best prices; bid prices are negated so ordinary `heapq` min-heaps work on Python 3.11 as well as newer versions.

Completed and cancelled orders are removed immediately from both indices. Empty levels are deleted, while a price can remain in its heap until it reaches the root. A set tracks heap entries, so a recreated price reuses its stale entry rather than creating a duplicate. When a heap exceeds three times its side's active price-level count, it is rebuilt from active levels; an empty side therefore has an empty heap. This avoids retaining inactive individual orders and bounds the heap to at most three entries per active level after each event. A rebuild can make an individual operation slower.

## Expected costs

Let B be active orders, P active price levels, F fills, and K stale heap entries removed during an operation. Dictionary operations are expected/amortized, not guaranteed worst-case. The heap is bounded by 3P after each event. Rebuilding costs O(P); stale root cleanup costs O(K log P). Python's insertion-ordered dictionary can retain internal deleted slots: selecting the first live queue entry is not guaranteed O(1) worst-case after deletions.

| Operation | Version A | Version B |
|---|---|---|
| Duplicate-ID lookup | O(B) | Expected O(1) |
| Best-price discovery | O(B) scan | O(1) for a valid heap root, plus O(K log P) stale cleanup |
| First maker at best price | O(B) scan | First entry of price dictionary; may scan deleted internal slots |
| Cancellation | O(B) | Expected O(1) lookup/removal, with occasional O(P) heap rebuild |
| Market sell | O((F+1)B) worst-case | F queue selections and updates, plus heap insertion/removal and cleanup; O(K log P) cleanup and occasional O(P) rebuilds, with O(F) fill output |

These are theoretical expectations, not observed speedups. Rebuild work is amortized over accumulated stale entries, but a single operation can pay the rebuild cost. Inspection still sorts and copies B orders in O(B log B) time and O(B) space. Book storage is O(B + P), plus the current event's O(F) output, excluding Python dictionary allocation history.

## Verification and limitations

On 23 November 2026, `python -B -m unittest discover -s 30_Tests -p 'test_*.py'` ran **23 tests, all passed**. The unchanged tests exercised both versions, the worked example, and event-by-event comparison on five small generated streams. Four additional tests cover middle-of-queue cancellation, a stale best price, removal and recreation of prices on both sides, and bounded heap size under cancellation churn. Instructor-file hashes matched the original manifest.

The assignment does not specify identifier types. Initial testing identified a difference: Version B's dictionary index rejected unhashable identifiers while Version A accepted some of them. Both versions now use the same project-specific policy for `event_id`, `order_id`, and `target_order_id`: accept nonempty strings and integers (including zero and negative values); reject empty strings, Booleans, floats, `None`, lists, dictionaries and other types. Explicit type checks keep Booleans separate from integers, and integer `123` remains distinct from string `"123"`. This is a project decision, not a requirement stated in the assignment. Matching and Version B's data structures and cleanup logic were unchanged.

On 23 November 2026, four new identifier test methods were first run before the change and produced 60 failing subtests across both versions. After the change, the complete suite ran 27 tests, all passed, including the worked example, event-by-event comparison, identifier checks, and instructor-file manifest verification. Direct `AddLimitOrder`, `CancelOrder`, and `FillMarketSell` calls assume prior validation; use `process_event` as the event interface. Earlier performance measurements describe the code versions recorded by their source hashes, before this validation change; no new benchmark was run.

## Version B-specific insertion and matching pseudocode

```text
ADD LIMIT: validate fields and look up duplicate order ID in the ID dictionary
    match eligible opposite prices as below
    if a residual remains:
        if its exact price level is absent:
            create an insertion-ordered dictionary for that price
            if no heap entry exists for the price, push its signed price to the heap
        append the residual order to that price dictionary and index it by ID
MATCH: clean stale heap roots; read the best opposite price
    while the price crosses and quantity remains:
        select the earliest order at that exact price
        execute at maker price and update both quantities
        immediately remove exhausted maker from ID and price dictionaries
        delete an empty level; rebuild its heap when stale entries exceed the policy
        clean stale roots and select the next best price
CANCEL: find ID in the index; remove its remaining order from both dictionaries
    delete an empty level and rebuild the heap if the threshold is exceeded
MARKET SELL: use MATCH against bid prices without a limit; discard any residual
```

For a non-crossing residual, duplicate-ID validation and insertion into an existing price level are expected O(1) dictionary operations. Creating a new level requires an expected O(1) dictionary insertion and O(log P) heap push when a heap entry is not already retained; a reappearing price with an existing stale entry avoids that push. Finding the opposite best price may also remove K stale roots in O(K log P). A crossing limit additionally pays the work of its F fills, output construction, price cleanup, and any O(P) heap rebuild. These are expected/amortized dictionary claims; a rebuild or stale cleanup can make an individual event slower, and ordered-dictionary iteration can encounter deleted slots.

