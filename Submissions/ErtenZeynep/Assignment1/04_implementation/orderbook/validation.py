"""State-independent validation for assignment event dictionaries."""

from __future__ import annotations

from typing import Any

from .contracts import EVENT_CANCEL, EVENT_LIMIT, EVENT_MARKET_SELL


_COMMON_FIELDS = frozenset({"seq", "event_id", "type"})
_TYPE_FIELDS = {
    EVENT_LIMIT: frozenset({"order_id", "side", "price_ticks", "qty_units"}),
    EVENT_MARKET_SELL: frozenset({"order_id", "qty_units"}),
    EVENT_CANCEL: frozenset({"target_order_id"}),
}


def rejected_result(event: Any, reason: str) -> dict[str, Any]:
    """Build the assignment rejection schema without consulting engine state."""

    result: dict[str, Any] = {}
    if type(event) is dict and "event_id" in event:
        result["event_id"] = event["event_id"]
    result["status"] = "rejected"
    result["reason"] = reason
    return result


def _is_identifier(value: Any) -> bool:
    return type(value) is str and bool(value)


def validate_event(event: Any) -> dict[str, Any] | None:
    """Return a rejection dictionary, or ``None`` for statelessly valid input."""

    if type(event) is not dict:
        return rejected_result(event, "invalid_event")
    if not _COMMON_FIELDS.issubset(event):
        return rejected_result(event, "missing_field")
    if not _is_identifier(event["event_id"]):
        return rejected_result(event, "invalid_identifier")
    if type(event["seq"]) is not int:
        return rejected_result(event, "invalid_field_type")
    if event["seq"] <= 0:
        return rejected_result(event, "invalid_sequence")
    if type(event["type"]) is not str:
        return rejected_result(event, "invalid_field_type")

    event_type = event["type"]
    if event_type not in _TYPE_FIELDS:
        return rejected_result(event, "invalid_event_type")
    if not _TYPE_FIELDS[event_type].issubset(event):
        return rejected_result(event, "missing_field")

    identifier_field = "target_order_id" if event_type == EVENT_CANCEL else "order_id"
    if not _is_identifier(event[identifier_field]):
        return rejected_result(event, "invalid_identifier")

    if event_type == EVENT_LIMIT:
        if type(event["side"]) is not str:
            return rejected_result(event, "invalid_field_type")
        if event["side"] not in {"BUY", "SELL"}:
            return rejected_result(event, "invalid_side")
        if type(event["price_ticks"]) is not int:
            return rejected_result(event, "invalid_field_type")
        if event["price_ticks"] <= 0:
            return rejected_result(event, "nonpositive_price")

    if event_type in {EVENT_LIMIT, EVENT_MARKET_SELL}:
        if type(event["qty_units"]) is not int:
            return rejected_result(event, "invalid_field_type")
        if event["qty_units"] <= 0:
            return rejected_result(event, "nonpositive_quantity")

    return None

