# Baseline interface

`orderbook.baseline.OrderBook` and `orderbook.revised.OrderBook` implement the
same event interface. Create an instance for a fresh book. The public
operations accept one event mapping each; `process_event(event)` dispatches to
the corresponding operation. Both implementations apply the same validation
and sequence rules.

## Event processing

Call `OrderBook.process_event(event)` once per event. `event` is a mapping with
the fields for one `LIMIT`, `MARKET_SELL`, or `CANCEL` event described in the
assignment README. The method returns a mapping:

- Every submission result contains `event_id`, `order_id`, `status`,
  `unfilled_qty_units`, and `fills`.
- A limit submission uses `filled` when no quantity rests and `resting`
  otherwise.
- A market sell uses `filled`, `partial`, or `unfilled`; any unfilled market
  quantity is discarded rather than resting.
- A cancellation result contains `event_id`, `target_order_id`, `status`, and
  `cancelled_qty_units`; its status is `cancelled` or `not_found`.
- A rejection contains `status: "rejected"`, a reason, and `event_id` when
  available.
- Each fill contains `maker_id`, `taker_id`, `price_ticks`, and `qty_units`.
  Fills are ordered by execution and use the resting maker's price.
- A valid `CANCEL` of an unknown or inactive target returns `not_found` and
  advances the accepted sequence. A rejection changes neither the book nor
  that sequence.

The explicit operation methods are `AddLimitOrder(event)`,
`CancelOrder(event)`, and `FillMarketSell(event)`. The accepted event schema
and result fields are the same whether an event is passed directly to one of
these methods or to `process_event`.

## Book inspection

`OrderBook.inspect_book()` returns active orders only, grouped as
`{"bids": [...], "asks": [...]}`. Each order contains `order_id`, `side`,
`price_ticks`, `qty_units` (remaining quantity), and `seq` (original arrival
sequence). Bids are ordered by decreasing price and then arrival sequence;
asks are ordered by increasing price and then arrival sequence.

`OrderBook.last_accepted_seq` is a read-only observation property for tests and
diagnostics. It returns the most recent accepted event sequence, or `None`
before any event has been accepted. Rejected events do not change it.
