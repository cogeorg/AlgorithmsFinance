"""Version A: transparent baseline.

Data organization: one Python list of order records per side, in arrival order
(new orders are appended, and seq only grows, so list order = arrival order).
Each record is a small list [order_id, price_ticks, qty_units, arrival_seq].

Nothing is indexed. Every lookup is a scan:
  - best price: one pass over the side            -> O(B)
  - cancel / "is this id live?": one pass         -> O(B)
  - remove a filled record: list.pop(i)           -> O(B)
So an insert costs O(B), a cancel O(B), and an event with F fills costs O(F * B).
Interface: SPEC.md section 6.
"""
from __future__ import annotations

from lob.common import (BUY, CANCEL, LIMIT, SELL, rejected_result, snapshot_sort_key,
                        validate)

ID, PRICE, QTY, SEQ = 0, 1, 2, 3     # positions inside a record


class OrderBookA:
    """Baseline limit order book (list per side, linear scans)."""

    name = "A"

    def __init__(self) -> None:
        self.last_seq = 0
        self._bids: list[list] = []
        self._asks: list[list] = []

    # --- entry point -------------------------------------------------------------
    def process(self, event: dict) -> dict:
        reason = validate(event, self.last_seq, self._is_live)
        if reason is not None:
            return rejected_result(event, reason)      # last_seq stays unchanged
        self.last_seq = event["seq"]
        if event["type"] == LIMIT:
            return self.AddLimitOrder(event)
        if event["type"] == CANCEL:
            return self.CancelOrder(event)
        return self.FillMarketSell(event)

    # --- the three operations (assume a validated event) -------------------------
    def AddLimitOrder(self, event: dict) -> dict:  # noqa: N802 (name from the spec)
        is_buy = event["side"] == BUY
        opposite = self._asks if is_buy else self._bids
        limit_price = event["price_ticks"]
        fills, remaining = self._take(opposite, not is_buy, event["order_id"],
                                      event["qty_units"], limit_price)
        if remaining > 0:
            own = self._bids if is_buy else self._asks
            own.append([event["order_id"], limit_price, remaining, event["seq"]])
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": "resting" if remaining > 0 else "filled",
                "unfilled_qty_units": remaining, "fills": fills}

    def FillMarketSell(self, event: dict) -> dict:  # noqa: N802
        fills, remaining = self._take(self._bids, True, event["order_id"],
                                      event["qty_units"], None)
        status = "filled" if remaining == 0 else ("partial" if fills else "unfilled")
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": status, "unfilled_qty_units": remaining, "fills": fills}

    def CancelOrder(self, event: dict) -> dict:  # noqa: N802
        target = event["target_order_id"]
        for side in (self._bids, self._asks):
            for i, rec in enumerate(side):
                if rec[ID] == target:
                    side.pop(i)
                    return {"event_id": event["event_id"], "target_order_id": target,
                            "status": "cancelled", "cancelled_qty_units": rec[QTY],
                            "fills": []}
        return {"event_id": event["event_id"], "target_order_id": target,
                "status": "not_found", "cancelled_qty_units": 0, "fills": []}

    # --- inspection ----------------------------------------------------------------
    def snapshot(self) -> list[dict]:
        orders = [self._as_dict(r, BUY) for r in self._bids]
        orders += [self._as_dict(r, SELL) for r in self._asks]
        orders.sort(key=snapshot_sort_key)
        return orders

    def best_bid(self) -> int | None:
        return max((r[PRICE] for r in self._bids), default=None)

    def best_ask(self) -> int | None:
        return min((r[PRICE] for r in self._asks), default=None)

    # --- helpers ---------------------------------------------------------------------
    @staticmethod
    def _as_dict(rec: list, side: str) -> dict:
        return {"order_id": rec[ID], "side": side, "price_ticks": rec[PRICE],
                "qty_units": rec[QTY], "arrival_seq": rec[SEQ]}

    def _is_live(self, order_id: str) -> bool:
        return (any(r[ID] == order_id for r in self._bids)
                or any(r[ID] == order_id for r in self._asks))

    @staticmethod
    def _best_index(side: list[list], is_bid: bool) -> int:
        """Index of the best record: highest bid / lowest ask, then smallest arrival seq."""
        best = 0
        for i in range(1, len(side)):
            r, b = side[i], side[best]
            if is_bid:
                better = r[PRICE] > b[PRICE] or (r[PRICE] == b[PRICE] and r[SEQ] < b[SEQ])
            else:
                better = r[PRICE] < b[PRICE] or (r[PRICE] == b[PRICE] and r[SEQ] < b[SEQ])
            if better:
                best = i
        return best

    def _take(self, side: list[list], side_is_bid: bool, taker_id: str, qty: int,
              limit_price: int | None) -> tuple[list[dict], int]:
        """Trade against `side` from the best price until qty is used up, the side is
        empty, or the best price no longer crosses `limit_price` (None = no limit).
        Returns (fills, remaining quantity)."""
        fills: list[dict] = []
        while qty > 0 and side:
            i = self._best_index(side, side_is_bid)
            rec = side[i]
            if limit_price is not None:
                crosses = (rec[PRICE] >= limit_price) if side_is_bid \
                    else (rec[PRICE] <= limit_price)
                if not crosses:
                    break
            traded = min(qty, rec[QTY])
            fills.append({"maker_id": rec[ID], "taker_id": taker_id,
                          "price_ticks": rec[PRICE], "qty_units": traded})
            qty -= traded
            rec[QTY] -= traded
            if rec[QTY] == 0:
                side.pop(i)
        return fills, qty
