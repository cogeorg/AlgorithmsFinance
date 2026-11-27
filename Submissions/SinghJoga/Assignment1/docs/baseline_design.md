# Version A design

## Representation and scope

`OrderBook` stores a Python list of dictionaries, one per currently active
resting order. Each dictionary contains `order_id`, `side`, `price_ticks`,
remaining `qty_units`, and original `seq`. Filled and cancelled orders are
removed. The engine retains neither historical orders nor trade history;
fills are returned only with the event that caused them.

This is a sequential, single-venue continuous order book. All orders are
eligible; there are no fees, account balances, hidden orders, self-trade
checks, network delays, or simultaneous executions. The synthetic events
represent one venue, not combined exchange liquidity. This is an assignment
model, not a production trading system.

## Operation pseudocode

```text
process_event(event):
    select LIMIT, MARKET_SELL, or CANCEL operation from event.type
    reject unknown type

AddLimitOrder(event):
    validate every required field, positive integer values (excluding bool),
        increasing seq, side, and absence of a duplicate live submission ID
    reject without mutation if validation fails
    find and sort eligible opposite-side active orders by best price, then seq
    fill in that order at each maker's price, reducing maker quantities
    remove exhausted makers; preserve the seq of partial makers
    append any positive incoming residual as a resting order
    advance last_accepted_seq and return this event's fills and residual

FillMarketSell(event):
    validate every required field, positive integer values (excluding bool),
        increasing seq, and absence of a duplicate live submission ID
    reject without mutation if validation fails
    find and sort active bids by decreasing price, then seq
    fill in that order at maker prices; remove exhausted makers
    discard any incoming residual
    advance last_accepted_seq and return this event's fills and residual

CancelOrder(event):
    validate required fields and increasing positive integer seq
    reject without mutation if validation fails
    scan active orders for target ID
    remove its remaining quantity if found; otherwise return not_found
    advance last_accepted_seq and return cancellation result
```

Validation completes before matching or cancellation mutates the book. A
rejected event therefore preserves both the active orders and
`last_accepted_seq`. A valid `not_found` cancellation is accepted and advances
the sequence.

## Invariants

- At each price, eligible makers are processed in increasing original `seq`;
  across prices, the best eligible price is processed first.
- A fill quantity is the minimum of the taker's remaining quantity and the
  maker's remaining quantity, and its price is the maker's resting price.
- A partially filled maker retains its original `seq`; exhausted makers leave
  the active list.
- For a submission, incoming quantity equals the sum of its fills plus its
  returned residual. A limit residual is active; a market residual is
  discarded.
- Cancellation removes exactly the active target's remaining quantity.
- The engine stores only active orders. The test suite checks canonical books,
  positive resting quantities, unique active IDs, and lack of crossed resting
  prices in representative event streams.

## Costs of this implementation

Let `B` be the number of active orders before an event, `C` the eligible
opposite-side candidates, `F` the number of maker fills, and `E` the number of
exhausted makers removed. The following counts are for the actual list-based
code; they omit the size of identifier payloads and treat their equality and
copy operations as constant-time.

- A new submission's live-ID check scans the active list: `O(B)`.
- Matching scans the list to select candidates: `O(B)`, then sorts the `C`
  references: `O(C log C)`. Fill creation and quantity updates cost `O(F)`.
- Each exhausted maker is removed with `list.remove`, which scans/shifts the
  list and is `O(B)`, not constant-time. With `E` removals this adds
  `O(E B)`. Since `E <= F <= B`, matching is bounded by
  `O(B + C log C + F + E B)`, or `O(B log B + B F)` in the worst case.
  Many exhausted makers can make this quadratic in `B`.
- A cancellation scans for its target and removes it from the list, both
  `O(B)`, for `O(B)` total.
- Appending a limit residual is amortized `O(1)`; a new submission still pays
  its duplicate scan and matching work.
- Inspection sorts bids and asks into canonical order and copies each active
  order: `O(B log B)` time and `O(B)` returned space.

Persistent engine space is `O(B)`. Matching temporarily holds up to `O(B)`
candidate references and creates `O(F)` fill records for the current event.
Inspection additionally allocates `O(B)` copies. No historical-order or
trade-history storage is retained.

## Supplied worked-example trace

The first five events rest bids `b1` and `b2` at 6,000,000 ticks (100,000,000
units each), `b3` at 5,990,000 ticks (300,000,000 units), `b4` at 5,970,000
ticks (500,000,000 units), and ask `a1` at 6,010,000 ticks (200,000,000 units).
The sixth event sells 600,000,000 units. The market sell consumes `b1`, `b2`,
and `b3` fully, then 100,000,000 units from `b4`. It returns fills in that
order; `b4` remains with 400,000,000 units and its original sequence 4. Ask
`a1` is unchanged. The result is `filled` with no residual.

Gross proceeds are the integer sum
`6,000,000*100,000,000 + 6,000,000*100,000,000 +
5,990,000*300,000,000 + 5,970,000*100,000,000`
`= 3,594,000,000,000,000` tick-times-quantity units, or `$359,400.00`.
This matches the supplied expected result.

## AI assistance

AI assistance was used to implement Version A and draft this design and
interface documentation. The supplied expected worked-example output and
literal test expectations were treated as independent checks. The complete
66-test suite passed; no benchmark or speedup claim has been made.
