"""B3r fallback: B3 plus a per-side heap rebuild (2026-11-22)."""
from heapq import heapify

from lob.book_b import OperationCounters
from lob.book_b3 import HeapOperationCounters, OrderBookB3


class RebuildOperationCounters(HeapOperationCounters):
    """Extra rebuild work, allocated only when operation counting is enabled."""
    __slots__ = ("heap_rebuilds", "heap_rebuild_keys_scanned", "heap_rebuild_stale_removed")
    _ALL_SLOTS = OperationCounters.__slots__ + HeapOperationCounters.__slots__ + __slots__

    def __init__(self):
        for name in self._ALL_SLOTS:
            setattr(self, name, 0)

    def as_dict(self):
        return {name: getattr(self, name) for name in self._ALL_SLOTS}


class OrderBookB3r(OrderBookB3):
    def __init__(self, *, count_operations=False):
        super().__init__()
        self.counters = RebuildOperationCounters() if count_operations else None

    def _remove_level(self, side, price, level, *, best=False):
        super()._remove_level(side, price, level, best=best)
        # Every live level owns exactly one key. Count only the changed side:
        # stale keys on the other side cannot be removed by this rebuild.
        live = len(side.levels)
        stale = len(side.heap) - live
        if stale > live and stale > 32:
            if self.counters is not None:
                self.counters.heap_rebuilds += 1
                self.counters.heap_rebuild_keys_scanned += len(side.heap)
                self.counters.heap_rebuild_stale_removed += stale
            # Iterate the compact list, never the levels dict's retained slots.
            # Fewer live than stale keys survive, so each discarded key can pay
            # for itself and at most one survivor. heapify/set rebuild are linear
            # (expected hashing), but one event can still pay this entire scan.
            side.heap = [key for key in side.heap if side.sign * key in side.levels]
            heapify(side.heap)
            side.in_heap = set(side.heap)
