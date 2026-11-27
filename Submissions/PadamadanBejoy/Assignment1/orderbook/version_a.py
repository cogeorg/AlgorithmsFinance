from orderbook.validation import validate
"""Version A: simple baseline order book (one list of orders)."""


class OrderBook:
    def __init__(self):
        self.orders = []      # every waiting order, as a dict (same shape as snapshot)
        self.last_seq = 0     # seq of the last accepted event (for validation later)

    def process_event(self, event):
        """Dispatcher: look at event['type'] and call the right method."""
        reason = validate(event, self.last_seq, self.is_live)
        if reason is not None:
            return {"event_id": event.get("event_id") if isinstance(event, dict) else None,
                    "status": "rejected", "reason": reason}
        self.last_seq = event["seq"]
        if event["type"] == "LIMIT":
            return self.AddLimitOrder(event)
        elif event["type"] == "MARKET_SELL":
            return self.FillMarketSell(event)
        elif event["type"] == "CANCEL":
            return self.CancelOrder(event)
    def is_live(self, order_id):
        for order in self.orders:
            if order["order_id"] == order_id:
                return True
        return False

    def _match(self, taker_id, side, remaining, limit_price):
        """Trade an incoming order against the best waiting orders on the other side.
        side = side of the INCOMING order ("BUY" or "SELL").
        limit_price = the incoming order's limit, or None for a market sell.
        Returns (fills, remaining)."""
        fills = []
        while remaining > 0:
            # --- 1. find the best waiting order on the other side that we accept ---
            best = None
            for order in self.orders:
                if order["side"] == side:
                    continue                      # same side: can't trade with it
                if limit_price is not None:
                    if side == "BUY" and order["price_ticks"] > limit_price:
                        continue                  # ask too expensive for this buyer
                    if side == "SELL" and order["price_ticks"] < limit_price:
                        continue                  # bid too low for this seller
                if best is None:
                    best = order
                elif side == "SELL":              # we sell to bids: highest price, then earliest
                    if (order["price_ticks"] > best["price_ticks"] or
                            (order["price_ticks"] == best["price_ticks"]
                             and order["arrival_seq"] < best["arrival_seq"])):
                        best = order
                else:                             # we buy from asks: lowest price, then earliest
                    if (order["price_ticks"] < best["price_ticks"] or
                            (order["price_ticks"] == best["price_ticks"]
                             and order["arrival_seq"] < best["arrival_seq"])):
                        best = order
            if best is None:
                break                             # nobody left to trade with

            # --- 2. trade with it (YOUR PART) ---
            qty = min(remaining, best["qty_units"])
            fills.append({
                "maker_id": best["order_id"],
                "taker_id": taker_id,
                "price_ticks": best["price_ticks"],
                "qty_units": qty,
            })
            best["qty_units"] = best["qty_units"] - qty  # maker loses what it traded
            remaining = remaining - qty  # incoming order has less left
            if best["qty_units"] == 0:  # maker used up?
                self.orders.remove(best)

        return fills, remaining

    def AddLimitOrder(self, event):
        # 1. trade first
        fills, remaining = self._match(event["order_id"], event["side"],
                                       event["qty_units"], event["price_ticks"])

        # 2. rest whatever is left
        if remaining > 0:
            order = {
                "order_id": event["order_id"],
                "side": event["side"],
                "price_ticks": event["price_ticks"],
                "qty_units": remaining,
                "arrival_seq": event["seq"],
            }
            self.orders.append(order)
            status = "resting"
        else:
            status = "filled"

        # 3. report
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def FillMarketSell(self, event):
        # trade against the bids: side "SELL", no limit price
        fills, remaining = self._match(event["order_id"], "SELL", event["qty_units"], None)

        # leftover is simply thrown away: nothing goes into the book

        if remaining == 0:
            status = "filled"
        elif len(fills) > 0:
            status = "partial"
        else:
            status = "unfilled"

        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }
        
    def CancelOrder(self, event):
        target = event["target_order_id"]
        for order in self.orders:
            if order["order_id"] == target:
                self.orders.remove(order)
                return {
                    "event_id": event["event_id"],
                    "target_order_id": target,
                    "status": "cancelled",
                    "cancelled_qty_units": order["qty_units"],
                }
        # loop finished without finding it
        return {
            "event_id": event["event_id"],
            "target_order_id": target,
            "status": "not_found",
            "cancelled_qty_units": 0,
        }

    def snapshot(self):
        """Book inspection: bids (high->low price, then seq), then asks (low->high, then seq)."""
        bids = []
        asks = []
        for order in self.orders:
            if order["side"] == "BUY":
                bids.append(order)
            else:
                asks.append(order)
        # best bid = highest price first; same price -> earliest arrival first
        bids.sort(key=lambda o: (-o["price_ticks"], o["arrival_seq"]))
        # best ask = lowest price first; same price -> earliest arrival first
        asks.sort(key=lambda o: (o["price_ticks"], o["arrival_seq"]))
        return bids + asks