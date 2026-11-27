"""Revision step 2 (kept for the measured revision history): step 1 + fused fast-path process(), Order objects.
The submitted Version B is lob/book_b.py (step 3: step 2 + 4-item list orders)."""
"""Version B: price levels with FIFO queues, a sorted price index and an order index.

Data organisation (standard library only):
  index        dict  order_id -> Order                       (active orders only)
  bid_levels   dict  price -> OrderedDict(order_id -> Order) (FIFO: insertion = arrival)
  ask_levels   dict  price -> OrderedDict(order_id -> Order)
  bid_keys     list  ascending bid prices      -> best bid = bid_keys[-1]
  ask_keys     list  ascending NEGATED ask prices -> best ask = -ask_keys[-1]
Storing both key lists so that the best price is the last element makes "remove best
level" a list.pop() in O(1).

Why OrderedDict instead of deque + lazy deletion: a cancel removes the order from its
queue immediately in O(1), so no tombstones exist and storage always equals the active
book (B orders, P levels), even under cancellation churn. The cost is a larger
per-entry memory footprint than a deque.

  duplicate check : dict lookup                                      O(1) expected
  insertion       : O(1) at an existing level; a new level adds a
                    bisect + list insert                             O(log P + P) memmove
  cancellation    : index pop + OrderedDict delete                   O(1); emptying a level
                    removes its key                                  O(log P + P) memmove
  market sell     : per fill O(1); per emptied level O(1)            O(F + L), L = levels visited
  memory          : O(B + P), no inactive entries, no trade history.
"""
from bisect import bisect_left, insort
from collections import OrderedDict

from lob.common import BUY, SELL, Order, OrderBookBase


class BookB(OrderBookBase):
    def __init__(self):
        super().__init__()
        self.index = {}
        self.bid_levels = {}
        self.ask_levels = {}
        self.bid_keys = []
        self.ask_keys = []

    def _is_live(self, order_id):
        return order_id in self.index

    # ---- fast path (second revision, driven by profiling) --------------------------
    def process(self, event):
        """Event dispatcher with a fused fast path for well-formed events.

        Profiling showed ~60% of Version B's time in the generic validate/dispatch code
        (eight dict.get calls and five helper calls per event). This path checks the
        same rules inline and matches/rests/cancels directly. It accepts an event only
        if OrderBookBase.validate would accept it; ANY doubt (missing field, wrong type,
        unknown type/side, nonincreasing seq, duplicate live id, dict/str subclasses)
        falls back to the shared, fully validating OrderBookBase.process, so rejection
        results and reasons are produced by exactly the same code as in Version A.
        """
        generic = OrderBookBase.process
        if type(event) is not dict:
            return generic(self, event)
        # Only field extraction is inside try: a KeyError raised later (while the book is
        # being changed) must never be swallowed and re-processed.
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
                if keys and -keys[-1] <= price:   # best ask at or below the limit: crosses
                    fills, qty = self._take(oid, qty, self.ask_levels, keys, -1, -price)
                else:
                    fills = []
                if qty:
                    order = Order(oid, BUY, price, qty, seq)
                    self.index[oid] = order
                    level = self.bid_levels.get(price)
                    if level is None:
                        level = self._add_level(self.bid_levels, self.bid_keys, price, price)
                    level[oid] = order
            elif side == SELL:
                keys = self.bid_keys
                if keys and keys[-1] >= price:     # best bid at or above the limit: crosses
                    fills, qty = self._take(oid, qty, self.bid_levels, keys, 1, price)
                else:
                    fills = []
                if qty:
                    order = Order(oid, SELL, price, qty, seq)
                    self.index[oid] = order
                    level = self.ask_levels.get(price)
                    if level is None:
                        level = self._add_level(self.ask_levels, self.ask_keys, price, -price)
                    level[oid] = order
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
            if order.side == BUY:
                levels, keys, key = self.bid_levels, self.bid_keys, order.price
            else:
                levels, keys, key = self.ask_levels, self.ask_keys, -order.price
            level = levels[order.price]
            del level[target]
            if not level:
                self._remove_level(levels, keys, order.price, key)
            return {"event_id": event_id, "target_order_id": target, "status": "cancelled",
                    "cancelled_qty_units": order.qty}

        return generic(self, event)  # unknown type: shared code produces the rejection

    # ---- level maintenance (rare relative to per-order work) -------------------------
    def _add_level(self, levels, keys, price, key):
        level = levels[price] = OrderedDict()
        insort(keys, key)
        return level

    def _remove_level(self, levels, keys, price, key):
        del levels[price]
        if keys[-1] == key:
            keys.pop()
        else:
            i = bisect_left(keys, key)
            del keys[i]

    # ---- matching ---------------------------------------------------------------------
    def _take(self, taker_id, qty, levels, keys, sign, min_key):
        """Trade against one side, best level first, FIFO inside a level.

        keys hold sign*price so the best level is keys[-1]; a level crosses while
        key >= min_key (min_key None = market order, everything crosses).
        """
        fills = []
        append = fills.append
        index = self.index
        while keys:
            key = keys[-1]
            if min_key is not None and key < min_key:
                break
            price = sign * key
            level = levels[price]  # never empty: empty levels are removed immediately
            while level:
                maker_id = next(iter(level))
                maker = level[maker_id]
                mq = maker.qty
                if mq > qty:  # partial maker keeps its queue position; incoming is done
                    maker.qty = mq - qty
                    append({"maker_id": maker_id, "taker_id": taker_id, "price_ticks": price, "qty_units": qty})
                    return fills, 0
                level.popitem(False)  # exhausted maker leaves the queue front
                del index[maker_id]
                append({"maker_id": maker_id, "taker_id": taker_id, "price_ticks": price, "qty_units": mq})
                qty -= mq
                if not qty:
                    if not level:
                        del levels[price]
                        keys.pop()
                    return fills, 0
            del levels[price]  # level emptied, incoming still has quantity: next level
            keys.pop()
        return fills, qty

    def _limit(self, order_id, side, price, qty, seq):
        if side == BUY:
            fills, rest = self._take(order_id, qty, self.ask_levels, self.ask_keys, -1, -price)
            levels, keys, key = self.bid_levels, self.bid_keys, price
        else:
            fills, rest = self._take(order_id, qty, self.bid_levels, self.bid_keys, 1, price)
            levels, keys, key = self.ask_levels, self.ask_keys, -price
        if rest:
            order = Order(order_id, side, price, rest, seq)
            self.index[order_id] = order
            level = levels.get(price)
            if level is None:
                level = self._add_level(levels, keys, price, key)
            level[order_id] = order  # appended at the back: later arrival, lower priority
        return fills, rest

    def _market_sell(self, order_id, qty):
        return self._take(order_id, qty, self.bid_levels, self.bid_keys, 1, None)

    def _cancel(self, target_order_id):
        order = self.index.pop(target_order_id, None)
        if order is None:
            return None
        if order.side == BUY:
            levels, keys, key = self.bid_levels, self.bid_keys, order.price
        else:
            levels, keys, key = self.ask_levels, self.ask_keys, -order.price
        level = levels[order.price]
        del level[target_order_id]
        if not level:
            self._remove_level(levels, keys, order.price, key)
        return order.qty

    # ---- inspection ---------------------------------------------------------------------
    def inspect_book(self):
        out = []
        for p in reversed(self.bid_keys):
            out.extend(o.as_dict() for o in self.bid_levels[p].values())
        for k in reversed(self.ask_keys):
            out.extend(o.as_dict() for o in self.ask_levels[-k].values())
        return out

    def storage_counts(self):
        return {
            "stored_orders": sum(map(len, self.bid_levels.values()))
                             + sum(map(len, self.ask_levels.values())),
            "index_entries": len(self.index),
            "stored_levels": len(self.bid_levels) + len(self.ask_levels),
            "level_keys": len(self.bid_keys) + len(self.ask_keys),
        }

    @classmethod
    def from_snapshot(cls, orders, last_seq):
        """Rebuild a fresh book from inspect_book() output (benchmark reset). O(B + P log P)."""
        book = cls()
        for d in sorted(orders, key=lambda d: d["arrival_seq"]):
            o = Order(d["order_id"], d["side"], d["price_ticks"], d["qty_units"], d["arrival_seq"])
            levels = book.bid_levels if o.side == BUY else book.ask_levels
            level = levels.get(o.price)
            if level is None:
                level = levels[o.price] = OrderedDict()
            level[o.order_id] = o
            book.index[o.order_id] = o
        book.bid_keys = sorted(book.bid_levels)
        book.ask_keys = sorted(-p for p in book.ask_levels)
        book.last_seq = last_seq
        return book

    def check_internal(self):
        """Structural invariants of Version B (used by tests, not on the hot path)."""
        seen = set()
        for side, levels, keys, sign in ((BUY, self.bid_levels, self.bid_keys, 1),
                                         (SELL, self.ask_levels, self.ask_keys, -1)):
            assert keys == sorted(keys) and len(set(keys)) == len(keys), "unsorted/duplicate keys"
            assert sorted(sign * k for k in keys) == sorted(levels), "keys != levels"
            for price, level in levels.items():
                assert level, f"empty level {price} kept"
                last_seq = 0
                for oid, o in level.items():
                    assert o.order_id == oid and o.side == side and o.price == price
                    assert o.qty > 0 and o.seq > last_seq, "queue not in arrival order"
                    last_seq = o.seq
                    assert self.index.get(oid) is o, "index mismatch"
                    assert oid not in seen, "order stored twice"
                    seen.add(oid)
        assert seen == set(self.index), "index has entries outside the levels"
