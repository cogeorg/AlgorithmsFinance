"""Shared API plumbing and validation for both order-book versions.

The matching and storage algorithms live in ``baseline`` and ``revised``.
Keeping validation here makes the externally visible rejection contract
identical without making one matching implementation an oracle for the other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RestingOrder:
    """Mutable internal representation of one active resting order."""

    order_id: str
    side: str
    price_ticks: int
    qty_units: int
    arrival_seq: int

    def inspected(self) -> dict[str, object]:
        """Return a fresh canonical public representation."""

        return {
            "order_id": self.order_id,
            "side": self.side,
            "price_ticks": self.price_ticks,
            "qty_units": self.qty_units,
            "arrival_seq": self.arrival_seq,
        }


class OrderBookBase:
    """Validate events and dispatch accepted events to version-specific logic."""

    def __init__(self) -> None:
        self._last_accepted_seq: int | None = None

    @property
    def last_accepted_seq(self) -> int | None:
        """Sequence number of the latest accepted event, or ``None``."""

        return self._last_accepted_seq

    def ProcessEvent(self, event: Mapping[str, object]) -> dict[str, object]:
        """Validate and process one event without mutating the input mapping."""

        rejection = self._validate(event)
        if rejection is not None:
            return rejection

        return self._process_valid(event)

    def _process_valid(self, event: Mapping[str, object]) -> dict[str, object]:
        """Dispatch one event that has already passed complete validation."""

        # Validation proves these indexed values and their concrete types.
        event_type = event["type"]
        if event_type == "LIMIT":
            result = self._add_limit_valid(event)
        elif event_type == "MARKET_SELL":
            result = self._fill_market_sell_valid(event)
        else:
            result = self._cancel_valid(event)

        self._last_accepted_seq = event["seq"]  # type: ignore[assignment]
        return result

    def AddLimitOrder(self, event: Mapping[str, object]) -> dict[str, object]:
        """Process a limit event through the same validation as the dispatcher."""

        return self._process_expected_type(event, "LIMIT")

    def CancelOrder(self, event: Mapping[str, object]) -> dict[str, object]:
        """Process a cancellation through the same validation as the dispatcher."""

        return self._process_expected_type(event, "CANCEL")

    def FillMarketSell(self, event: Mapping[str, object]) -> dict[str, object]:
        """Process a market sell through the same validation as the dispatcher."""

        return self._process_expected_type(event, "MARKET_SELL")

    def _process_expected_type(
        self,
        event: Mapping[str, object],
        expected_type: str,
    ) -> dict[str, object]:
        """Validate a direct call and reject a valid event of another type."""

        rejection = self._validate(event)
        if rejection is not None:
            return rejection
        if event["type"] != expected_type:
            return self._rejection(event["event_id"], "wrong_event_type_for_method")
        return self._process_valid(event)

    def _validate(self, event: object) -> dict[str, object] | None:
        """Return a stable rejection dictionary, or ``None`` when accepted."""

        if not isinstance(event, Mapping):
            return self._rejection(None, "event_must_be_mapping")

        if "event_id" not in event:
            return self._rejection(None, "missing_event_id")
        event_id = event["event_id"]
        if not self._nonempty_string(event_id):
            return self._rejection(None, "invalid_event_id")

        if "seq" not in event:
            return self._rejection(event_id, "missing_seq")
        seq = event["seq"]
        if not self._positive_integer(seq):
            return self._rejection(event_id, "invalid_seq")
        if self._last_accepted_seq is not None and seq <= self._last_accepted_seq:
            return self._rejection(event_id, "nonincreasing_seq")

        if "type" not in event:
            return self._rejection(event_id, "missing_type")
        event_type = event["type"]
        if not isinstance(event_type, str) or event_type not in (
            "LIMIT",
            "MARKET_SELL",
            "CANCEL",
        ):
            return self._rejection(event_id, "unknown_event_type")

        if event_type in {"LIMIT", "MARKET_SELL"}:
            if "order_id" not in event:
                return self._rejection(event_id, "missing_order_id")
            order_id = event["order_id"]
            if not self._nonempty_string(order_id):
                return self._rejection(event_id, "invalid_order_id")
            if self._contains_order(order_id):
                return self._rejection(event_id, "duplicate_live_order_id")

        if event_type == "LIMIT":
            if "side" not in event:
                return self._rejection(event_id, "missing_side")
            side = event["side"]
            if not isinstance(side, str) or side not in ("BUY", "SELL"):
                return self._rejection(event_id, "invalid_side")
            if "price_ticks" not in event:
                return self._rejection(event_id, "missing_price_ticks")
            if not self._positive_integer(event["price_ticks"]):
                return self._rejection(event_id, "invalid_price_ticks")

        if event_type in {"LIMIT", "MARKET_SELL"}:
            if "qty_units" not in event:
                return self._rejection(event_id, "missing_qty_units")
            if not self._positive_integer(event["qty_units"]):
                return self._rejection(event_id, "invalid_qty_units")

        if event_type == "CANCEL":
            if "target_order_id" not in event:
                return self._rejection(event_id, "missing_target_order_id")
            if not self._nonempty_string(event["target_order_id"]):
                return self._rejection(event_id, "invalid_target_order_id")

        return None

    @staticmethod
    def _nonempty_string(value: object) -> bool:
        return isinstance(value, str) and bool(value)

    @staticmethod
    def _positive_integer(value: object) -> bool:
        # ``bool`` is a subclass of ``int`` and must be rejected explicitly.
        return type(value) is int and value > 0

    @staticmethod
    def _rejection(event_id: object | None, reason: str) -> dict[str, object]:
        result: dict[str, object] = {}
        if event_id is not None:
            result["event_id"] = event_id
        result["status"] = "rejected"
        result["reason"] = reason
        return result

    @staticmethod
    def _fill(
        maker: RestingOrder,
        taker_id: str,
        qty_units: int,
    ) -> dict[str, object]:
        return {
            "maker_id": maker.order_id,
            "taker_id": taker_id,
            "price_ticks": maker.price_ticks,
            "qty_units": qty_units,
        }

    def _contains_order(self, order_id: object) -> bool:
        raise NotImplementedError

    def _add_limit_valid(
        self, event: Mapping[str, object]
    ) -> dict[str, object]:
        raise NotImplementedError

    def _fill_market_sell_valid(
        self, event: Mapping[str, object]
    ) -> dict[str, object]:
        raise NotImplementedError

    def _cancel_valid(self, event: Mapping[str, object]) -> dict[str, object]:
        raise NotImplementedError

    def InspectBook(self) -> list[dict[str, object]]:
        raise NotImplementedError


def canonical_order_key(order: RestingOrder) -> tuple[int, int, int]:
    """Sort bids first/best-first, then asks best-first."""

    if order.side == "BUY":
        return (0, -order.price_ticks, order.arrival_seq)
    return (1, order.price_ticks, order.arrival_seq)
