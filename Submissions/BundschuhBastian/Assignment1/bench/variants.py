"""Fairness variant for Phase 6c: Version A plus a set of live order ids.

Version A checks "is this id live?" with a scan of both lists on every event (O(B)). A reader may say
that this makes A unfairly slow: any baseline would keep a set of ids. `OrderBookAIdSet` is A with
exactly that one change: validation asks a set (O(1)); everything else (list per side, scan for the
best price, scan for the cancel target, list.pop) is A's code. It is a labeled variant for the
fairness check only (results/fairness_time.csv, version "A_idset"); it never replaces Version A and
lives outside lob/. The set is kept up to date in the three places where an order appears or goes.
"""
from __future__ import annotations

from lob.common import BUY, SELL
from lob.version_a import ID, OrderBookA, QTY

NAME = "A_idset"


class OrderBookAIdSet(OrderBookA):
    name = NAME

    def __init__(self) -> None:
        super().__init__()
        self._live: set[str] = set()

    def _is_live(self, order_id: str) -> bool:           # O(1) instead of two scans
        return order_id in self._live

    def AddLimitOrder(self, event: dict) -> dict:  # noqa: N802
        result = super().AddLimitOrder(event)
        if result["status"] == "resting":
            self._live.add(event["order_id"])
        return result

    def CancelOrder(self, event: dict) -> dict:  # noqa: N802
        result = super().CancelOrder(event)
        if result["status"] == "cancelled":
            self._live.discard(event["target_order_id"])
        return result

    def _take(self, side, side_is_bid, taker_id, qty, limit_price):
        """A's `_take` unchanged, plus: a maker that is filled completely leaves the set."""
        fills: list[dict] = []
        while qty > 0 and side:
            i = self._best_index(side, side_is_bid)
            rec = side[i]
            if limit_price is not None:
                crosses = (rec[1] >= limit_price) if side_is_bid else (rec[1] <= limit_price)
                if not crosses:
                    break
            traded = min(qty, rec[QTY])
            fills.append({"maker_id": rec[ID], "taker_id": taker_id,
                          "price_ticks": rec[1], "qty_units": traded})
            qty -= traded
            rec[QTY] -= traded
            if rec[QTY] == 0:
                side.pop(i)
                self._live.discard(rec[ID])
        return fills, qty


__all__ = ["OrderBookAIdSet", "NAME", "BUY", "SELL"]
