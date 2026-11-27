"""Version A: transparent list-scanning limit order book."""

from __future__ import annotations

from collections.abc import Mapping

from .common import OrderBookBase, RestingOrder, canonical_order_key


class BaselineOrderBook(OrderBookBase):
    """Store active orders in one list and scan it for every operation.

    This version favors visible control flow over speed. Finding a maker,
    detecting a duplicate, and cancelling an order are linear in active book
    size. Repeating the maker scan makes a many-fill event potentially
    quadratic in the active book size.
    """

    def __init__(self) -> None:
        super().__init__()
        self._orders: list[RestingOrder] = []

    def _contains_order(self, order_id: object) -> bool:
        return any(order.order_id == order_id for order in self._orders)

    def _add_limit_valid(
        self, event: Mapping[str, object]
    ) -> dict[str, object]:
        order_id = event["order_id"]
        side = event["side"]
        price_ticks = event["price_ticks"]
        remaining = event["qty_units"]
        assert isinstance(order_id, str)
        assert isinstance(side, str)
        assert type(price_ticks) is int
        assert type(remaining) is int

        fills: list[dict[str, object]] = []
        while remaining:
            maker = self._best_eligible_maker(side, price_ticks)
            if maker is None:
                break
            executed = min(remaining, maker.qty_units)
            fills.append(self._fill(maker, order_id, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                self._remove_identity(maker)

        if remaining:
            self._orders.append(
                RestingOrder(
                    order_id=order_id,
                    side=side,
                    price_ticks=price_ticks,
                    qty_units=remaining,
                    arrival_seq=event["seq"],  # type: ignore[arg-type]
                )
            )

        return {
            "event_id": event["event_id"],
            "order_id": order_id,
            "status": "resting" if remaining else "filled",
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def _fill_market_sell_valid(
        self, event: Mapping[str, object]
    ) -> dict[str, object]:
        order_id = event["order_id"]
        requested = event["qty_units"]
        assert isinstance(order_id, str)
        assert type(requested) is int
        remaining = requested
        fills: list[dict[str, object]] = []

        while remaining:
            maker = self._best_bid()
            if maker is None:
                break
            executed = min(remaining, maker.qty_units)
            fills.append(self._fill(maker, order_id, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                self._remove_identity(maker)

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
            "fills": fills,
        }

    def _cancel_valid(self, event: Mapping[str, object]) -> dict[str, object]:
        target = event["target_order_id"]
        assert isinstance(target, str)
        cancelled = 0
        for index, order in enumerate(self._orders):
            if order.order_id == target:
                cancelled = order.qty_units
                self._orders.pop(index)
                break
        return {
            "event_id": event["event_id"],
            "target_order_id": target,
            "status": "cancelled" if cancelled else "not_found",
            "cancelled_qty_units": cancelled,
        }

    def _best_eligible_maker(
        self, incoming_side: str, limit_price: int
    ) -> RestingOrder | None:
        best: RestingOrder | None = None
        if incoming_side == "BUY":
            for order in self._orders:
                if order.side != "SELL" or order.price_ticks > limit_price:
                    continue
                if best is None or (order.price_ticks, order.arrival_seq) < (
                    best.price_ticks,
                    best.arrival_seq,
                ):
                    best = order
        else:
            for order in self._orders:
                if order.side != "BUY" or order.price_ticks < limit_price:
                    continue
                if best is None or (-order.price_ticks, order.arrival_seq) < (
                    -best.price_ticks,
                    best.arrival_seq,
                ):
                    best = order
        return best

    def _best_bid(self) -> RestingOrder | None:
        best: RestingOrder | None = None
        for order in self._orders:
            if order.side != "BUY":
                continue
            if best is None or (-order.price_ticks, order.arrival_seq) < (
                -best.price_ticks,
                best.arrival_seq,
            ):
                best = order
        return best

    def _remove_identity(self, target: RestingOrder) -> None:
        for index, order in enumerate(self._orders):
            if order is target:
                self._orders.pop(index)
                return
        raise AssertionError("active maker missing from baseline order list")

    def InspectBook(self) -> list[dict[str, object]]:
        return [
            order.inspected()
            for order in sorted(self._orders, key=canonical_order_key)
        ]
