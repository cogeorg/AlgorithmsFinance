"""Shared input validation for Version A and Version B (SPEC.md, Validation; Q2-Q5, Q13, Q14).

One module for both versions, so they cannot diverge on bad input. Consequence: the
A/B differential test cannot catch validation bugs, so every rule has its own
contract check (02_tests/contract.py) and direct test (02_tests/test_validation.py).

Interface (fixed in SPEC.md):
    validate(event, last_seq, is_live, expected_type=None) -> str | None
        reason code of the FIRST failing rule in the fixed check order, or None if valid.
        `last_seq`: seq of the last accepted event (0 before the first one).
        `is_live(order_id) -> bool`: True if the id is currently resting in the book.
    rejection(event, reason) -> dict
        {"event_id": <event_id if a non-empty str, else None>, "status": "rejected", "reason": reason}

`expected_type` is set by direct methods; its check follows unknown_type (N2).
Unknown extra fields are ignored (N3). No state or caller data is changed here.
"""

EVENT_TYPES = ("LIMIT", "MARKET_SELL", "CANCEL")
SIDES = ("BUY", "SELL")

# Required fields per type, in the order in which a missing one is reported
# (`event_id` first for every type; `seq` and `type` are checked earlier).
REQUIRED_FIELDS = {
    "LIMIT": ("event_id", "order_id", "side", "price_ticks", "qty_units"),
    "MARKET_SELL": ("event_id", "order_id", "qty_units"),
    "CANCEL": ("event_id", "target_order_id"),
}

# Reason codes (SPEC.md, Q2). `missing_field:<name>` and `bad_id:<name>` carry the field name.
NOT_AN_OBJECT = "not_an_object"
BAD_SEQ = "bad_seq"
NONINCREASING_SEQ = "nonincreasing_seq"
UNKNOWN_TYPE = "unknown_type"
WRONG_TYPE_FOR_METHOD = "wrong_type_for_method"
MISSING_FIELD = "missing_field:"
BAD_ID = "bad_id:"
UNKNOWN_SIDE = "unknown_side"
BAD_PRICE = "bad_price"
BAD_QTY = "bad_qty"
DUPLICATE_LIVE_ORDER_ID = "duplicate_live_order_id"


def validate(event, last_seq, is_live, expected_type=None):
    """Return the first failing reason, following SPEC.md's numbered table."""
    # 1-4: establish an object and a fresh positive integer sequence number.
    if not isinstance(event, dict):
        return NOT_AN_OBJECT
    if "seq" not in event:
        return MISSING_FIELD + "seq"
    if not _positive_int(event["seq"]):
        return BAD_SEQ
    if event["seq"] <= last_seq:
        return NONINCREASING_SEQ

    # 5-7: establish a known type before checking the direct-method constraint.
    # Tuple membership also safely rejects unhashable JSON values (lists/dicts).
    if "type" not in event:
        return MISSING_FIELD + "type"
    kind = event["type"]
    if kind not in EVENT_TYPES:
        return UNKNOWN_TYPE
    if expected_type is not None and kind != expected_type:
        return WRONG_TYPE_FOR_METHOD

    # 8: report any missing required field before checking field values.
    for name in REQUIRED_FIELDS[kind]:
        if name not in event:
            return MISSING_FIELD + name

    # 9: a present null or empty identifier is bad, rather than missing.
    id_field = "target_order_id" if kind == "CANCEL" else "order_id"
    for name in ("event_id", id_field):
        if not isinstance(event[name], str) or not event[name]:
            return BAD_ID + name

    # 10-12: only fields relevant to this event type are validated.
    if kind == "LIMIT":
        if event["side"] not in SIDES:
            return UNKNOWN_SIDE
        if not _positive_int(event["price_ticks"]):
            return BAD_PRICE
    if kind != "CANCEL" and not _positive_int(event["qty_units"]):
        return BAD_QTY

    # 13: duplicate detection is last; CANCEL targets need not be live.
    if kind != "CANCEL" and is_live(event["order_id"]):
        return DUPLICATE_LIVE_ORDER_ID
    return None


def _positive_int(value):
    """bool is a subclass of int, but is outside the input domain."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def rejection(event, reason):
    event_id = event.get("event_id") if isinstance(event, dict) else None
    if not isinstance(event_id, str) or not event_id:
        event_id = None
    return {"event_id": event_id, "status": "rejected", "reason": reason}
