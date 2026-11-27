"""The interface shared by both versions (written before either implementation).

Each version is a class with these methods. Events are dictionaries exactly as read from
the JSON Lines files (see the assignment README for the fields).

    process(event) -> result          event dispatcher: routes by "type", rejects unknown types
    add_limit_order(event) -> result  AddLimitOrder   (LIMIT events)
    cancel_order(event) -> result     CancelOrder     (CANCEL events)
    fill_market_sell(event) -> result FillMarketSell  (MARKET_SELL events)
    snapshot() -> {"bids": [...], "asks": [...]}      book inspection
    best_bid() / best_ask() -> price_ticks or None    None if that side is empty

The CamelCase names AddLimitOrder, CancelOrder and FillMarketSell are aliases of the
snake_case methods. Every public method validates its event; a rejected event changes
nothing, including the last accepted sequence number.

Result formats
--------------
Submission (LIMIT, MARKET_SELL):
    {"event_id", "order_id", "status", "unfilled_qty_units", "fills": [fill, ...]}
    LIMIT status: "filled" (nothing rests) or "resting" (residual rests in the book)
    MARKET_SELL status: "filled", "partial" or "unfilled"; the residual is discarded
Fill (in execution order):
    {"maker_id", "taker_id", "price_ticks", "qty_units"}   price = resting order's price
Cancellation:
    {"event_id", "target_order_id", "status": "cancelled" | "not_found", "cancelled_qty_units"}
Rejection:
    {"event_id": <id or None>, "status": "rejected", "reason": <text>}

Snapshot (canonical order, used to compare versions and expected books):
    bids sorted by decreasing price, then arrival; asks by increasing price, then arrival;
    each order {"order_id", "side", "price_ticks", "qty_units", "arrival_seq"}.
"""

STATUS_FILLED = "filled"
STATUS_RESTING = "resting"
STATUS_PARTIAL = "partial"
STATUS_UNFILLED = "unfilled"
STATUS_CANCELLED = "cancelled"
STATUS_NOT_FOUND = "not_found"
STATUS_REJECTED = "rejected"
