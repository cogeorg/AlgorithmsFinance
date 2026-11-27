"""Version B: indexed price-level limit order book."""

from __future__ import annotations

from bisect import bisect_left, insort
from collections.abc import Mapping

from .common import OrderBookBase, RestingOrder, canonical_order_key


class RevisedOrderBook(OrderBookBase):
    """Group FIFO makers by price and index every active identifier.

    Python dictionaries preserve insertion order, so each price-level mapping
    is a FIFO queue that also supports constant-time removal by identifier.
    Sorted price keys make the best bid and ask available at the end of their
    respective lists. Empty levels are removed eagerly, avoiding stale orders
    during cancellation-heavy workloads.
    """

    def __init__(self) -> None:
        super().__init__()
        self._levels: dict[str, dict[int, dict[str, RestingOrder]]] = {
            "BUY": {},
            "SELL": {},
        }
        self._bid_price_keys: list[int] = []
        # Negative ask prices make the lowest actual ask the final element.
        self._ask_price_keys: list[int] = []
        self._active: dict[str, RestingOrder] = {}

    def _contains_order(self, order_id: object) -> bool:
        return order_id in self._active

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
        opposite = "SELL" if side == "BUY" else "BUY"
        while remaining:
            maker = self._best_maker(opposite)
            if maker is None or not self._crosses(side, price_ticks, maker.price_ticks):
                break
            executed = min(remaining, maker.qty_units)
            fills.append(self._fill(maker, order_id, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                self._remove_active(maker)

        if remaining:
            self._rest(
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
            maker = self._best_maker("BUY")
            if maker is None:
                break
            executed = min(remaining, maker.qty_units)
            fills.append(self._fill(maker, order_id, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                self._remove_active(maker)

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
        order = self._active.get(target)
        if order is None:
            cancelled = 0
        else:
            cancelled = order.qty_units
            self._remove_active(order)
        return {
            "event_id": event["event_id"],
            "target_order_id": target,
            "status": "cancelled" if cancelled else "not_found",
            "cancelled_qty_units": cancelled,
        }

    @staticmethod
    def _crosses(incoming_side: str, limit_price: int, maker_price: int) -> bool:
        if incoming_side == "BUY":
            return limit_price >= maker_price
        return limit_price <= maker_price

    def _rest(self, order: RestingOrder) -> None:
        side_levels = self._levels[order.side]
        level = side_levels.get(order.price_ticks)
        if level is None:
            level = {}
            side_levels[order.price_ticks] = level
            price_key = self._price_key(order.side, order.price_ticks)
            insort(self._price_keys(order.side), price_key)
        level[order.order_id] = order
        self._active[order.order_id] = order

    def _best_maker(self, side: str) -> RestingOrder | None:
        price_keys = self._price_keys(side)
        if not price_keys:
            return None
        price = self._actual_price(side, price_keys[-1])
        level = self._levels[side][price]
        return next(iter(level.values()))

    def _remove_active(self, order: RestingOrder) -> None:
        level = self._levels[order.side][order.price_ticks]
        del level[order.order_id]
        del self._active[order.order_id]
        if level:
            return

        del self._levels[order.side][order.price_ticks]
        price_keys = self._price_keys(order.side)
        key = self._price_key(order.side, order.price_ticks)
        index = bisect_left(price_keys, key)
        if index == len(price_keys) or price_keys[index] != key:
            raise AssertionError("empty price level missing from sorted price keys")
        price_keys.pop(index)

    def _price_keys(self, side: str) -> list[int]:
        return self._bid_price_keys if side == "BUY" else self._ask_price_keys

    @staticmethod
    def _price_key(side: str, price: int) -> int:
        return price if side == "BUY" else -price

    @staticmethod
    def _actual_price(side: str, price_key: int) -> int:
        return price_key if side == "BUY" else -price_key

    def InspectBook(self) -> list[dict[str, object]]:
        return [
            order.inspected()
            for order in sorted(self._active.values(), key=canonical_order_key)
        ]
