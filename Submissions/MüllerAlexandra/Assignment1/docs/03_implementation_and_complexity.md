# Implementation and complexity

Let `B` be active individual orders, `P` occupied price levels, `M` incoming
events in a replay, and `F` maker fills produced by one incoming event. Version
A stores a single Python list of `B` mutable `RestingOrder` values. Replay cost
is the sum of the `M` individual event costs; `M` does not determine `B` or
`F`, so an event-count-only bound would hide the workload-dependent costs.

## Baseline operations

### Validation

The baseline constructs the set of active identifiers before every event.
That costs `O(B)` time and `O(B)` temporary space. Field checks are constant
after that construction.

### Resting insertion

Appending a noncrossing residual is amortized `O(1)`, but the dispatcher has
already paid the `O(B)` validation cost. Finding eligible makers scans all
active orders. If `K <= B` makers are eligible, sorting them costs
`O(K log K)` time and `O(K)` temporary space.

### Matching and market selling

Each fill update is constant work, but removing an exhausted maker from the
middle of the list costs `O(B)` because later references shift. Consequently,
the directly implemented worst-case matching cost is

```text
O(B + K log K + F B)
```

including validation, candidate construction, sorting, state updates, and
fill-list construction. The returned `F` fill records are required output,
not auxiliary space. Candidate storage and active-identifier validation use
`O(B)` temporary space.

### Cancellation

Cancellation scans for the target and removes it from the list, so it is
`O(B)` time and `O(B)` temporary space including the shared validation set.

### Inspection

Canonical inspection sorts bids and asks, requiring `O(B log B)` time and
`O(B)` returned output plus sorting workspace.

## Version B: indexed price levels

Version B keeps three synchronized views of the active book:

- a dictionary from active order identifier to its `RestingOrder`;
- for each side, a dictionary from price to an `OrderedDict` FIFO queue; and
- for each side, a strictly increasing list of occupied prices.

The same `RestingOrder` object is referenced by the identifier dictionary and
exactly one price queue. The sorted price lists use `bisect`; no matching-engine
package or heap is used.

### Revised resting insertion pseudocode

```text
validate using the active-order dictionary keys
while the residual crosses the best opposite price:
    take the oldest maker from that price's FIFO queue
    fill min(residual, maker remainder) at the maker price
    reduce both remainders
    if the maker is exhausted:
        delete it from the FIFO queue and identifier dictionary
        if its price level is empty, delete the level and sorted price entry
if a limit residual remains:
    create its price level and sorted price entry if necessary
    append it to that level's FIFO queue and identifier dictionary
```

### Revised cancellation pseudocode

```text
look up and remove target_order_id in the active-order dictionary
if absent, return not_found
delete the same identifier from its side-and-price FIFO queue
if the queue is empty, delete its level and sorted price entry
return the removed order's residual quantity
```

### Revised market-selling pseudocode

```text
while quantity remains and a bid price exists:
    select the highest occupied bid price
    take the oldest maker from that price's FIFO queue
    fill min(seller remainder, maker remainder) at the maker price
    reduce both remainders
    delete an exhausted maker from both indexes
    delete an empty price level and sorted price entry
return the unmatched market quantity without resting it
```

### Revised complexity

Dictionary and `OrderedDict` operations below are expected `O(1)` under
Python's hashing model. Validation membership checks no longer build an
`O(B)` temporary set.

- Resting at an existing price is expected `O(1)`. Creating a new price is
  `O(P)` because insertion may shift the sorted Python list.
- Cancellation is expected `O(1)` unless it empties a level; removing that
  price from the sorted list is `O(P)`.
- Reading the best bid or ask is `O(1)`, and taking the oldest maker is
  expected `O(1)`.
- For an event producing `F` fills and emptying `L` price levels, matching is
  expected `O(F + L P)`, plus `O(P)` if a residual creates a new level. Here
  `L <= min(F, P)`. Unlike Version A, this bound has no scan of all `B` active
  orders and no `O(B)` shift for each exhausted maker.
- Canonical inspection is `O(B + P)` time and `O(B)` returned output because
  prices and FIFO queues are already ordered.
- Persistent auxiliary state is `O(B + P)`. A live order has references in
  two indexes, but cancelled and executed orders leave both; there are no
  stale heap entries that can grow with event history.

This organization deliberately trades potentially linear `O(P)` shifts on
price-level creation/removal for fast operations within occupied levels. Its
effect is a measurement question; the complexity argument alone is not a
performance result.
