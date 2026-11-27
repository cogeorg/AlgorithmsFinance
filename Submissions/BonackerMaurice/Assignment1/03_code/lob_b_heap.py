"""Version B-heap: shared B core + a heapq of price keys per side.

Key per side: bids -p, asks p, so the BEST price has the SMALLEST key and
sits at heap[0]. Emptied levels are deleted lazily: their key stays in the
heap ("stale") until it reaches the top or compaction rebuilds the heap
(07_docs/REVISIONS.md).

    best price      O(1) if heap[0] is live; each stale top popped O(log H)
    new level       heappush                        O(log H) worst
    level emptied   nothing now (lazy)              O(1)
    compaction      rebuild when H > 2 * levels + 16; heapify O(P), linear,
                    amortized O(1) per removed level. Keeps H <= 2P + 16.
"""

from heapq import heapify, heappop, heappush

from lob_b_common import OrderBookB

SLACK = 16


def _key(side, price):
    return -price if side == "BUY" else price


class OrderBook(OrderBookB):
    """Version B with a lazy-deletion heap price index."""

    def _init_index(self):
        self._heaps = {"BUY": [], "SELL": []}

    def _best_price(self, side):
        heap = self._heaps[side]
        side_levels = self.levels[side]
        sign = -1 if side == "BUY" else 1
        while heap:
            price = sign * heap[0]
            if price in side_levels:
                return price
            heappop(heap)                      # stale: level already emptied
        return None

    def _index_add(self, side, price):
        heappush(self._heaps[side], _key(side, price))

    def _index_remove(self, side, price):
        # Lazy: the key stays until it reaches the top. Compact if the heap
        # holds too many stale keys.
        side_levels = self.levels[side]
        if len(self._heaps[side]) > 2 * len(side_levels) + SLACK:
            heap = [_key(side, p) for p in side_levels]
            heapify(heap)
            self._heaps[side] = heap

    _index_remove_best = _index_remove

    def _ordered_prices(self, side):
        return sorted(self.levels[side], reverse=(side == "BUY"))

    def _check_index(self):
        for side in ("BUY", "SELL"):
            heap = self._heaps[side]
            side_levels = self.levels[side]
            assert len(heap) <= 2 * len(side_levels) + SLACK, \
                f"{side} heap too large: {len(heap)} for {len(side_levels)} levels"
            assert all(heap[(i - 1) // 2] <= heap[i] for i in range(1, len(heap))), \
                f"{side} heap order broken"
            keys = set(heap)
            assert all(_key(side, p) in keys for p in side_levels), \
                f"{side} occupied level missing from heap"
