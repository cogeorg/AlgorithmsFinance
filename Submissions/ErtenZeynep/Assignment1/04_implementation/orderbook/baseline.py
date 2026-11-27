"""Transparent active-order-list baseline limit order book."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import EVENT_CANCEL, EVENT_LIMIT, EVENT_MARKET_SELL
from .validation import rejected_result, validate_event


@dataclass(slots=True)
class _ActiveOrder:
    order_id: str
    side: str
    price_ticks: int
    qty_units: int
    arrival_seq: int


class BaselineOrderBook:
    """Auditable baseline that stores every active order in one list."""

    def __init__(self) -> None:
        self._orders: list[_ActiveOrder] = []
        self._last_accepted_seq: int | None = None

    @property
    def last_accepted_seq(self) -> int | None:
        return self._last_accepted_seq

    def canonical_snapshot(self) -> list[dict[str, Any]]:
        ordered = sorted(
            self._orders,
            key=lambda order: (
                0 if order.side == "BUY" else 1,
                -order.price_ticks if order.side == "BUY" else order.price_ticks,
                order.arrival_seq,
            ),
        )
        return [
            {
                "order_id": order.order_id,
                "side": order.side,
                "price_ticks": order.price_ticks,
                "qty_units": order.qty_units,
                "arrival_seq": order.arrival_seq,
            }
            for order in ordered
        ]

    def process_event(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=None)

    def AddLimitOrder(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=EVENT_LIMIT)

    def CancelOrder(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=EVENT_CANCEL)

    def FillMarketSell(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=EVENT_MARKET_SELL)

    def _process(self, event: Any, required_type: str | None) -> dict[str, Any]:
        rejection = validate_event(event)
        if rejection is not None:
            return rejection
        if required_type is not None and event["type"] != required_type:
            return rejected_result(event, "invalid_event_type")
        if self._last_accepted_seq is not None and event["seq"] <= self._last_accepted_seq:
            return rejected_result(event, "nonincreasing_sequence")
        if event["type"] in {EVENT_LIMIT, EVENT_MARKET_SELL} and self._has_live_id(event["order_id"]):
            return rejected_result(event, "duplicate_live_order_id")

        if event["type"] == EVENT_LIMIT:
            result = self._apply_limit(event)
        elif event["type"] == EVENT_MARKET_SELL:
            result = self._apply_market_sell(event)
        else:
            result = self._apply_cancel(event)
        self._last_accepted_seq = event["seq"]
        return result

    def _has_live_id(self, order_id: str) -> bool:
        return any(order.order_id == order_id for order in self._orders)

    def _apply_limit(self, event: dict[str, Any]) -> dict[str, Any]:
        if event["side"] == "BUY":
            makers = [
                order
                for order in self._orders
                if order.side == "SELL" and order.price_ticks <= event["price_ticks"]
            ]
            makers.sort(key=lambda order: (order.price_ticks, order.arrival_seq))
        else:
            makers = [
                order
                for order in self._orders
                if order.side == "BUY" and order.price_ticks >= event["price_ticks"]
            ]
            makers.sort(key=lambda order: (-order.price_ticks, order.arrival_seq))

        fills, residual = self._match(event["order_id"], event["qty_units"], makers)
        if residual > 0:
            self._orders.append(
                _ActiveOrder(
                    order_id=event["order_id"],
                    side=event["side"],
                    price_ticks=event["price_ticks"],
                    qty_units=residual,
                    arrival_seq=event["seq"],
                )
            )
            status = "resting"
        else:
            status = "filled"
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "fills": fills,
            "status": status,
            "unfilled_qty_units": residual,
        }

    def _apply_market_sell(self, event: dict[str, Any]) -> dict[str, Any]:
        makers = [order for order in self._orders if order.side == "BUY"]
        makers.sort(key=lambda order: (-order.price_ticks, order.arrival_seq))
        fills, residual = self._match(event["order_id"], event["qty_units"], makers)
        if residual == 0:
            status = "filled"
        elif fills:
            status = "partial"
        else:
            status = "unfilled"
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "fills": fills,
            "status": status,
            "unfilled_qty_units": residual,
        }

    def _apply_cancel(self, event: dict[str, Any]) -> dict[str, Any]:
        for index, order in enumerate(self._orders):
            if order.order_id == event["target_order_id"]:
                cancelled = order.qty_units
                self._orders.pop(index)
                return {
                    "event_id": event["event_id"],
                    "target_order_id": event["target_order_id"],
                    "status": "cancelled",
                    "cancelled_qty_units": cancelled,
                }
        return {
            "event_id": event["event_id"],
            "target_order_id": event["target_order_id"],
            "status": "not_found",
            "cancelled_qty_units": 0,
        }

    def _match(
        self,
        taker_id: str,
        incoming_qty: int,
        makers: list[_ActiveOrder],
    ) -> tuple[list[dict[str, Any]], int]:
        residual = incoming_qty
        fills: list[dict[str, Any]] = []
        for maker in makers:
            if residual == 0:
                break
            executed = min(residual, maker.qty_units)
            fills.append(
                {
                    "maker_id": maker.order_id,
                    "taker_id": taker_id,
                    "price_ticks": maker.price_ticks,
                    "qty_units": executed,
                }
            )
            maker.qty_units -= executed
            residual -= executed
        self._orders = [order for order in self._orders if order.qty_units > 0]
        return fills, residual

