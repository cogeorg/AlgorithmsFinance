"""ATTACK MODELS of the planned revision B3r (own/attack). NOT an implementation, not
registered, not a proposal to merge: B3r does not exist yet, so these two plausible
readings of "B3 + heap rebuild when stale heap keys > live levels" are attacked.

Every live level owns exactly one heap key, so stale keys = len(heap) - len(levels) exactly;
no extra counter is needed. The check runs where keys become stale (_remove_level), per side.

B3rL rebuilds from the levels dict  -> iterates dict slots, including dead ones.
B3rF filters the existing heap list -> iterates live + stale keys only.
B3rT counts stale/live over BOTH sides but rebuilds only the side that changed.
"""
from heapq import heapify

from lob.book_b3 import OrderBookB3


class B3rL(OrderBookB3):
    rebuilds = 0

    def _keys(self, side):
        return [side.sign * p for p in side.levels]

    def _remove_level(self, side, price, level, *, best=False):
        super()._remove_level(side, price, level, best=best)
        if len(side.heap) - len(side.levels) > len(side.levels):
            side.heap = self._keys(side)
            heapify(side.heap)
            side.in_heap = set(side.heap)
            self.rebuilds += 1


class B3rF(B3rL):
    def _keys(self, side):
        levels, sign = side.levels, side.sign
        return [k for k in side.heap if sign * k in levels]


class B3rT(B3rF):
    def _remove_level(self, side, price, level, *, best=False):
        OrderBookB3._remove_level(self, side, price, level, best=best)
        live = len(self.bids.levels) + len(self.asks.levels)
        stale = len(self.bids.heap) + len(self.asks.heap) - live
        if stale > live:
            side.heap = self._keys(side)
            heapify(side.heap)
            side.in_heap = set(side.heap)
            self.rebuilds += 1
