"""Version B: indexed orders with FIFO queues grouped by price."""

from __future__ import annotations

from bisect import bisect_left, insort
from collections import OrderedDict
from collections.abc import Iterable

from .common import BUY, SELL, BaseLimitOrderBook, Order


class IndexedOrderBook(BaseLimitOrderBook):
    """Use an ID index, sorted price lists, and insertion-ordered price queues."""

    version = "B-indexed"

    def __init__(self, *, instrument: bool = False) -> None:
        super().__init__(instrument=instrument)
        self.active: dict[str, Order] = {}
        self.levels: dict[str, dict[int, OrderedDict[str, Order]]] = {
            BUY: {},
            SELL: {},
        }
        self.prices: dict[str, list[int]] = {BUY: [], SELL: []}

    def _best_order(self, side: str) -> Order | None:
        if self.instrument:
            self.operation_counts["best_order_calls"] += 1
        prices = self.prices[side]
        if not prices:
            return None
        price = prices[-1] if side == BUY else prices[0]
        level = self.levels[side][price]
        return next(iter(level.values()))

    def _rest(self, order: Order) -> None:
        levels = self.levels[order.side]
        if order.price_ticks not in levels:
            levels[order.price_ticks] = OrderedDict()
            insort(self.prices[order.side], order.price_ticks)
        levels[order.price_ticks][order.order_id] = order
        self.active[order.order_id] = order

    def _remove(self, order: Order) -> None:
        self.active.pop(order.order_id)
        level = self.levels[order.side][order.price_ticks]
        level.pop(order.order_id)
        if not level:
            self._remove_level(order.side, order.price_ticks)

    def _remove_level(self, side: str, price: int) -> None:
        del self.levels[side][price]
        prices = self.prices[side]
        index = bisect_left(prices, price)
        if index == len(prices) or prices[index] != price:
            raise AssertionError("price index is inconsistent")
        prices.pop(index)

    def _cancel(self, order_id: str) -> int:
        order = self.active.get(order_id)
        if order is None:
            return 0
        quantity = order.qty_units
        self._remove(order)
        return quantity

    def _is_live(self, order_id: str) -> bool:
        return order_id in self.active

    def _iter_active_orders(self) -> Iterable[Order]:
        return iter(self.active.values())

    def active_order_count(self) -> int:
        return len(self.active)

    def price_level_count(self) -> int:
        return len(self.prices[BUY]) + len(self.prices[SELL])

    def validate_invariants(self) -> None:
        super().validate_invariants()
        queued = {
            order_id
            for side_levels in self.levels.values()
            for level in side_levels.values()
            for order_id in level
        }
        if queued != set(self.active):
            raise AssertionError("active ID index and queues disagree")
        for side in (BUY, SELL):
            if self.prices[side] != sorted(self.levels[side]):
                raise AssertionError("sorted price index disagrees with levels")
