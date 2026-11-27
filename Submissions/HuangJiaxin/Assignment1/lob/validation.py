"""Event validation shared by both versions, so that both reject exactly the same events.

`check(event, last_seq, is_live)` returns None for a valid event, otherwise a reason.
`is_live(order_id)` must say whether that identifier belongs to an active resting order.
Cost: O(1) plus the cost of `is_live` (O(B) scan in version A, O(1) dict lookup in B).
"""

TYPES = {"LIMIT", "MARKET_SELL", "CANCEL"}
SIDES = {"BUY", "SELL"}


def _is_int(x):
    # bool is a subclass of int in Python; True must not count as quantity 1
    return isinstance(x, int) and not isinstance(x, bool)


def _positive_int(x):
    return _is_int(x) and x > 0


def check(event, last_seq, is_live):
    if not isinstance(event, dict):
        return "event is not an object"
    if not isinstance(event.get("event_id"), str):
        return "missing or invalid event_id"
    seq = event.get("seq")
    if not _positive_int(seq):
        return "seq must be a positive integer"
    if last_seq is not None and seq <= last_seq:
        return f"seq {seq} is not greater than the last accepted seq {last_seq}"
    kind = event.get("type")
    if not isinstance(kind, str) or kind not in TYPES:     # a JSON list is unhashable
        return f"unknown event type {kind!r}"
    if kind == "CANCEL":
        if not isinstance(event.get("target_order_id"), str):
            return "missing or invalid target_order_id"
        return None
    oid = event.get("order_id")
    if not isinstance(oid, str) or not oid:
        return "missing or invalid order_id"
    if not _positive_int(event.get("qty_units")):
        return "qty_units must be a positive integer"
    if kind == "LIMIT":
        if not isinstance(event.get("side"), str) or event["side"] not in SIDES:
            return f"unknown side {event.get('side')!r}"
        if not _positive_int(event.get("price_ticks")):
            return "price_ticks must be a positive integer"
    if is_live(oid):
        return f"order_id {oid!r} is already active"
    return None


def rejected(event, reason):
    event_id = event.get("event_id") if isinstance(event, dict) else None
    return {"event_id": event_id, "status": "rejected", "reason": reason}
