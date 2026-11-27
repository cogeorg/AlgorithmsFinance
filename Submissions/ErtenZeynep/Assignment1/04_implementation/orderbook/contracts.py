"""Public assignment contract constants shared by both order-book versions."""

EVENT_LIMIT = "LIMIT"
EVENT_MARKET_SELL = "MARKET_SELL"
EVENT_CANCEL = "CANCEL"

LIMIT_STATUSES = frozenset({"filled", "resting"})
MARKET_SELL_STATUSES = frozenset({"filled", "partial", "unfilled"})
CANCEL_STATUSES = frozenset({"cancelled", "not_found"})

FILL_FIELDS = frozenset({"maker_id", "taker_id", "price_ticks", "qty_units"})
SUBMISSION_RESULT_FIELDS = frozenset(
    {"event_id", "order_id", "fills", "status", "unfilled_qty_units"}
)
CANCEL_RESULT_FIELDS = frozenset(
    {"event_id", "target_order_id", "status", "cancelled_qty_units"}
)
SNAPSHOT_FIELDS = frozenset(
    {"order_id", "side", "price_ticks", "qty_units", "arrival_seq"}
)

