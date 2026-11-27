"""Shared validation performed before either engine mutates its state."""

from __future__ import annotations

from typing import AbstractSet

from .interface import Event


class EventValidationError(ValueError):
    """An input event violates the documented external contract."""


def _require_nonempty_string(event: Event, field: str) -> str:
    value = event.get(field)
    if not isinstance(value, str) or not value:
        raise EventValidationError(f"{field} must be a nonempty string")
    return value


def _require_positive_integer(event: Event, field: str) -> int:
    value = event.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EventValidationError(f"{field} must be a positive integer")
    return value


def validate_event(
    event: Event,
    last_accepted_seq: int,
    active_order_ids: AbstractSet[str],
) -> None:
    """Raise before mutation if one event violates the assignment contract."""

    seq = _require_positive_integer(event, "seq")
    if seq <= last_accepted_seq:
        raise EventValidationError("seq must be strictly increasing")

    _require_nonempty_string(event, "event_id")
    event_type = _require_nonempty_string(event, "type")
    if event_type not in {"LIMIT", "MARKET_SELL", "CANCEL"}:
        raise EventValidationError(f"unknown event type: {event_type}")

    if event_type == "LIMIT":
        order_id = _require_nonempty_string(event, "order_id")
        if order_id in active_order_ids:
            raise EventValidationError("order_id is already active")
        side = _require_nonempty_string(event, "side")
        if side not in {"BUY", "SELL"}:
            raise EventValidationError(f"unknown side: {side}")
        _require_positive_integer(event, "price_ticks")
        _require_positive_integer(event, "qty_units")
        return

    if event_type == "MARKET_SELL":
        order_id = _require_nonempty_string(event, "order_id")
        if order_id in active_order_ids:
            raise EventValidationError("order_id is already active")
        _require_positive_integer(event, "qty_units")
        return

    _require_nonempty_string(event, "target_order_id")

