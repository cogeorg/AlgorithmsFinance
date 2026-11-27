"""Operation counters for diagnostic runs. Never used in timing or memory measurements.

The counting subclasses run the measured engines' code unchanged, so results are
identical. Version A's two scans are separate methods and are wrapped directly.
Version B's hot path has no such methods (that is part of its tuning), so its heap
work is counted by replacing book_b's heappush and heappop with counting wrappers
for the duration of one operation; every real heap call is therefore counted,
whatever happens inside the operation (rebuilds and capacity releases included).
"""
from collections import Counter

import book_b
from book_a import OrderBookA
from book_b import OrderBookB


class CountingBookA(OrderBookA):
    """records_examined_* is the number of list elements a scan had to look at."""

    def __init__(self):
        super().__init__()
        self.counters = Counter()

    def _best(self, side):
        self.counters["best_scans"] += 1
        self.counters["records_examined_best"] += len(side)      # min() reads every record
        return min(side)

    def _remove(self, side, record):
        position = side.index(record)                            # what list.remove() searches
        self.counters["removals"] += 1
        self.counters["records_examined_remove"] += position + 1
        self.counters["records_shifted"] += len(side) - position - 1
        del side[position]


class CountingBookB(OrderBookB):
    """heap_pushes and heappop_calls are real calls. A pop either removes the level that
    matching just emptied (heap_pops) or discards a stale entry (stale_heap_discards)."""

    def __init__(self):
        super().__init__()
        self.counters = Counter()
        self._counting = False

    def _counted(self, operation, *args):
        if self._counting:                       # already inside a counted operation
            return operation(*args)
        counters, real_push, real_pop = self.counters, book_b.heappush, book_b.heappop

        def counting_push(heap, item):
            counters["heap_pushes"] += 1
            real_push(heap, item)

        def counting_pop(heap):
            counters["heappop_calls"] += 1
            return real_pop(heap)

        book_b.heappush, book_b.heappop, self._counting = counting_push, counting_pop, True
        try:
            return operation(*args)
        finally:
            book_b.heappush, book_b.heappop, self._counting = real_push, real_pop, False

    def _add_limit(self, *args):
        return self._counted(super()._add_limit, *args)

    def _market_sell(self, *args):
        return self._counted(super()._market_sell, *args)

    def _match(self, heap, limit, taker_id, qty, fills):
        levels_before, pops_before = len(self._levels), self.counters["heappop_calls"]
        unfilled = self._counted(super()._match, heap, limit, taker_id, qty, fills)
        emptied = levels_before - len(self._levels)          # matching only ever removes levels
        self.counters["match_calls"] += 1
        self.counters["levels_emptied_by_matching"] += emptied
        self.counters["heap_pops"] += emptied
        self.counters["stale_heap_discards"] += self.counters["heappop_calls"] - pops_before - emptied
        return unfilled

    def _cancel(self, order_id):
        before = len(self._levels)
        removed = self._counted(super()._cancel, order_id)
        self.counters["levels_emptied_by_cancel"] += before - len(self._levels)
        return removed

    def _best(self, heap):                       # best_bid / best_ask also discard stale tops
        pops_before = self.counters["heappop_calls"]
        key = self._counted(super()._best, heap)
        self.counters["stale_heap_discards"] += self.counters["heappop_calls"] - pops_before
        return key

    def _rebuild_heaps(self):
        self.counters["heap_rebuilds"] += 1
        self.counters["heap_entries_rebuilt"] += len(self._levels)
        super()._rebuild_heaps()

    def _release_capacity(self):
        self.counters["capacity_releases"] += 1
        super()._release_capacity()


COUNTING = {"A": CountingBookA, "B": CountingBookB}
