"""Version C (measured experiment, NOT the submitted revision): Version B with deque queues and
lazy cancellation. Measured by bench/run_version_c.py, tested by tests/test_version_c.py; see
REPORT.md section 7 for why it was not adopted.

Same order index, sorted key lists and fast-path dispatcher as Version B. Only the FIFO
queue per price level changes:
  level   = _Level: a deque of order lists with a `live` slot (count of live entries)
  order   = [qty, side, price, seq, order_id]    qty == 0 marks a cancelled (dead) entry
The deque holds the order *objects*, never ids: ids may be reused after an order is gone,
so an id-based lazy check could mistake a dead entry for a newer live order.

  cancel   : index pop + mark dead + live_count - 1            O(1)
             level with live_count 0 is deleted at once        (no stale entries survive it)
             compaction when dead entries outnumber live + 16  amortised O(1) per cancel
  matching : dead entries at the front are popped and skipped  amortised O(1) each
Stale entries are therefore bounded: at most live + 16 per level, i.e. O(B + P) overall.
"""
from bisect import bisect_left, insort
from collections import deque

from lob.common import BUY, SELL, OrderBookBase

QTY, SIDE, PRICE, SEQ, OID = 0, 1, 2, 3, 4
COMPACT_SLACK = 16


class _Level(deque):
    """FIFO queue of one price level; `live` counts entries that are not cancelled."""
    __slots__ = ("live",)


def _compact(level):
    """Drop dead entries in place (keeps the level object and its arrival order)."""
    kept = [o for o in level if o[QTY]]
    level.clear()
    level.extend(kept)


class BookC(OrderBookBase):
    def __init__(self):
        super().__init__()
        self.index = {}
        self.bid_levels = {}
        self.ask_levels = {}
        self.bid_keys = []
        self.ask_keys = []

    def _is_live(self, order_id):
        return order_id in self.index

    # ---- fast path (same rules as Version B; anything doubtful -> shared validating code) ----
    def process(self, event):
        generic = OrderBookBase.process
        if type(event) is not dict:
            return generic(self, event)
        try:
            seq = event["seq"]
            event_id = event["event_id"]
            kind = event["type"]
        except KeyError:
            return generic(self, event)
        if type(seq) is not int or seq <= self.last_seq or type(event_id) is not str or not event_id:
            return generic(self, event)

        if kind == "LIMIT":
            try:
                oid = event["order_id"]
                side = event["side"]
                price = event["price_ticks"]
                qty = event["qty_units"]
            except KeyError:
                return generic(self, event)
            if (type(oid) is not str or not oid or type(price) is not int or price <= 0
                    or type(qty) is not int or qty <= 0 or oid in self.index):
                return generic(self, event)
            if side == BUY:
                keys = self.ask_keys
                if keys and -keys[-1] <= price:
                    fills, qty = self._take(oid, qty, self.ask_levels, keys, -1, -price)
                else:
                    fills = []
                if qty:
                    order = [qty, BUY, price, seq, oid]
                    self.index[oid] = order
                    level = self.bid_levels.get(price)
                    if level is None:
                        level = self._add_level(self.bid_levels, self.bid_keys, price, price)
                    level.append(order)
                    level.live += 1
            elif side == SELL:
                keys = self.bid_keys
                if keys and keys[-1] >= price:
                    fills, qty = self._take(oid, qty, self.bid_levels, keys, 1, price)
                else:
                    fills = []
                if qty:
                    order = [qty, SELL, price, seq, oid]
                    self.index[oid] = order
                    level = self.ask_levels.get(price)
                    if level is None:
                        level = self._add_level(self.ask_levels, self.ask_keys, price, -price)
                    level.append(order)
                    level.live += 1
            else:
                return generic(self, event)
            self.last_seq = seq
            return {"event_id": event_id, "order_id": oid, "status": "resting" if qty else "filled",
                    "unfilled_qty_units": qty, "fills": fills}

        if kind == "MARKET_SELL":
            try:
                oid = event["order_id"]
                qty = event["qty_units"]
            except KeyError:
                return generic(self, event)
            if type(oid) is not str or not oid or type(qty) is not int or qty <= 0 or oid in self.index:
                return generic(self, event)
            if self.bid_keys:
                fills, rest = self._take(oid, qty, self.bid_levels, self.bid_keys, 1, None)
            else:
                fills, rest = [], qty
            self.last_seq = seq
            return {"event_id": event_id, "order_id": oid,
                    "status": "filled" if not rest else ("partial" if fills else "unfilled"),
                    "unfilled_qty_units": rest, "fills": fills}

        if kind == "CANCEL":
            target = event.get("target_order_id")
            if type(target) is not str or not target:
                return generic(self, event)
            order = self.index.pop(target, None)
            self.last_seq = seq
            if order is None:
                return {"event_id": event_id, "target_order_id": target, "status": "not_found",
                        "cancelled_qty_units": 0}
            q = order[0]
            order[0] = 0  # mark dead; the queue entry is removed lazily
            price = order[2]
            if order[1] == BUY:
                levels, keys, key = self.bid_levels, self.bid_keys, price
            else:
                levels, keys, key = self.ask_levels, self.ask_keys, -price
            level = levels[price]
            live = level.live - 1
            if live:
                level.live = live
                if len(level) > 2 * live + COMPACT_SLACK:
                    _compact(level)
            else:
                self._remove_level(levels, keys, price, key)
            return {"event_id": event_id, "target_order_id": target, "status": "cancelled",
                    "cancelled_qty_units": q}

        return generic(self, event)

    # ---- levels -------------------------------------------------------------------------------
    def _add_level(self, levels, keys, price, key):
        level = levels[price] = _Level()
        level.live = 0
        insort(keys, key)
        return level

    def _remove_level(self, levels, keys, price, key):
        del levels[price]
        if keys[-1] == key:
            keys.pop()
        else:
            del keys[bisect_left(keys, key)]

    # ---- matching --------------------------------------------------------------------------------
    def _take(self, taker_id, qty, levels, keys, sign, min_key):
        fills = []
        append = fills.append
        index = self.index
        while keys:
            key = keys[-1]
            if min_key is not None and key < min_key:
                break
            price = sign * key
            level = levels[price]  # level.live > 0, so a live entry exists in the queue
            while True:
                maker = level[0]
                mq = maker[0]
                if not mq:  # cancelled earlier: drop the stale entry
                    level.popleft()
                    continue
                if mq > qty:  # partial maker keeps its position; incoming is done
                    maker[0] = mq - qty
                    append({"maker_id": maker[4], "taker_id": taker_id, "price_ticks": price, "qty_units": qty})
                    return fills, 0
                level.popleft()
                del index[maker[4]]
                append({"maker_id": maker[4], "taker_id": taker_id, "price_ticks": price, "qty_units": mq})
                qty -= mq
                live = level.live - 1
                if not live:  # level exhausted: drop it with any stale entries it still holds
                    del levels[price]
                    keys.pop()
                    break
                level.live = live
                if len(level) > 2 * live + COMPACT_SLACK:  # fills shrank live: keep stale entries bounded
                    _compact(level)
                if not qty:
                    return fills, 0
            if not qty:
                return fills, 0
        return fills, qty

    # ---- generic hooks (used by the shared validating path) -------------------------------------
    def _limit(self, order_id, side, price, qty, seq):
        if side == BUY:
            fills, rest = self._take(order_id, qty, self.ask_levels, self.ask_keys, -1, -price)
            levels, keys, key = self.bid_levels, self.bid_keys, price
        else:
            fills, rest = self._take(order_id, qty, self.bid_levels, self.bid_keys, 1, price)
            levels, keys, key = self.ask_levels, self.ask_keys, -price
        if rest:
            order = [rest, side, price, seq, order_id]
            self.index[order_id] = order
            level = levels.get(price)
            if level is None:
                level = self._add_level(levels, keys, price, key)
            level.append(order)
            level.live += 1
        return fills, rest

    def _market_sell(self, order_id, qty):
        return self._take(order_id, qty, self.bid_levels, self.bid_keys, 1, None)

    def _cancel(self, target_order_id):
        order = self.index.pop(target_order_id, None)
        if order is None:
            return None
        q = order[QTY]
        order[QTY] = 0  # mark dead; the deque entry is removed lazily
        price = order[PRICE]
        if order[SIDE] == BUY:
            levels, keys, key = self.bid_levels, self.bid_keys, price
        else:
            levels, keys, key = self.ask_levels, self.ask_keys, -price
        level = levels[price]
        live = level.live - 1
        if not live:
            self._remove_level(levels, keys, price, key)
        else:
            level.live = live
            if len(level) > 2 * live + COMPACT_SLACK:  # dead entries dominate: compact once
                _compact(level)
        return q

    # ---- inspection -------------------------------------------------------------------------------
    def inspect_book(self):
        out = []
        for levels, prices in ((self.bid_levels, reversed(self.bid_keys)),
                               (self.ask_levels, (-k for k in reversed(self.ask_keys)))):
            for p in prices:
                out.extend({"order_id": o[OID], "side": o[SIDE], "price_ticks": o[PRICE], "qty_units": o[QTY],
                            "arrival_seq": o[SEQ]} for o in levels[p] if o[QTY])
        return out

    def storage_counts(self):
        levels = list(self.bid_levels.values()) + list(self.ask_levels.values())
        entries = sum(len(lv) for lv in levels)
        live = sum(lv.live for lv in levels)
        return {"stored_orders": live, "stale_entries": entries - live, "index_entries": len(self.index),
                "stored_levels": len(levels), "level_keys": len(self.bid_keys) + len(self.ask_keys)}

    @classmethod
    def from_snapshot(cls, orders, last_seq):
        book = cls()
        for d in sorted(orders, key=lambda d: d["arrival_seq"]):
            o = [d["qty_units"], d["side"], d["price_ticks"], d["arrival_seq"], d["order_id"]]
            levels = book.bid_levels if o[SIDE] == BUY else book.ask_levels
            level = levels.get(o[PRICE])
            if level is None:
                level = levels[o[PRICE]] = _Level()
                level.live = 0
            level.append(o)
            level.live += 1
            book.index[o[OID]] = o
        book.bid_keys = sorted(book.bid_levels)
        book.ask_keys = sorted(-p for p in book.ask_levels)
        book.last_seq = last_seq
        return book

    def check_internal(self):
        seen = set()
        for side, levels, keys, sign in ((BUY, self.bid_levels, self.bid_keys, 1),
                                         (SELL, self.ask_levels, self.ask_keys, -1)):
            assert keys == sorted(keys) and len(set(keys)) == len(keys), "unsorted/duplicate keys"
            assert sorted(sign * k for k in keys) == sorted(levels), "keys != levels"
            for price, dq in levels.items():
                live = dq.live
                live_entries = [o for o in dq if o[QTY]]
                assert live > 0 and len(live_entries) == live, "live count wrong or empty level kept"
                assert len(dq) - live <= live + COMPACT_SLACK + 1, "stale entries not bounded"
                last = 0
                for o in dq:
                    assert o[SEQ] > last, "queue not in arrival order"
                    last = o[SEQ]
                    if o[QTY]:
                        assert o[SIDE] == side and o[PRICE] == price and type(o[QTY]) is int and o[QTY] > 0
                        assert self.index.get(o[OID]) is o, "index mismatch"
                        assert o[OID] not in seen, "order stored twice"
                        seen.add(o[OID])
                    else:
                        assert self.index.get(o[OID]) is not o, "dead entry still indexed"
        assert seen == set(self.index), "index has entries outside the levels"
