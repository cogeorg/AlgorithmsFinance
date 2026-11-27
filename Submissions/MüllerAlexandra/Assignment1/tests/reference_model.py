"""Small test-only oracle independent of both submitted engine classes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast


class ReferenceBook:
    """Directly recompute the best eligible maker for each generated fill."""

    def __init__(self) -> None:
        self.orders: list[dict[str, object]] = []

    def process_event(self, event: Mapping[str, object]) -> dict[str, object]:
        event_type = event["type"]
        if event_type == "LIMIT":
            return self._limit(event)
        if event_type == "MARKET_SELL":
            return self._market_sell(event)
        if event_type == "CANCEL":
            return self._cancel(event)
        raise AssertionError(f"the generated oracle stream has invalid type {event_type}")

    def _limit(self, event: Mapping[str, object]) -> dict[str, object]:
        order_id = cast(str, event["order_id"])
        side = cast(str, event["side"])
        limit = cast(int, event["price_ticks"])
        remaining = cast(int, event["qty_units"])
        fills: list[dict[str, object]] = []

        while remaining:
            eligible = [
                order
                for order in self.orders
                if order["side"] != side
                and (
                    (side == "BUY" and cast(int, order["price_ticks"]) <= limit)
                    or (side == "SELL" and cast(int, order["price_ticks"]) >= limit)
                )
            ]
            if not eligible:
                break
            if side == "BUY":
                maker = min(
                    eligible,
                    key=lambda order: (order["price_ticks"], order["arrival_seq"]),
                )
            else:
                maker = min(
                    eligible,
                    key=lambda order: (-cast(int, order["price_ticks"]), order["arrival_seq"]),
                )
            executed = min(remaining, cast(int, maker["qty_units"]))
            fills.append(
                {
                    "maker_id": maker["order_id"],
                    "taker_id": order_id,
                    "price_ticks": maker["price_ticks"],
                    "qty_units": executed,
                }
            )
            maker["qty_units"] = cast(int, maker["qty_units"]) - executed
            remaining -= executed
            if maker["qty_units"] == 0:
                self.orders.remove(maker)

        if remaining:
            self.orders.append(
                {
                    "order_id": order_id,
                    "side": side,
                    "price_ticks": limit,
                    "qty_units": remaining,
                    "arrival_seq": event["seq"],
                }
            )
        return {
            "event_id": event["event_id"],
            "order_id": order_id,
            "status": "filled" if remaining == 0 else "resting",
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def _market_sell(self, event: Mapping[str, object]) -> dict[str, object]:
        order_id = cast(str, event["order_id"])
        requested = cast(int, event["qty_units"])
        remaining = requested
        fills: list[dict[str, object]] = []
        while remaining:
            bids = [order for order in self.orders if order["side"] == "BUY"]
            if not bids:
                break
            maker = min(
                bids,
                key=lambda order: (-cast(int, order["price_ticks"]), order["arrival_seq"]),
            )
            executed = min(remaining, cast(int, maker["qty_units"]))
            fills.append(
                {
                    "maker_id": maker["order_id"],
                    "taker_id": order_id,
                    "price_ticks": maker["price_ticks"],
                    "qty_units": executed,
                }
            )
            maker["qty_units"] = cast(int, maker["qty_units"]) - executed
            remaining -= executed
            if maker["qty_units"] == 0:
                self.orders.remove(maker)

        executed_total = requested - remaining
        status = "filled" if remaining == 0 else ("partial" if executed_total else "unfilled")
        return {
            "event_id": event["event_id"],
            "order_id": order_id,
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def _cancel(self, event: Mapping[str, object]) -> dict[str, object]:
        target = cast(str, event["target_order_id"])
        for order in self.orders:
            if order["order_id"] == target:
                cancelled = order["qty_units"]
                self.orders.remove(order)
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

    def inspect_book(self) -> list[dict[str, object]]:
        bids = sorted(
            (order for order in self.orders if order["side"] == "BUY"),
            key=lambda order: (-cast(int, order["price_ticks"]), order["arrival_seq"]),
        )
        asks = sorted(
            (order for order in self.orders if order["side"] == "SELL"),
            key=lambda order: (order["price_ticks"], order["arrival_seq"]),
        )
        return [dict(order) for order in [*bids, *asks]]
