"""Version B1, the first revision (preserved): price levels, best-price heaps and an order index.

This is the revision as first written. book_b.py keeps the same data organization and
removes constant-factor overhead; tuning.py measures the difference. B1 runs through the
same tests as A and B but is not part of the main benchmark.

Per side:
  levels    dict price -> OrderedDict(order_id -> order); the OrderedDict is the
            FIFO queue of that price and also supports removing any order in O(1).
  heap      binary heap of occupied prices (negated for bids), so the best price
            is heap[0]; in_heap is the set of prices currently in the heap.
Book-wide:
  _live   dict order_id -> order for duplicate checks and cancellation.

Price priority comes from the heap, time priority from queue order: arrival ranks
only increase, and a new order is appended at the tail of its queue.

Delayed cleanup is confined to the heaps. When a cancellation empties a level,
its heap entry stays behind ("stale") and is discarded when it reaches the top. A price is never pushed twice (in_heap), and
a heap is rebuilt from the occupied levels once it exceeds twice their number
plus HEAP_SLACK, so heap size stays O(P) and the rebuild is amortized O(1) per
cancellation. Queues and the order index never hold inactive orders.

Costs with P occupied prices on a side (dictionary operations are expected O(1)):
  passive insertion   O(1), or O(log P) when it opens a new price level
  each maker fill     O(1), plus O(log P) for each level emptied
  cancellation        O(1); amortized O(log P) if it empties a level (its stale heap
                      entry is popped later, or swept by a rebuild)
  space               O(B + P)
"""
from collections import OrderedDict
from heapq import heapify, heappop, heappush

from events import LimitOrderBook, BUY, SELL

HEAP_SLACK = 32          # stale heap entries tolerated beyond 2x occupied levels
SHRINK_MIN = 4096        # index peak below which releasing capacity is not worth it
SHRINK_FACTOR = 8        # release capacity once fewer than 1/8 of the peak remain


class _Order:
    __slots__ = ("order_id", "is_buy", "price", "qty", "seq")

    def __init__(self, order_id, is_buy, price, qty, seq):
        self.order_id = order_id
        self.is_buy = is_buy
        self.price = price
        self.qty = qty
        self.seq = seq


class _Side:
    """One side of the book. sign is -1 for bids (max-heap via negation), +1 for asks."""
    __slots__ = ("levels", "heap", "in_heap", "sign")

    def __init__(self, sign):
        self.levels = {}
        self.heap = []
        self.in_heap = set()
        self.sign = sign

    def best_price(self):
        """Best occupied price, or None. Discards stale heap tops on the way."""
        heap, levels, sign = self.heap, self.levels, self.sign
        while heap:
            price = heap[0] * sign
            if price in levels:
                return price
            heappop(heap)
            self.in_heap.discard(price)
        return None

    def queue(self, price):
        """The FIFO queue at price, opening the level (and its heap entry) if needed."""
        level = self.levels.get(price)
        if level is None:
            level = self.levels[price] = OrderedDict()
            if price not in self.in_heap:        # a stale entry for this price becomes valid again
                heappush(self.heap, price * self.sign)
                self.in_heap.add(price)
        return level

    def close_best(self, price):
        """Matching emptied the best level: remove the level and its heap top together."""
        del self.levels[price]
        heappop(self.heap)
        self.in_heap.discard(price)
        if len(self.heap) > 2 * len(self.levels) + HEAP_SLACK:    # added after test_stale_entries_
            self.rebuild_heap()                                   # stay_bounded_when_matching_... failed

    def close_cancelled(self, price):
        """A cancellation emptied a level anywhere in the book: its heap entry goes stale."""
        del self.levels[price]
        if len(self.heap) > 2 * len(self.levels) + HEAP_SLACK:
            self.rebuild_heap()

    def rebuild_heap(self):
        sign = self.sign
        self.heap = [price * sign for price in self.levels]
        heapify(self.heap)
        self.in_heap = set(self.levels)


class OrderBookB1(LimitOrderBook):
    version = "B1"
    side_class = _Side       # replaceable (the planted-bug tests substitute a broken subclass)

    def __init__(self):
        super().__init__()
        self._bids = self.side_class(-1)
        self._asks = self.side_class(+1)
        self._live = {}
        self._index_peak = 0     # largest index size since the last capacity release

    # -- matching
    def _match(self, side, limit, taker_buys, taker_id, qty, fills):
        """Trade against `side`, best price first, FIFO within a price; limit None = any price."""
        orders = self._live
        while qty:
            price = side.best_price()
            if price is None:
                break
            if limit is not None and (price > limit if taker_buys else price < limit):
                break
            level = side.levels[price]
            exhausted = 0
            for maker in level.values():             # arrival order
                available = maker.qty
                if available <= qty:
                    traded = available
                    exhausted += 1
                    del orders[maker.order_id]
                else:
                    traded = qty
                    maker.qty = available - qty      # keeps its place at the head
                qty -= traded
                fills.append({"maker_id": maker.order_id, "taker_id": taker_id,
                              "price_ticks": price, "qty_units": traded})
                if not qty:
                    break
            if exhausted == len(level):
                side.close_best(price)
            else:
                for _ in range(exhausted):
                    level.popitem(last=False)
        if self._index_peak > SHRINK_MIN and len(orders) * SHRINK_FACTOR < self._index_peak:
            self._release_capacity()
        return qty

    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        if is_buy:
            opposite, own = self._asks, self._bids
        else:
            opposite, own = self._bids, self._asks
        if opposite.levels:
            qty = self._match(opposite, price, is_buy, order_id, qty, fills)
        if qty:
            order = _Order(order_id, is_buy, price, qty, seq)
            own.queue(price)[order_id] = order
            orders = self._live
            orders[order_id] = order
            if len(orders) > self._index_peak:
                self._index_peak = len(orders)
        return qty

    def _market_sell(self, order_id, qty, fills):
        return self._match(self._bids, None, False, order_id, qty, fills)

    def _cancel(self, order_id):
        order = self._live.pop(order_id, None)
        if order is None:
            return 0
        side = self._bids if order.is_buy else self._asks
        level = side.levels[order.price]
        del level[order_id]
        if not level:
            side.close_cancelled(order.price)
        if self._index_peak > SHRINK_MIN and len(self._live) * SHRINK_FACTOR < self._index_peak:
            self._release_capacity()
        return order.qty

    def _release_capacity(self):
        """Python dictionaries keep their table after deletions; copy them once the book has
        shrunk to under 1/SHRINK_FACTOR of its peak. O(B) now, amortized O(1) per removal."""
        self._live = dict(self._live)
        for side in (self._bids, self._asks):
            side.levels = {price: OrderedDict(level) for price, level in side.levels.items()}
            side.rebuild_heap()
        self._index_peak = len(self._live)

    # -- inspection
    def InspectBook(self):
        rows = []
        for side, name, descending in ((self._bids, BUY, True), (self._asks, SELL, False)):
            for price in sorted(side.levels, reverse=descending):
                rows += [{"order_id": o.order_id, "side": name, "price_ticks": price, "qty_units": o.qty,
                          "arrival_seq": o.seq} for o in side.levels[price].values()]
        return rows

    def best_bid(self):
        return self._bids.best_price()

    def best_ask(self):
        return self._asks.best_price()

    def active_orders(self):
        return len(self._live)

    def price_levels(self):
        return len(self._bids.levels) + len(self._asks.levels)

    def storage_stats(self):
        sides = (self._bids, self._asks)
        queued = sum(len(level) for side in sides for level in side.levels.values())
        levels = sum(len(side.levels) for side in sides)
        heap = sum(len(side.heap) for side in sides)
        return {"active_orders": len(self._live), "id_index_entries": len(self._live),
                "queue_entries": queued, "price_levels": levels, "heap_entries": heap,
                "stale_heap_entries": heap - levels,
                "stored_entries": (len(self._live) + queued + levels + heap
                                   + sum(len(side.in_heap) for side in sides))}

    def check_invariants(self):
        """Raise AssertionError if the stored state is inconsistent (used by tests)."""
        seen = 0
        for side, is_buy in ((self._bids, True), (self._asks, False)):
            assert sorted(side.in_heap) == sorted(p * side.sign for p in side.heap), "heap/in_heap mismatch"
            assert all(side.heap[(i - 1) // 2] <= side.heap[i] for i in range(1, len(side.heap))), "heap order"
            assert len(side.heap) <= 2 * len(side.levels) + HEAP_SLACK, "stale heap entries not bounded"
            for price, level in side.levels.items():
                assert level, "empty level kept"
                assert price in side.in_heap, "occupied price missing from heap"
                previous = 0
                for order_id, order in level.items():
                    assert self._live.get(order_id) is order, "queued order not indexed exactly once"
                    assert order.order_id == order_id and order.price == price and order.is_buy is is_buy
                    assert type(order.qty) is int and order.qty > 0, "nonpositive resting quantity"
                    assert previous < order.seq <= self.last_seq, "queue not in arrival order"
                    previous = order.seq
                    seen += 1
        assert seen == len(self._live), "index holds an order that is in no queue"
        bid, ask = self.best_bid(), self.best_ask()
        assert bid is None or ask is None or bid < ask, "crossed book"
