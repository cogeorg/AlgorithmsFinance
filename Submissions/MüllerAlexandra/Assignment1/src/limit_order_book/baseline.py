"""Transparent list-based baseline implementation."""

from __future__ import annotations

from typing import cast

from .inspection import canonical_snapshot
from .interface import BookSnapshot, Event, EventResult
from .models import Fill, RestingOrder, Side
from .validation import EventValidationError, validate_event


class BaselineOrderBook:
    """Version A scans and sorts a list of individual resting orders."""

    def __init__(self) -> None:
        self._orders: list[RestingOrder] = []
        self._last_accepted_seq = 0

    def process_event(self, event: Event) -> EventResult:
        try:
            validate_event(event, self._last_accepted_seq, self._active_order_ids())
        except EventValidationError as error:
            result: EventResult = {
                "status": "rejected",
                "reason": str(error),
            }
            if "event_id" in event:
                result["event_id"] = event["event_id"]
            return result

        event_type = cast(str, event["type"])
        if event_type == "LIMIT":
            result = self.add_limit_order(event)
        elif event_type == "MARKET_SELL":
            result = self.fill_market_sell(event)
        else:
            result = self.cancel_order(event)
        self._last_accepted_seq = cast(int, event["seq"])
        return result

    def add_limit_order(self, event: Event) -> EventResult:
        order_id = cast(str, event["order_id"])
        side = cast(Side, event["side"])
        price_ticks = cast(int, event["price_ticks"])
        remaining = cast(int, event["qty_units"])
        arrival_seq = cast(int, event["seq"])
        fills: list[Fill] = []

        if side == "BUY":
            candidates = sorted(
                (
                    order
                    for order in self._orders
                    if order.side == "SELL" and order.price_ticks <= price_ticks
                ),
                key=lambda order: (order.price_ticks, order.arrival_seq),
            )
        else:
            candidates = sorted(
                (
                    order
                    for order in self._orders
                    if order.side == "BUY" and order.price_ticks >= price_ticks
                ),
                key=lambda order: (-order.price_ticks, order.arrival_seq),
            )

        for maker in candidates:
            if remaining == 0:
                break
            executed = min(remaining, maker.qty_units)
            fills.append(Fill(maker.order_id, order_id, maker.price_ticks, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                self._orders.remove(maker)

        if remaining > 0:
            self._orders.append(
                RestingOrder(order_id, side, price_ticks, remaining, arrival_seq)
            )

        return {
            "event_id": event["event_id"],
            "order_id": order_id,
            "status": "filled" if remaining == 0 else "resting",
            "unfilled_qty_units": remaining,
            "fills": [self._fill_dict(fill) for fill in fills],
        }

    def cancel_order(self, event: Event) -> EventResult:
        target = cast(str, event["target_order_id"])
        for index, order in enumerate(self._orders):
            if order.order_id == target:
                cancelled = order.qty_units
                self._orders.pop(index)
                return {
                    "event_id": event["event_id"],
                    "target_order_id": target,
                    "status": "cancelled",
                    "cancelled_qty_units": cancelled,
                }
        return {
            "event_id": event["event_id"],
            "target_order_id": target,
            "status": "not_found",
            "cancelled_qty_units": 0,
        }

    def fill_market_sell(self, event: Event) -> EventResult:
        order_id = cast(str, event["order_id"])
        requested = cast(int, event["qty_units"])
        remaining = requested
        fills: list[Fill] = []
        candidates = sorted(
            (order for order in self._orders if order.side == "BUY"),
            key=lambda order: (-order.price_ticks, order.arrival_seq),
        )

        for maker in candidates:
            if remaining == 0:
                break
            executed = min(remaining, maker.qty_units)
            fills.append(Fill(maker.order_id, order_id, maker.price_ticks, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                self._orders.remove(maker)

        if remaining == 0:
            status = "filled"
        elif remaining == requested:
            status = "unfilled"
        else:
            status = "partial"
        return {
            "event_id": event["event_id"],
            "order_id": order_id,
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": [self._fill_dict(fill) for fill in fills],
        }

    def inspect_book(self) -> BookSnapshot:
        return canonical_snapshot(self._orders)

    def _active_order_ids(self) -> set[str]:
        return {order.order_id for order in self._orders}

    @staticmethod
    def _fill_dict(fill: Fill) -> dict[str, object]:
        return {
            "maker_id": fill.maker_id,
            "taker_id": fill.taker_id,
            "price_ticks": fill.price_ticks,
            "qty_units": fill.qty_units,
        }

