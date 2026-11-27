"""Event validation shared by Version A and Version B (spec rule 6)."""


def is_positive_int(value):
    # bool is a subclass of int in Python (True == 1), so exclude it explicitly
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate(event, last_seq, is_live):
    """Return None if the event is valid, otherwise a short reason (text).
    last_seq: seq of the last ACCEPTED event.
    is_live:  function(order_id) -> True if that order is currently resting."""
    if not isinstance(event, dict):
        return "event is not an object"
    seq = event.get("seq")
    if not is_positive_int(seq):
        return "seq must be a positive integer"
    if seq <= last_seq:
        return "seq not increasing"
    etype = event.get("type")
    if etype == "LIMIT":
        if event.get("side") not in ("BUY", "SELL"):
            return "unknown side"
        if not is_positive_int(event.get("price_ticks")):
            return "price_ticks must be a positive integer"
        if not is_positive_int(event.get("qty_units")):
            return "qty_units must be a positive integer"
        if "order_id" not in event:
            return "missing order_id"
        if is_live(event["order_id"]):
            return "duplicate live order_id"
    elif etype == "MARKET_SELL":
        if not is_positive_int(event.get("qty_units")):
            return "qty_units must be a positive integer"
        if "order_id" not in event:
            return "missing order_id"
        if is_live(event["order_id"]):
            return "duplicate live order_id"
    elif etype == "CANCEL":
        if "target_order_id" not in event:
            return "missing target_order_id"
    else:
        return "unknown type"
    return None