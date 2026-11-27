"""B3: B1's compacted FIFO deques with a lazy heap of prices per side.

Bid heap keys are negated; ask keys are positive. in_heap prevents duplicate
keys when a deleted level is recreated before its old heap key is popped.
Stale heap prices are removed only at the root; there is no heap compaction.
"""
from heapq import heappop, heappush

from lob.book_b import OperationCounters, OrderBookB, _Level, _Order


class _HeapSide:
    __slots__ = ("levels", "heap", "in_heap", "sign")

    def __init__(self, sign):
        self.levels = {}
        self.heap = []
        self.in_heap = set()
        self.sign = sign


class HeapOperationCounters(OperationCounters):
    """B1 counters plus heap work on accepted-event paths (not quote cleanup)."""
    __slots__ = ("heap_pushes", "heap_pops", "heap_stale_pops", "heap_entry_peak")

    def __init__(self):
        for name in OperationCounters.__slots__ + self.__slots__:
            setattr(self, name, 0)

    def as_dict(self):
        return {name: getattr(self, name) for name in OperationCounters.__slots__ + self.__slots__}


class OrderBookB3(OrderBookB):
    """Shared B1 public/validation/result paths; lazy heap price selection."""

    def __init__(self, *, count_operations=False):
        self.orders = {}
        self.bids = _HeapSide(-1)
        self.asks = _HeapSide(1)
        self.last_seq = 0
        self.counters = HeapOperationCounters() if count_operations else None

    def _best_price(self, side, *, count=False):
        c = self.counters if count else None
        while side.heap:
            key = side.heap[0]
            price = side.sign * key
            if price in side.levels:
                return price
            heappop(side.heap)
            side.in_heap.remove(key)
            if c is not None:
                c.heap_pops += 1
                c.heap_stale_pops += 1
        return None

    def _remove_level(self, side, price, level, *, best=False):
        # No heap search/removal here: leave the key in heap and in_heap.
        del side.levels[price]
        if self.counters is not None:
            self.counters.stale_discarded += level.stale

    def _match(self, event, incoming_side, limit):
        side = self.asks if incoming_side == "BUY" else self.bids
        remaining, fills = event["qty_units"], []
        c = self.counters
        while remaining > 0:
            price = self._best_price(side, count=True)
            if price is None:
                break
            level = side.levels[price]
            if c is not None:
                c.levels_visited += 1
            if limit is not None:
                if (incoming_side == "BUY" and price > limit) or (incoming_side == "SELL" and price < limit):
                    break
            while remaining > 0 and level.live > 0:
                while not level.queue[0].alive:
                    level.queue.popleft()
                    level.stale -= 1
                    if c is not None:
                        c.stale_skipped += 1
                maker = level.queue[0]
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
                    level.queue.popleft()
                    del self.orders[maker.order_id]
                    level.live -= 1
            if level.live == 0:
                self._remove_level(side, price, level, best=True)
            else:
                self._compact(level)
        return fills, remaining

    def _rest(self, event, remaining):
        side = self.bids if event["side"] == "BUY" else self.asks
        price = event["price_ticks"]
        level = side.levels.get(price)
        if level is None:
            level = _Level()
            side.levels[price] = level
            key = side.sign * price
            if key not in side.in_heap:
                heappush(side.heap, key)
                side.in_heap.add(key)
                if self.counters is not None:
                    self.counters.heap_pushes += 1
                    self.counters.heap_entry_peak = max(
                        self.counters.heap_entry_peak, len(self.bids.heap) + len(self.asks.heap))
        record = _Order(event, remaining)
        level.queue.append(record)
        level.live += 1
        self.orders[record.order_id] = record

    def snapshot(self):
        # Inspection sorts live level prices, never the heap's stale entries.
        rows = []
        for side in (self.bids, self.asks):
            for price in sorted(side.levels, reverse=(side.sign == -1)):
                for record in side.levels[price].queue:
                    if record.alive:
                        rows.append({"order_id": record.order_id, "side": record.side,
                                     "price_ticks": record.price_ticks, "qty_units": record.qty_units,
                                     "arrival_seq": record.arrival_seq})
        return rows

    def best_bid(self):
        return self._best_price(self.bids)

    def best_ask(self):
        return self._best_price(self.asks)
