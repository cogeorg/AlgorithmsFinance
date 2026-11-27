"""Version B-sorted: shared B core + a sorted list of price keys per side.

Key per side: bids p, asks -p, so the BEST price always has the LARGEST key
and sits at the END of the ascending list (07_docs/REVISIONS.md).

    best price               keys[-1]                       O(1) worst
    new level                bisect.insort                  O(log P) search + O(P) shift
    best level exhausted     keys.pop()                     O(1) amortized
    level emptied by cancel  del keys[bisect_left(...)]     O(log P) + O(P) shift
"""

from bisect import bisect_left, insort

from lob_b_common import OrderBookB


def _key(side, price):
    return price if side == "BUY" else -price


class OrderBook(OrderBookB):
    """Version B with a sorted-list price index."""

    def _init_index(self):
        self._keys = {"BUY": [], "SELL": []}   # ascending; best at the end

    def _best_price(self, side):
        keys = self._keys[side]
        if not keys:
            return None
        k = keys[-1]
        return k if side == "BUY" else -k

    def _index_add(self, side, price):
        insort(self._keys[side], _key(side, price))

    def _index_remove_best(self, side, price):
        keys = self._keys[side]
        assert keys[-1] == _key(side, price), "emptied level is not the best"
        keys.pop()

    def _index_remove(self, side, price):
        keys = self._keys[side]
        del keys[bisect_left(keys, _key(side, price))]

    def _ordered_prices(self, side):
        sign = 1 if side == "BUY" else -1
        return [sign * k for k in reversed(self._keys[side])]

    def _check_index(self):
        for side in ("BUY", "SELL"):
            keys = self._keys[side]
            expected = sorted(_key(side, p) for p in self.levels[side])
            assert keys == expected, f"{side} key list != occupied levels"
