"""Version A: transparent baseline.

Data organisation: one Python list per side holding Order objects in arrival order
(appends only, so list order == seq order). There is no index and no price structure:
every lookup is a linear scan.

  find best order : scan the side; strict comparison keeps the first (= earliest) order
                    at the best price, which is exactly price-time priority.  O(B_side)
  duplicate check : scan both sides for the order_id.                         O(B)
  insertion       : duplicate check + best-opposite check + append.            O(B)
  cancellation    : scan for the id, then list deletion (shifts the tail).     O(B)
  market sell     : per fill one best-order scan + possible deletion.          O(F * B)
  memory          : O(B) order objects; nothing is kept after fill or cancel.
"""
from lob.common import BUY, SELL, Order, OrderBookBase


class BookA(OrderBookBase):
    def __init__(self):
        super().__init__()
        self.bids = []  # resting BUY orders, arrival order
        self.asks = []  # resting SELL orders, arrival order

    # ---- searches (linear) ----------------------------------------------------------------
    def _is_live(self, order_id):
        for o in self.bids:
            if o.order_id == order_id:
                return True
        for o in self.asks:
            if o.order_id == order_id:
                return True
        return False

    def _best_index(self, orders, highest):
        """Index of the best order (highest/lowest price, earliest at that price) or -1."""
        best_i = -1
        best_p = None
        if highest:
            for i, o in enumerate(orders):
                if best_p is None or o.price > best_p:
                    best_p, best_i = o.price, i
        else:
            for i, o in enumerate(orders):
                if best_p is None or o.price < best_p:
                    best_p, best_i = o.price, i
        return best_i

    # ---- matching -----------------------------------------------------------------------------
    def _match(self, taker_id, taker_side, qty, limit):
        """Trade against the opposite side while it crosses; mutate makers in place."""
        book = self.asks if taker_side == BUY else self.bids
        fills = []
        while qty > 0 and book:
            i = self._best_index(book, highest=(taker_side == SELL))
            maker = book[i]
            if limit is not None and (maker.price > limit if taker_side == BUY else maker.price < limit):
                break  # best opposite price no longer crosses
            q = qty if qty < maker.qty else maker.qty
            fills.append({"maker_id": maker.order_id, "taker_id": taker_id,
                          "price_ticks": maker.price, "qty_units": q})
            qty -= q
            maker.qty -= q
            if maker.qty == 0:
                del book[i]  # exhausted maker leaves; a partial maker keeps its position
        return fills, qty

    def _limit(self, order_id, side, price, qty, seq):
        fills, rest = self._match(order_id, side, qty, price)
        if rest:
            (self.bids if side == BUY else self.asks).append(Order(order_id, side, price, rest, seq))
        return fills, rest

    def _market_sell(self, order_id, qty):
        return self._match(order_id, SELL, qty, None)

    def _cancel(self, target_order_id):
        for book in (self.bids, self.asks):
            for i, o in enumerate(book):
                if o.order_id == target_order_id:
                    del book[i]
                    return o.qty
        return None

    # ---- inspection -------------------------------------------------------------------------
    def inspect_book(self):
        bids = sorted(self.bids, key=lambda o: (-o.price, o.seq))
        asks = sorted(self.asks, key=lambda o: (o.price, o.seq))
        return [o.as_dict() for o in bids] + [o.as_dict() for o in asks]

    def storage_counts(self):
        return {"stored_orders": len(self.bids) + len(self.asks), "stored_levels": 0}

    @classmethod
    def from_snapshot(cls, orders, last_seq):
        """Rebuild a fresh book from inspect_book() output (benchmark reset). O(B log B)."""
        book = cls()
        for d in sorted(orders, key=lambda d: d["arrival_seq"]):
            o = Order(d["order_id"], d["side"], d["price_ticks"], d["qty_units"], d["arrival_seq"])
            (book.bids if o.side == BUY else book.asks).append(o)
        book.last_seq = last_seq
        return book
