"""Version A, the transparent baseline: two unsorted lists of individual orders.

Every resting order is one record [priority_key, arrival_seq, remaining_qty, order_id]
appended to the list of its side in arrival order. priority_key is the price for
asks and the negated price for bids, so on either side the smallest record is the
best price and, at equal price, the earliest arrival. The best order is found by
scanning the whole side with min(); an exhausted or cancelled order is removed
with list.remove(), another scan. An identifier dictionary answers "is this
order active?" and locates the record of a cancel target.

Costs with B_side active orders on the scanned side:
  passive insertion   O(B_opposite)   one min() scan to test for crossing
  each maker fill     O(B_side)       min() scan, plus remove() if exhausted
  cancellation        O(B_side)       list.remove() scan and shift
  space               O(B)            no inactive entries are kept
"""
from events import LimitOrderBook, BUY, SELL

KEY, SEQ, QTY, ID = 0, 1, 2, 3


class OrderBookA(LimitOrderBook):
    version = "A"

    def __init__(self):
        super().__init__()
        self._bids = []     # records with key = -price_ticks
        self._asks = []     # records with key = +price_ticks
        self._live = {}     # order_id -> the same record object (an index, not a second copy)

    # -- scans (separate methods so that instrumented.py can count them)
    def _best(self, side):
        return min(side)                 # compares key, then arrival_seq (unique)

    def _remove(self, side, record):
        side.remove(record)

    # -- matching
    def _match(self, side, limit_key, taker_id, qty, fills):
        """Trade against `side` while its best key is within limit_key (None = any price)."""
        while qty and side:
            best = self._best(side)
            key = best[KEY]
            if limit_key is not None and key > limit_key:
                break
            traded = best[QTY] if best[QTY] < qty else qty
            best[QTY] -= traded
            qty -= traded
            fills.append({"maker_id": best[ID], "taker_id": taker_id,
                          "price_ticks": key if key > 0 else -key, "qty_units": traded})
            if best[QTY] == 0:
                self._remove(side, best)
                del self._live[best[ID]]
        return qty

    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        if is_buy:      # asks qualify while ask <= limit
            qty = self._match(self._asks, price, order_id, qty, fills)
            own, key = self._bids, -price
        else:           # bids qualify while bid >= limit, i.e. -bid <= -limit
            qty = self._match(self._bids, -price, order_id, qty, fills)
            own, key = self._asks, price
        if qty:
            record = [key, seq, qty, order_id]
            own.append(record)
            self._live[order_id] = record
        return qty

    def _market_sell(self, order_id, qty, fills):
        return self._match(self._bids, None, order_id, qty, fills)

    def _cancel(self, order_id):
        record = self._live.pop(order_id, None)
        if record is None:
            return 0
        self._remove(self._bids if record[KEY] < 0 else self._asks, record)
        return record[QTY]

    # -- inspection
    def InspectBook(self):
        rows = [{"order_id": r[ID], "side": BUY, "price_ticks": -r[KEY], "qty_units": r[QTY],
                 "arrival_seq": r[SEQ]} for r in sorted(self._bids)]
        rows += [{"order_id": r[ID], "side": SELL, "price_ticks": r[KEY], "qty_units": r[QTY],
                  "arrival_seq": r[SEQ]} for r in sorted(self._asks)]
        return rows

    def best_bid(self):
        return -min(self._bids)[KEY] if self._bids else None

    def best_ask(self):
        return min(self._asks)[KEY] if self._asks else None

    def active_orders(self):
        return len(self._live)

    def price_levels(self):
        """Occupied prices on both sides. O(B): intended for inspection, not the hot path."""
        return len({r[KEY] for r in self._bids}) + len({r[KEY] for r in self._asks})

    def storage_stats(self):
        return {"active_orders": len(self._live), "bid_list_entries": len(self._bids),
                "ask_list_entries": len(self._asks), "id_index_entries": len(self._live),
                "stored_entries": len(self._bids) + len(self._asks) + len(self._live)}

    def check_invariants(self):
        """Raise AssertionError if the stored state is inconsistent (used by tests)."""
        records = self._bids + self._asks
        assert len(records) == len(self._live), "list and identifier index differ in size"
        assert all(self._live.get(r[ID]) is r for r in records), "record not indexed exactly once"
        assert all(r[KEY] < 0 for r in self._bids) and all(r[KEY] > 0 for r in self._asks), "order on wrong side"
        assert all(type(r[QTY]) is int and r[QTY] > 0 for r in records), "nonpositive resting quantity"
        for side in (self._bids, self._asks):
            assert all(a[SEQ] < b[SEQ] for a, b in zip(side, side[1:])), "list not in arrival order"
        assert all(r[SEQ] <= self.last_seq for r in records), "arrival rank beyond last accepted seq"
        if self._bids and self._asks:
            assert self.best_bid() < self.best_ask(), "crossed book"
