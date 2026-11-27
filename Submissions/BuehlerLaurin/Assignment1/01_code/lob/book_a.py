"""Version A: transparent baseline (unsorted list per side + scan, SPEC.md Q15).

Each side's list stays in arrival order. Prices are unsorted: every selection
scans the whole opposite side. There is no id index, cached depth or history.
"""
from lob.validation import rejection, validate


class OrderBookA:
    """Version A order book. Public API as in SPEC.md (Interface)."""

    def __init__(self):
        self.bids = []
        self.asks = []
        self.last_seq = 0

    def process(self, event):
        """Validate `event`, route it by its type and return the result dict."""
        return self._process(event)

    def AddLimitOrder(self, event):  # noqa: N802 - name required by the assignment
        return self._process(event, expected_type="LIMIT")

    def CancelOrder(self, event):  # noqa: N802 - name required by the assignment
        return self._process(event, expected_type="CANCEL")

    def FillMarketSell(self, event):  # noqa: N802 - name required by the assignment
        return self._process(event, expected_type="MARKET_SELL")

    def _process(self, event, expected_type=None):
        # Finish all validation before changing either book state or last_seq.
        reason = validate(event, self.last_seq, self._is_live, expected_type)
        if reason is not None:
            return rejection(event, reason)
        self.last_seq = event["seq"]
        if event["type"] == "CANCEL":
            return self._cancel(event)
        return self._submit(event)

    def _is_live(self, order_id):
        # A deliberately uses a scan, including for duplicate validation.
        for orders in (self.bids, self.asks):
            for order in orders:
                if order["order_id"] == order_id:
                    return True
        return False

    def _cancel(self, event):
        # Locate the target, capture its remaining quantity, then delete it.
        for orders in (self.bids, self.asks):
            for i, order in enumerate(orders):
                if order["order_id"] == event["target_order_id"]:
                    qty = order["qty_units"]
                    del orders[i]
                    return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                            "status": "cancelled", "cancelled_qty_units": qty}
        return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                "status": "not_found", "cancelled_qty_units": 0}

    def _submit(self, event):
        is_limit = event["type"] == "LIMIT"
        side = event["side"] if is_limit else "SELL"
        limit = event["price_ticks"] if is_limit else None
        fills, remaining = self._match(event, side, limit)
        if is_limit:
            if remaining > 0:
                self._rest(event, remaining)
            status = "resting" if remaining > 0 else "filled"
        else:
            # A market residual is returned, then discarded; it never rests.
            status = "filled" if remaining == 0 else ("partial" if fills else "unfilled")
        return {"event_id": event["event_id"], "order_id": event["order_id"], "status": status,
                "unfilled_qty_units": remaining, "fills": fills}

    def _best_index(self, orders, side):
        """Scan for the best price; keep the earliest list position on a tie."""
        best = None
        for i, order in enumerate(orders):
            if best is None:
                best = i
                continue
            price, best_price = order["price_ticks"], orders[best]["price_ticks"]
            if (side == "BUY" and price > best_price) or (side == "SELL" and price < best_price):
                best = i
        return best

    def _match(self, event, side, limit):
        """Repeatedly scan, fill at the maker price, and remove exhausted makers."""
        opposite = self.asks if side == "BUY" else self.bids
        opposite_side = "SELL" if side == "BUY" else "BUY"
        remaining, fills = event["qty_units"], []
        while remaining > 0:
            i = self._best_index(opposite, opposite_side)
            if i is None:
                break
            maker = opposite[i]
            price = maker["price_ticks"]
            # With no limit (market sell), every bid is eligible.
            if limit is not None:
                if (side == "BUY" and price > limit) or (side == "SELL" and price < limit):
                    break
            qty = min(remaining, maker["qty_units"])
            fills.append({"maker_id": maker["order_id"], "taker_id": event["order_id"],
                          "price_ticks": price, "qty_units": qty})
            remaining -= qty
            maker["qty_units"] -= qty
            if maker["qty_units"] == 0:
                del opposite[i]
            # A surviving maker stays in place, preserving its FIFO priority.
        return fills, remaining

    def _rest(self, event, remaining):
        # Copy only the book fields: never store or mutate the caller's dict.
        order = {"order_id": event["order_id"], "side": event["side"],
                 "price_ticks": event["price_ticks"], "qty_units": remaining,
                 "arrival_seq": event["seq"]}
        orders = self.bids if event["side"] == "BUY" else self.asks
        orders.append(order)

    def snapshot(self):
        """Active orders in canonical order (bids price desc, asks price asc, then arrival)."""
        bids = sorted(self.bids, key=lambda r: (-r["price_ticks"], r["arrival_seq"]))
        asks = sorted(self.asks, key=lambda r: (r["price_ticks"], r["arrival_seq"]))
        return [dict(order) for orders in (bids, asks) for order in orders]

    def best_bid(self):
        i = self._best_index(self.bids, "BUY")
        return self.bids[i]["price_ticks"] if i is not None else None

    def best_ask(self):
        i = self._best_index(self.asks, "SELL")
        return self.asks[i]["price_ticks"] if i is not None else None
