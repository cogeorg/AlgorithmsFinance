"""Version B, the revision: price levels with FIFO queues, best-price heaps and an order index.

Data organization (the same idea as the first revision in book_b1.py, with less overhead):

  _levels    dict key -> OrderedDict(order_id -> record). key is the price for asks and
             the NEGATED price for bids, so both sides share one dictionary, the smaller
             key is always the better price, and a record needs no side field. The
             OrderedDict is that price's FIFO queue and removes any order in O(1).
  record     the list [remaining_qty, key, arrival_seq]; one per active order.
  _bid_heap, _ask_heap
             binary heaps of occupied keys, so heap[0] is the best price of that side.
             _in_heap is the set of keys currently in either heap.
  _live      dict order_id -> record, for duplicate checks and cancellation.

Price priority comes from the heaps, time priority from queue order: arrival ranks only
increase and a new order is appended at the tail of its queue.

Delayed cleanup is confined to the heaps. When a cancellation empties a level, its heap
entry stays behind ("stale") and is discarded when it reaches the top. A key is never
pushed twice (_in_heap). After every event the two heaps together hold at most
2 * (occupied levels) + HEAP_SLACK entries; when a cancellation or a match would exceed
that, both heaps are rebuilt from the occupied levels. A rebuild costs O(P) and removes
more than P stale entries, each created by one cancellation, so rebuilding is amortized
O(1) per cancellation. Queues and the order index never hold inactive orders.

Costs with P occupied prices (dictionary operations are expected O(1); a heap holds
O(P) entries, so one push or pop is O(log P)):
  passive insertion   O(1), or O(log P) when it opens a new price level
  each maker fill     O(1), plus O(log P) for each level emptied
  cancellation        O(1); amortized O(log P) if it empties a level, see below
  space               O(B + P) entries; table capacity is released only after the book
                      has shrunk to 1/SHRINK_FACTOR of its peak

A stale entry is created by exactly one cancellation that emptied a level, and is
removed exactly once: by a pop (O(log P)) when it reaches the heap top, or by a rebuild
(O(1) per entry). That cost is charged to the cancellation, which is what makes it
amortized O(log P). The operation that happens to meet stale entries pays for them in
real time: a single match or passive insertion can pop up to P + HEAP_SLACK of them, so
the per-operation bounds above are amortized, not worst-case.

What changed against book_b1.py, and why (measured by tuning.py):
  - signed keys and one level dictionary instead of two side objects: no method call to
    find the best price or a queue, and matching needs no "which side" branch;
  - a three-element list instead of an object with five attributes per order;
  - a passive order is recognised by comparing with heap[0] directly: a stale top can only
    be better than the true best price, so "top does not cross" already proves "no cross";
  - the peak used for releasing capacity is updated when orders leave, not when they arrive.
"""
from collections import OrderedDict
from heapq import heapify, heappop, heappush

from events import LimitOrderBook, BUY, SELL

HEAP_SLACK = 32          # stale heap entries tolerated beyond 2x occupied levels
SHRINK_MIN = 4096        # index peak below which releasing capacity is not worth it
SHRINK_FACTOR = 8        # release capacity once fewer than 1/8 of the peak remain

QTY, KEY, SEQ = 0, 1, 2


class OrderBookB(LimitOrderBook):
    version = "B"

    def __init__(self):
        super().__init__()           # creates self._live
        self._levels = {}
        self._bid_heap = []
        self._ask_heap = []
        self._in_heap = set()
        self._index_peak = 0         # largest index size noted since the last capacity release
                                     # (noted whenever orders can leave: in _match and _cancel)

    # -- matching
    def _match(self, heap, limit, taker_id, qty, fills):
        """Trade against the side whose heap is given while its best key is <= limit.

        Keys are prices for asks and negated prices for bids, so "key <= limit" means
        "ask <= buy limit" or "bid >= sell limit"; a market sell passes limit 0, which
        every (negative) bid key satisfies.
        """
        levels, live = self._levels, self._live
        if len(live) > self._index_peak:
            self._index_peak = len(live)
        while heap:
            key = heap[0]
            level = levels.get(key)
            if level is None:                        # stale entry left by a cancellation
                heappop(heap)
                self._in_heap.discard(key)
                continue
            if key > limit:
                break
            price = -key if key < 0 else key
            exhausted = 0
            for maker_id, record in level.items():   # arrival order
                available = record[QTY]
                if available <= qty:
                    exhausted += 1
                    del live[maker_id]
                    qty -= available
                    fills.append({"maker_id": maker_id, "taker_id": taker_id,
                                  "price_ticks": price, "qty_units": available})
                    if not qty:
                        break
                else:
                    record[QTY] = available - qty    # keeps its place at the head
                    fills.append({"maker_id": maker_id, "taker_id": taker_id,
                                  "price_ticks": price, "qty_units": qty})
                    qty = 0
                    break
            if exhausted == len(level):              # level emptied: it is the heap top, remove both
                del levels[key]
                heappop(heap)
                self._in_heap.discard(key)
            else:
                remove_head = level.popitem
                for _ in range(exhausted):
                    remove_head(False)
            if not qty:
                break
        if self._index_peak > SHRINK_MIN and len(live) * SHRINK_FACTOR < self._index_peak:
            self._release_capacity()
        elif len(self._bid_heap) + len(self._ask_heap) > 2 * len(levels) + HEAP_SLACK:
            self._rebuild_heaps()
        return qty

    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        if is_buy:
            opposite, limit = self._ask_heap, price
        else:
            opposite, limit = self._bid_heap, -price
        if opposite and opposite[0] <= limit:        # see module docstring: safe with a stale top
            qty = self._match(opposite, limit, order_id, qty, fills)
        if qty:
            key = -limit
            record = [qty, key, seq]
            level = self._levels.get(key)
            if level is None:
                self._levels[key] = level = OrderedDict()
                if key not in self._in_heap:         # a stale entry for this key becomes valid again
                    heappush(self._bid_heap if is_buy else self._ask_heap, key)
                    self._in_heap.add(key)
            level[order_id] = record
            self._live[order_id] = record
        return qty

    def _market_sell(self, order_id, qty, fills):
        return self._match(self._bid_heap, 0, order_id, qty, fills)

    def _cancel(self, order_id):
        live = self._live
        record = live.pop(order_id, None)
        if record is None:
            return 0
        levels = self._levels
        key = record[KEY]
        level = levels[key]
        del level[order_id]
        if not level:
            del levels[key]                          # its heap entry goes stale
            if len(self._bid_heap) + len(self._ask_heap) > 2 * len(levels) + HEAP_SLACK:
                self._rebuild_heaps()
        remaining = len(live)
        if remaining >= self._index_peak:
            self._index_peak = remaining + 1
        elif self._index_peak > SHRINK_MIN and remaining * SHRINK_FACTOR < self._index_peak:
            self._release_capacity()
        return record[QTY]

    def _rebuild_heaps(self):
        self._bid_heap = [key for key in self._levels if key < 0]
        self._ask_heap = [key for key in self._levels if key > 0]
        heapify(self._bid_heap)
        heapify(self._ask_heap)
        self._in_heap = set(self._levels)

    def _release_capacity(self):
        """Python dictionaries keep their table after deletions; copy them once the book has
        shrunk to under 1/SHRINK_FACTOR of its peak. O(B) now, amortized O(1) per removal."""
        self._live = dict(self._live)
        self._levels = {key: OrderedDict(level) for key, level in self._levels.items()}
        self._rebuild_heaps()
        self._index_peak = len(self._live)

    # -- inspection
    def InspectBook(self):
        rows = []
        for key in sorted(self._levels):             # bids (negative keys) by falling price, then asks rising
            side, price = (BUY, -key) if key < 0 else (SELL, key)
            rows += [{"order_id": order_id, "side": side, "price_ticks": price, "qty_units": record[QTY],
                      "arrival_seq": record[SEQ]} for order_id, record in self._levels[key].items()]
        return rows

    def _best(self, heap):
        while heap:
            if heap[0] in self._levels:
                return heap[0]
            self._in_heap.discard(heappop(heap))
        return None

    def best_bid(self):
        key = self._best(self._bid_heap)
        return None if key is None else -key

    def best_ask(self):
        return self._best(self._ask_heap)

    def active_orders(self):
        return len(self._live)

    def price_levels(self):
        return len(self._levels)

    def storage_stats(self):
        queued = sum(len(level) for level in self._levels.values())
        levels = len(self._levels)
        heap = len(self._bid_heap) + len(self._ask_heap)
        return {"active_orders": len(self._live), "id_index_entries": len(self._live),
                "queue_entries": queued, "price_levels": levels, "heap_entries": heap,
                "stale_heap_entries": heap - levels,
                "stored_entries": len(self._live) + queued + levels + heap + len(self._in_heap)}

    def check_invariants(self):
        """Raise AssertionError if the stored state is inconsistent (used by tests)."""
        bids, asks = self._bid_heap, self._ask_heap
        assert all(key < 0 for key in bids) and all(key > 0 for key in asks), "key in the wrong heap"
        assert len(bids) + len(asks) == len(self._in_heap) and set(bids) | set(asks) == self._in_heap, \
            "heap/in_heap mismatch"
        for heap in (bids, asks):
            assert all(heap[(i - 1) // 2] <= heap[i] for i in range(1, len(heap))), "heap order"
        assert len(bids) + len(asks) <= 2 * len(self._levels) + HEAP_SLACK, "stale heap entries not bounded"
        seen = 0
        for key, level in self._levels.items():
            assert type(key) is int and key != 0, "invalid level key"
            assert level, "empty level kept"
            assert key in self._in_heap, "occupied price missing from heap"
            previous = 0
            for order_id, record in level.items():
                assert self._live.get(order_id) is record, "queued order not indexed exactly once"
                assert record[KEY] == key, "order queued at the wrong price"
                assert type(record[QTY]) is int and record[QTY] > 0, "nonpositive resting quantity"
                assert previous < record[SEQ] <= self.last_seq, "queue not in arrival order"
                previous = record[SEQ]
                seen += 1
        assert seen == len(self._live), "index holds an order that is in no queue"
        bid, ask = self.best_bid(), self.best_ask()
        assert bid is None or ask is None or bid < ask, "crossed book"
