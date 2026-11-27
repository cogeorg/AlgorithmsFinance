# Assignment 1 frozen contract

This contract is fixed before implementation. Both preserved implementations
must satisfy the same tests and return the same observable results.

## Public classes and methods

The package will provide:

- `orderbook.baseline.BaselineOrderBook`
- `orderbook.revised.RevisedOrderBook`

Each class has an empty constructor and these public methods:

```python
ProcessEvent(event: Mapping[str, object]) -> dict[str, object]
AddLimitOrder(event: Mapping[str, object]) -> dict[str, object]
CancelOrder(event: Mapping[str, object]) -> dict[str, object]
FillMarketSell(event: Mapping[str, object]) -> dict[str, object]
InspectBook() -> list[dict[str, object]]
```

`ProcessEvent` is the normal entry point and dispatches by `type`. Direct calls
to the three operation methods use the same validation and result schema, but
each accepts only its named event type: `AddLimitOrder` accepts `LIMIT`,
`CancelOrder` accepts `CANCEL`, and `FillMarketSell` accepts `MARKET_SELL`.
After normal validation, a valid event of the wrong type is rejected with
`wrong_event_type_for_method`; it does not mutate state or advance the accepted
sequence. The read-only `last_accepted_seq` property is `None` on an empty book
and otherwise contains the most recent accepted event sequence. No method
mutates the input mapping.

## Integer units and ordering

- `price_ticks` is a positive integer number of USD cents per BTC.
- `qty_units` is a positive integer number of `0.00000001 BTC` units.
- `seq` is a positive, strictly increasing integer arrival rank.
- `bool` is rejected wherever an integer is required.
- Matching uses best price first, then the smallest original `seq` at that
  price. Identifier spelling never determines priority.
- Trades execute at the resting maker's price.
- A partially filled maker keeps its original arrival rank.

## Accepted input events

Every accepted event has a nonempty string `event_id`, an integer `seq`, and
at least the following required fields:

```text
LIMIT:
  type, event_id, seq, order_id, side, price_ticks, qty_units

MARKET_SELL:
  type, event_id, seq, order_id, qty_units

CANCEL:
  type, event_id, seq, target_order_id
```

Additional fields are permitted and ignored. They do not affect validation,
matching, state, or returned results, and the input mapping remains unchanged.

`side` is exactly `BUY` or `SELL`. Submission and target identifiers are
nonempty strings. A limit or market submission whose `order_id` equals an
active resting order is rejected as `duplicate_live_order_id`. Historical
identifier reuse after an order leaves the book is outside the required model;
the supplied valid streams use globally unique identifiers.

Cancellation of an unknown, filled, or previously cancelled target is a valid
accepted event with status `not_found`; it advances `last_accepted_seq`.

## Validation and atomic rejection

The whole event is validated before any state change. Rejected events do not
change the book, active-order index, price levels, or `last_accepted_seq`.
They return a stable reason from this list:

- `event_must_be_mapping`
- `missing_event_id`
- `invalid_event_id`
- `missing_seq`
- `invalid_seq`
- `nonincreasing_seq`
- `missing_type`
- `unknown_event_type`
- `wrong_event_type_for_method`
- `missing_order_id`
- `invalid_order_id`
- `duplicate_live_order_id`
- `missing_side`
- `invalid_side`
- `missing_price_ticks`
- `invalid_price_ticks`
- `missing_qty_units`
- `invalid_qty_units`
- `missing_target_order_id`
- `invalid_target_order_id`

If more than one field is invalid, validation follows this order: mapping,
`event_id`, `seq`, `type`, then type-specific fields in the order shown above.

## Matching behavior

An incoming limit buy matches asks while its price is greater than or equal to
the best ask. An incoming limit sell matches bids while its price is less than
or equal to the best bid. Any positive limit residual rests at its own price
behind earlier orders there.

A market sell consumes the highest bid first, then lower bids, with FIFO at
each price. Its residual is reported and discarded. It never rests.

An exhausted maker is removed from its price queue and active-order index. A
cancelled active maker loses exactly its remaining quantity; empty price levels
are removed.

## Result schemas

Every fill is a dictionary with this exact field set:

```json
{"maker_id":"b1","taker_id":"s1","price_ticks":6000000,"qty_units":100000000}
```

Fills appear in execution order.

A valid limit result contains exactly:

```text
event_id, order_id, status, unfilled_qty_units, fills
```

Its status is `filled` when no incoming quantity rests and `resting` otherwise.
For a resting limit, `unfilled_qty_units` is the residual placed on the book.

A valid market-sell result has the same fields. Status is `filled` when fully
executed, `partial` when some but not all quantity executes, and `unfilled`
when no quantity executes. `unfilled_qty_units` is discarded market residual.

A valid cancellation result contains exactly:

```text
event_id, target_order_id, status, cancelled_qty_units
```

Status is `cancelled` or `not_found`; `not_found` has zero cancelled quantity.

A rejection contains `event_id` when it is available and valid, plus exactly:

```text
status="rejected", reason=<stable reason above>
```

## Canonical inspection

`InspectBook` returns a new list of active-order dictionaries with exactly:

```text
order_id, side, price_ticks, qty_units, arrival_seq
```

Bids come first, sorted by decreasing price then increasing arrival sequence.
Asks follow, sorted by increasing price then increasing arrival sequence. The
returned list and dictionaries do not expose mutable internal containers.

The implementation retains no historical fill list. Each result contains only
the current event's fills.

## Required invariants

After every accepted event:

1. No resting bid crosses the best resting ask.
2. Every resting quantity is positive.
3. Every active order occurs exactly once in the book and active-order index.
4. FIFO order agrees with original arrival sequence at every price.
5. Incoming quantity equals executed quantity plus reported residual.
6. A maker loses exactly its executed quantity.
7. Cancellation removes exactly the maker's remaining quantity.
8. Gross proceeds equal `sum(price_ticks * qty_units)` over ordered fills.

Integers are used for every matching and conservation calculation. Decimal
formatting is display-only.
