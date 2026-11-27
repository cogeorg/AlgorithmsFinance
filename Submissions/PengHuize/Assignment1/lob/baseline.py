"""Version A: a transparent list-scanning limit order book."""

from __future__ import annotations

from collections.abc import Iterable

from .common import BUY, SELL, BaseLimitOrderBook, Order


class ListOrderBook(BaseLimitOrderBook):
    """Store individual orders in two unsorted lists.

    Finding the next maker scans its whole side. Cancellation and duplicate-live
    checks also scan, making the implementation intentionally simple and useful as
    a baseline.
    """

    version = "A-list"

    def __init__(self, *, instrument: bool = False) -> None:
        super().__init__(instrument=instrument)
        self.bids: list[Order] = []
        self.asks: list[Order] = []

    def _side(self, side: str) -> list[Order]:
        return self.bids if side == BUY else self.asks

    def _best_order(self, side: str) -> Order | None:
        if self.instrument:
            self.operation_counts["best_order_calls"] += 1
        best: Order | None = None
        for candidate in self._side(side):
            if self.instrument:
                self.operation_counts["maker_scans"] += 1
            if best is None:
                best = candidate
            elif side == BUY and (
                candidate.price_ticks > best.price_ticks
                or (
                    candidate.price_ticks == best.price_ticks
                    and candidate.arrival_seq < best.arrival_seq
                )
            ):
                best = candidate
            elif side == SELL and (
                candidate.price_ticks < best.price_ticks
                or (
                    candidate.price_ticks == best.price_ticks
                    and candidate.arrival_seq < best.arrival_seq
                )
            ):
                best = candidate
        return best

    def _rest(self, order: Order) -> None:
        self._side(order.side).append(order)

    def _remove(self, order: Order) -> None:
        side = self._side(order.side)
        for index, candidate in enumerate(side):
            if candidate is order:
                side.pop(index)
                return
        raise AssertionError("attempted to remove a missing order")

    def _cancel(self, order_id: str) -> int:
        for side in (self.bids, self.asks):
            for index, order in enumerate(side):
                if order.order_id == order_id:
                    quantity = order.qty_units
                    side.pop(index)
                    return quantity
        return 0

    def _is_live(self, order_id: str) -> bool:
        return any(
            order.order_id == order_id for order in (*self.bids, *self.asks)
        )

    def _iter_active_orders(self) -> Iterable[Order]:
        yield from self.bids
        yield from self.asks

    def active_order_count(self) -> int:
        return len(self.bids) + len(self.asks)

    def price_level_count(self) -> int:
        return len({(order.side, order.price_ticks) for order in self._iter_active_orders()})
