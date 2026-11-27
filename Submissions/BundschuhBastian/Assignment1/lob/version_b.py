"""Version B: revised data organization (Phase 3).

Per side:
  - `levels`: dict  price -> level = [queue, live, dead]
    `queue` is a deque of order records [qty, arrival_seq, order_id] in arrival order (FIFO).
    A partial fill changes qty in place, so the order keeps its place.
    Cancel is LAZY: the record stays in the deque with qty = 0 ("dead") and is skipped or
    popped when it reaches the front. `live` counts records with qty > 0, `dead` counts the
    zeros, so a price level whose last live order goes away is still dropped at once.
    Compaction: after a cancel or a match, if more than half of a deque is dead, it is
    rebuilt without the dead records. Then len(queue) <= 2 * live at all times between
    operations, so memory stays O(B) (not O(number of submissions)).
  - `keys`: sorted list of occupied prices (bisect). Asks are stored negated (-price), so
    on BOTH sides the best price is the LAST element: best price O(1), remove best O(1).
    A new or emptied price level costs O(P) (list insert / delete in the middle).
One index for both sides: order_id -> (is_bid, price, record). It answers "is this id live?"
and finds a cancel target in O(1).
Cost: cancel O(1) amortized (a compaction costs O(len) but removes more than len/2 dead
records, each paid for by one earlier cancel); worst single cancel O(len of its queue).

Interface: SPEC.md section 6. Final design and the A -> B changes: REVISIONS.md.
"""
from __future__ import annotations

from bisect import bisect_left, insort
from collections import deque

from lob.common import (BUY, CANCEL, LIMIT, SELL, is_valid_fast, rejected_result,
                        validate)

QTY, SEQ, OID = 0, 1, 2          # positions inside an order record [qty, arrival_seq, order_id]
QUEUE, LIVE, DEAD = 0, 1, 2      # positions inside a price level [queue, live, dead]


class _Side:
    """One side of the book (all bids or all asks)."""

    __slots__ = ("is_bid", "levels", "keys")

    def __init__(self, is_bid: bool) -> None:
        self.is_bid = is_bid
        self.levels: dict[int, list] = {}      # price -> [deque of records, live, dead]
        self.keys: list[int] = []      # sorted ascending; best price is keys[-1]

    def key(self, price: int) -> int:
        return price if self.is_bid else -price

    def price_of(self, key: int) -> int:
        return key if self.is_bid else -key

    def best_price(self) -> int | None:
        return self.price_of(self.keys[-1]) if self.keys else None

    def cancel(self, price: int, rec: list) -> None:
        """Lazy cancel of one live record: mark it dead, drop the level if no live order is
        left, compact the queue if more than half of it is dead."""
        level = self.levels[price]
        rec[QTY] = 0
        level[LIVE] -= 1
        if level[LIVE] == 0:
            self.drop_level(price)
        else:
            level[DEAD] += 1
            self.compact_if_needed(level)

    @staticmethod
    def compact_if_needed(level: list) -> None:
        if level[DEAD] * 2 > len(level[QUEUE]):
            level[QUEUE] = deque(r for r in level[QUEUE] if r[QTY])
            level[DEAD] = 0

    def drop_level(self, price: int) -> None:
        del self.levels[price]
        k = self.key(price)
        if self.keys[-1] == k:
            self.keys.pop()
        else:
            del self.keys[bisect_left(self.keys, k)]


class OrderBookB:
    """Revised limit order book (price levels + FIFO queues + order index)."""

    name = "B"

    def __init__(self) -> None:
        self.last_seq = 0
        self._bids = _Side(True)
        self._asks = _Side(False)
        self._index: dict[str, tuple[bool, int, list]] = {}    # order_id -> (is_bid, price, record)

    # --- entry point -------------------------------------------------------------
    def process(self, event: dict) -> dict:
        if not is_valid_fast(event, self.last_seq, self._index):
            reason = validate(event, self.last_seq, self._index.__contains__)
            if reason is not None:
                return rejected_result(event, reason)  # last_seq stays unchanged
        self.last_seq = event["seq"]
        if event["type"] == LIMIT:
            return self.AddLimitOrder(event)
        if event["type"] == CANCEL:
            return self.CancelOrder(event)
        return self.FillMarketSell(event)

    # --- the three operations (assume a validated event) -------------------------
    def AddLimitOrder(self, event: dict) -> dict:  # noqa: N802 (name from the spec)
        is_buy = event["side"] == BUY
        order_id = event["order_id"]
        price = event["price_ticks"]
        remaining = event["qty_units"]
        opposite, own = (self._asks, self._bids) if is_buy else (self._bids, self._asks)
        fills: list[dict] = []
        keys = opposite.keys
        # Only call the matching loop if the order can cross the best opposite price.
        if keys and (price >= -keys[-1] if is_buy else price <= keys[-1]):
            fills, remaining = self._take(opposite, order_id, remaining, price)
        if remaining > 0:
            levels = own.levels                     # inlined _Side.add (hot path)
            level = levels.get(price)
            if level is None:
                level = levels[price] = [deque(), 0, 0]
                insort(own.keys, price if is_buy else -price)
            rec = [remaining, event["seq"], order_id]
            level[QUEUE].append(rec)
            level[LIVE] += 1
            self._index[order_id] = (is_buy, price, rec)
        return {"event_id": event["event_id"], "order_id": order_id,
                "status": "resting" if remaining > 0 else "filled",
                "unfilled_qty_units": remaining, "fills": fills}

    def FillMarketSell(self, event: dict) -> dict:  # noqa: N802
        fills, remaining = self._take(self._bids, event["order_id"], event["qty_units"], None)
        status = "filled" if remaining == 0 else ("partial" if fills else "unfilled")
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": status, "unfilled_qty_units": remaining, "fills": fills}

    def CancelOrder(self, event: dict) -> dict:  # noqa: N802
        target = event["target_order_id"]
        where = self._index.pop(target, None)
        if where is None:
            return {"event_id": event["event_id"], "target_order_id": target,
                    "status": "not_found", "cancelled_qty_units": 0, "fills": []}
        is_bid, price, rec = where
        cancelled_qty = rec[QTY]                    # read before cancel() zeroes it
        (self._bids if is_bid else self._asks).cancel(price, rec)
        return {"event_id": event["event_id"], "target_order_id": target,
                "status": "cancelled", "cancelled_qty_units": cancelled_qty, "fills": []}

    # --- inspection ----------------------------------------------------------------
    def snapshot(self) -> list[dict]:
        out: list[dict] = []
        for side, name in ((self._bids, BUY), (self._asks, SELL)):
            for key in reversed(side.keys):        # best price first = canonical order
                price = side.price_of(key)
                for rec in side.levels[price][QUEUE]:           # FIFO = arrival order
                    if rec[QTY]:                                # skip dead records
                        out.append({"order_id": rec[OID], "side": name, "price_ticks": price,
                                    "qty_units": rec[QTY], "arrival_seq": rec[SEQ]})
        return out

    def best_bid(self) -> int | None:
        return self._bids.best_price()

    def best_ask(self) -> int | None:
        return self._asks.best_price()

    # --- matching ------------------------------------------------------------------
    def _take(self, side: _Side, taker_id: str, qty: int,
              limit_price: int | None) -> tuple[list[dict], int]:
        """Trade against `side` from the best price until qty is used up, the side is
        empty, or the best price no longer crosses `limit_price` (None = no limit).
        Returns (fills, remaining quantity)."""
        fills: list[dict] = []
        is_bid = side.is_bid
        index = self._index
        while qty > 0 and side.keys:
            price = side.price_of(side.keys[-1])
            if limit_price is not None and (
                    price < limit_price if is_bid else price > limit_price):
                break
            level = side.levels[price]
            queue = level[QUEUE]
            while qty > 0 and level[LIVE]:
                rec = queue[0]                                  # oldest record at this price
                rec_qty = rec[QTY]
                if rec_qty == 0:                                # dead (cancelled) record
                    queue.popleft()
                    level[DEAD] -= 1
                    continue
                traded = qty if qty < rec_qty else rec_qty
                fills.append({"maker_id": rec[OID], "taker_id": taker_id,
                              "price_ticks": price, "qty_units": traded})
                qty -= traded
                if traded == rec_qty:
                    queue.popleft()
                    level[LIVE] -= 1
                    del index[rec[OID]]
                else:
                    rec[QTY] = rec_qty - traded
            if level[LIVE] == 0:
                side.drop_level(price)
            else:
                side.compact_if_needed(level)
        return fills, qty
