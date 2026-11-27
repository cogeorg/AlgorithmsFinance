# Specification and model

## Scope

This project implements a sequential limit order book for one synthetic BTC
venue. An event is processed completely before the next event begins. The book
contains individual visible resting orders and applies price-time priority.
Assignment 1 is authoritative if this summary and the supplied contract ever
appear to differ.

The two submitted implementations expose the same public operations:

- `process_event(event)` dispatches one event;
- `add_limit_order(event)` processes a limit order;
- `cancel_order(event)` cancels an active residual, if present;
- `fill_market_sell(event)` processes a market sell; and
- `inspect_book()` returns the current canonical book.

## Integer units

- `price_ticks` is a positive integer number of cents per BTC. One tick is
  USD 0.01 per BTC.
- `qty_units` is a positive integer number of satoshis. One unit is
  0.00000001 BTC, so 100,000,000 units equal one BTC.
- A fill at price `p` and quantity `q` contributes `p * q` integer
  tick-times-quantity units to gross proceeds. Dividing the total by
  10,000,000,000 converts it to US dollars.

Matching and conservation use integers. Rounding is only a display concern.

## Event order and identifiers

Every event has `seq`, `event_id`, and `type`. An accepted sequence number is a
strictly increasing positive integer. It defines arrival priority; identifier
spelling never defines priority. A rejected event does not advance the last
accepted sequence.

Valid supplied submission `order_id` values are globally unique. The engine
directly rejects reuse of a currently active submission identifier. Historical
reuse after an order has left the book is outside the assignment contract.

## Event types

### Limit order

A `LIMIT` event additionally has `order_id`, `side`, `price_ticks`, and
`qty_units`. `side` is `BUY` or `SELL`.

- A buy crosses while its limit is at least the lowest resting ask.
- A sell crosses while its limit is at most the highest resting bid.
- Matching takes the best opposite price first and then the oldest maker at
  that price.
- Every fill executes at the resting maker's price for the smaller of the
  incoming and resting residual quantities.
- An exhausted maker is removed. A partially filled maker retains its original
  queue position.
- A positive noncrossing incoming residual rests at its limit behind earlier
  orders at that price, using its original `seq` as arrival rank.

### Market sell

A `MARKET_SELL` event additionally has `order_id` and `qty_units`. It consumes
the highest bid first, then lower bids, preserving FIFO within each price. It
mutates the live book. Any unfilled market quantity is returned in the result
and discarded; it never rests.

### Cancellation

A `CANCEL` event additionally has `target_order_id`. Cancelling an active order
removes exactly its remaining quantity. Cancelling an unknown, already filled,
or already cancelled target is a valid no-op with status `not_found`.

## Results

Fills are returned in execution order. Every fill contains `maker_id`,
`taker_id`, `price_ticks`, and `qty_units`.

A limit or market submission result includes `event_id`, incoming `order_id`,
`status`, `unfilled_qty_units`, and only the current event's fills. A limit is
`filled` when no residual rests and otherwise `resting`. A market sell is
`filled`, `partial`, or `unfilled` according to its executed quantity.

A cancellation result includes `event_id`, `target_order_id`, status
`cancelled` or `not_found`, and `cancelled_qty_units`. A rejected result
includes `event_id` when available, status `rejected`, and a reason.

## Validation and state atomicity

Unknown event types or sides, missing required fields, noninteger or
nonpositive prices and quantities, Boolean values where integers are required,
duplicate live submission identifiers, and nonincreasing sequences are
rejected. Rejection leaves every observable book field unchanged.

After every accepted event:

1. every active identifier appears exactly once;
2. every resting quantity is positive;
3. bids are strictly below asks whenever both sides are nonempty;
4. price priority and FIFO priority hold;
5. incoming quantity equals fills plus its returned or resting residual; and
6. a maker loses exactly its fills, while cancellation removes exactly its
   remaining residual.

## Canonical inspection

`inspect_book()` returns active orders with `order_id`, `side`, `price_ticks`,
remaining `qty_units`, and original `arrival_seq`. Bids are ordered by
decreasing price then increasing arrival sequence. Asks are ordered by
increasing price then increasing arrival sequence.

## Modeling boundaries

There are no fees, balances, hidden orders, self-trade checks, multiple venues,
network or queueing delay, simultaneous events, strategic agents, or historical
market calibration. Synthetic sequence numbers are ordering keys, not elapsed
time. The measurements describe Python processing of teaching workloads on one
machine; they do not establish production exchange capacity or real-time
overload behavior.

