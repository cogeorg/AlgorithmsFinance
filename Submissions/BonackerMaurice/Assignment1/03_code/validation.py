"""Event validation shared by every version (same rules, same reasons).

validate_event(event, last_seq, is_live) -> None if valid, else a reason str.
`is_live(order_id) -> bool` is supplied by the order book, so each version
answers the duplicate-live-id question with its own data structure.

Checks, in this order (the first failing one is reported):
  1. event is a dict
  2. seq is a positive int (not bool) and > last accepted seq
  3. event_id is present
  4. type is LIMIT, MARKET_SELL or CANCEL
  5. type-specific fields:
       LIMIT:       order_id str, side BUY/SELL, price_ticks int > 0,
                    qty_units int > 0, order_id not live
       MARKET_SELL: order_id str, qty_units int > 0, order_id not live
       CANCEL:      target_order_id str (an unknown target is still valid)
"""

TYPES = ("LIMIT", "MARKET_SELL", "CANCEL")
SIDES = ("BUY", "SELL")


def _positive_int(value):
    # bool is a subclass of int; JSON 1.0 parses as float -> both rejected.
    return type(value) is int and value > 0


def validate_event(event, last_seq, is_live):
    if not isinstance(event, dict):
        return "event is not an object"

    seq = event.get("seq")
    if not _positive_int(seq):
        return "seq must be a positive integer"
    if seq <= last_seq:
        return f"non-increasing seq {seq} (last accepted {last_seq})"

    if "event_id" not in event:
        return "missing event_id"

    kind = event.get("type")
    if kind not in TYPES:
        return f"unknown type {kind!r}"

    if kind == "CANCEL":
        if not isinstance(event.get("target_order_id"), str):
            return "target_order_id must be a string"
        return None

    order_id = event.get("order_id")
    if not isinstance(order_id, str):
        return "order_id must be a string"

    if kind == "LIMIT":
        if event.get("side") not in SIDES:
            return f"unknown side {event.get('side')!r}"
        if not _positive_int(event.get("price_ticks")):
            return "price_ticks must be a positive integer"

    if not _positive_int(event.get("qty_units")):
        return "qty_units must be a positive integer"

    if is_live(order_id):
        return f"duplicate live order_id {order_id!r}"
    return None
