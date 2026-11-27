# Version B revision design

## Bottleneck and chosen organization

Version A scans active orders to find duplicate submission IDs and eligible
makers. It sorts candidate makers for every match, and each exhausted maker
requires a linear-time list removal. Version B replaces these scans with an
active-ID dictionary, FIFO `OrderedDict` queues grouped by side and price, and
standard-library heaps for best-price selection. It does not subclass Version
A and retains no order or trade history.

## Bounded lazy heap cleanup policy

Each side has a price heap and a companion set containing exactly the encoded
heap values physically present (including stale values). Bid heap values are
negative prices, so the minimum is the highest bid; ask values are positive
prices, so the minimum is the lowest ask.

When a price queue becomes empty, remove it from the side's price dictionary
but leave its heap value in place. Do not push another value for a price
already in the membership set. Thus a price reactivated while its stale value
is buried in the heap reuses that one value; it cannot create duplicates. When
a stale value reaches the heap top, pop it and remove it from the set. If a
side becomes empty, clear both its heap and membership set immediately.

After deleting a price queue, rebuild that side's heap from its active price
keys with `heapify` whenever its physical heap size `H` exceeds `2*P + 32`,
where `P` is its active price-level count. Rebuild also recreates the
membership set from those keys. This keeps `H <= 2*P + 32` after each
operation, bounds stale storage even when another price remains active, and
handles later reactivation without duplicate entries. The small allowance
avoids rebuilding for a few stale entries. Cleanup can make an individual
deletion expensive; its cost is documented below rather than claimed as
worst-case constant time.

## Pseudocode and invariants

```text
AddLimitOrder(event):
    validate event and check order_id in active-ID dictionary
    while incoming quantity remains:
        discard stale heap tops; read best maker price
        stop if no price or the best price does not cross the limit
        take the first maker from that price's OrderedDict
        emit a maker-price fill and update its remaining quantity
        if exhausted, delete it from the queue and ID dictionary
        if its queue is empty, delete the price and apply heap cleanup
    if limit residual remains, append it to its FIFO price queue and ID index
    advance accepted seq and return this event's fills and residual

FillMarketSell(event):
    validate event and check order_id in active-ID dictionary
    consume the best bid queues in the same manner, without a price limit
    discard any residual; advance accepted seq and return its fills

CancelOrder(event):
    validate event; look up target in active-ID dictionary
    if found, delete it from both the ID index and its price queue
    if that queue empties, delete the level and apply heap cleanup
    return cancelled or not_found; advance accepted seq
```

- Every active ID maps to exactly one order object, and the same order object
  is present under its ID in exactly one side/price queue.
- Each `OrderedDict` retains arrival order. Partial fills mutate the order's
  quantity without removing or reinserting its key.
- Every active price level has exactly one encoded value in its side's heap
  and membership set. A stale value may remain for an empty level; membership
  prevents a duplicate if that price is reactivated.
- The heaps determine only best-price selection; queue order determines FIFO
  within a price. All fills are at maker prices.
- A rejected event changes neither active storage nor `last_accepted_seq`.
  Accepted unknown-target cancellation advances the sequence.

## Actual operation and space costs

Let `B` be active orders across both sides, `P` the active price levels on the
side being operated on, `H` its physical heap size, `F` the number of maker
fills returned by an event, `E` the number of exhausted makers, `S` the stale
heap values popped while finding the best price, and `R` the number of heap
rebuilds during an operation. The cleanup policy bounds each side by
`H <= 2*P + 32` after an operation. Expected dictionary and set costs assume
ordinary hash behavior; identifier copying/output cost additionally depends
on identifier payload size.

- Validation and duplicate-live-ID checking use dictionary membership:
  expected `O(1)` for the ID check rather than a scan of `B`.
- A noncrossing insertion adds one ID-index entry and one queue entry in
  expected `O(1)`. A new physical price entry uses `heappush`, `O(log H)`;
  a reactivated price whose stale entry remains does not push a duplicate.
- Cancellation uses expected `O(1)` ID lookup and expected `O(1)` deletion
  from the ID dictionary and `OrderedDict`. If that was the level's last
  order, deleting the price level is expected `O(1)` and invokes the cleanup
  policy. A cancellation that triggers rebuilding costs `O(P + H)`; it is
  not claimed to be worst-case `O(1)`.
- Matching advances through FIFO queue heads rather than scanning active
  orders. Each of `F` fills takes expected `O(1)` queue/index operations and
  allocates one output record. Exhausted makers incur expected `O(1)` index
  and queue deletion, with at most `E` emptied-level cleanup checks.
  Stale-top removal costs `O(S log H)`. A limit insertion may also pay for
  insertion of its residual.
- Each rebuild creates a list from the active `P` prices, heapifies it, and
  rebuilds the membership set: `O(P + H)` time and `O(P)` temporary space.
  The threshold bounds `H` before the rebuild, but an individual triggering
  cancellation or matching event can still incur this cleanup cost. Stale
  values popped from the heap are each removed once. No global amortized
  worst-case `O(1)` cancellation claim is made.
- Inspection sorts the active price keys and visits each order once:
  `O(P log P + B)` time, plus `O(B)` returned copies and `O(P)` sort storage.

Persistent storage is `O(B + P + H)` for the ID index, orders/queue entries,
price levels, heaps, and membership sets; under the policy this is
`O(B + P)` per book. A matching event allocates `O(F)` fill records.
Inspection allocates `O(B)` returned order records. Neither version retains
historical orders or trade history.

## AI assistance

AI assistance was used to implement Version B, add its regression and parity
tests, and document the design. The cleanup threshold is an explicit design
choice. The specification tests passed for both versions, but performance
improvement remains unmeasured until the benchmark work is run.
