"""B2: ordered per-level maps for direct cancellation, B1's sorted prices.

Public dispatch, validation, result construction and accepted-event counters are
inherited from B1. Only level storage and its matching/removal paths change.
No dead records are retained in levels and no compaction is needed.
"""
from bisect import bisect_left
from collections import OrderedDict

from lob.book_b import OrderBookB, _Order


class _OrderedLevel:
    __slots__ = ("queue",)

    def __init__(self):
        self.queue = OrderedDict()


class OrderBookB2(OrderBookB):
    """Indexed OrderedDict FIFO levels; sorted signed prices as in B1."""

    def _cancel(self, event):
        record = self.orders.pop(event["target_order_id"], None)
        qty = 0
        if record is not None:
            qty = record.qty_units
            record.alive = False
            side = self.bids if record.side == "BUY" else self.asks
            level = side.levels[record.price_ticks]
            del level.queue[record.order_id]
            if not level.queue:
                self._remove_level(side, record.price_ticks, level)
        return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                "status": "cancelled" if record is not None else "not_found",
                "cancelled_qty_units": qty}

    def _remove_level(self, side, price, level, *, best=False):
        del side.levels[price]
        if best:
            side.prices.pop()
        else:
            i = bisect_left(side.prices, side.sign * price)
            if self.counters is not None:
                self.counters.price_list_shifts += len(side.prices) - i - 1
            del side.prices[i]

    def _match(self, event, incoming_side, limit):
        side = self.asks if incoming_side == "BUY" else self.bids
        remaining, fills = event["qty_units"], []
        c = self.counters
        while remaining > 0 and side.prices:
            price = side.sign * side.prices[-1]
            level = side.levels[price]
            if c is not None:
                c.levels_visited += 1
            if limit is not None:
                if (incoming_side == "BUY" and price > limit) or (incoming_side == "SELL" and price < limit):
                    break
            while remaining > 0 and level.queue:
                # OrderedDict keeps a linked FIFO, so first-entry access is O(1).
                maker = next(iter(level.queue.values()))
                qty = min(remaining, maker.qty_units)
                fills.append({"maker_id": maker.order_id, "taker_id": event["order_id"],
                              "price_ticks": price, "qty_units": qty})
                if c is not None:
                    c.makers_touched += 1
                    c.fills += 1
                remaining -= qty
                maker.qty_units -= qty
                if maker.qty_units == 0:
                    maker.alive = False
                    level.queue.popitem(last=False)
                    del self.orders[maker.order_id]
                # A partial maker is neither deleted nor reinserted.
            if not level.queue:
                self._remove_level(side, price, level, best=True)
        return fills, remaining

    def _rest(self, event, remaining):
        side = self.bids if event["side"] == "BUY" else self.asks
        price = event["price_ticks"]
        level = side.levels.get(price)
        if level is None:
            level = _OrderedLevel()
            side.levels[price] = level
            i = bisect_left(side.prices, side.sign * price)
            if self.counters is not None:
                self.counters.price_list_shifts += len(side.prices) - i
            side.prices.insert(i, side.sign * price)
        record = _Order(event, remaining)
        level.queue[record.order_id] = record
        self.orders[record.order_id] = record

    def snapshot(self):
        rows = []
        for side in (self.bids, self.asks):
            for signed_price in reversed(side.prices):
                for record in side.levels[side.sign * signed_price].queue.values():
                    rows.append({"order_id": record.order_id, "side": record.side,
                                 "price_ticks": record.price_ticks, "qty_units": record.qty_units,
                                 "arrival_seq": record.arrival_seq})
        return rows
