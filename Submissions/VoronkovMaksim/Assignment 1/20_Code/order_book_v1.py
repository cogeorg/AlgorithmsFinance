"""A simple sequential, list-based limit order book."""


def valid_identifier(value):
    return type(value) is int or (type(value) is str and bool(value))


class OrderBook:
    def __init__(self):
        self.orders = []
        self.last_seq = 0

    def process_event(self, event):
        reason = self._validate(event)
        if reason:
            result = {"status": "rejected", "reason": reason}
            if isinstance(event, dict) and "event_id" in event:
                result["event_id"] = event["event_id"]
            return result
        self.last_seq = event["seq"]
        if event["type"] == "CANCEL":
            return self.CancelOrder(event)
        if event["type"] == "MARKET_SELL":
            return self.FillMarketSell(event)
        return self.AddLimitOrder(event)

    def _validate(self, event):
        if not isinstance(event, dict):
            return "event must be a dictionary"
        if not all(field in event for field in ("seq", "event_id", "type")):
            return "missing common field"
        seq = event["seq"]
        if type(seq) is not int or seq <= self.last_seq:
            return "sequence must be a strictly increasing positive integer"
        kind = event["type"]
        if kind not in ("LIMIT", "MARKET_SELL", "CANCEL"):
            return "unknown event type"
        required = {"LIMIT": ("order_id", "side", "price_ticks", "qty_units"),
                    "MARKET_SELL": ("order_id", "qty_units"),
                    "CANCEL": ("target_order_id",)}[kind]
        if not all(field in event for field in required):
            return "missing required field"
        identifier_field = "target_order_id" if kind == "CANCEL" else "order_id"
        for field in ("event_id", identifier_field):
            if not valid_identifier(event[field]):
                return f"{field} must be a nonempty string or integer"
        if kind == "CANCEL":
            return None
        if any(order["order_id"] == event["order_id"] for order in self.orders):
            return "duplicate live order identifier"
        if kind == "LIMIT" and event["side"] not in ("BUY", "SELL"):
            return "invalid side"
        for field in (("price_ticks", "qty_units") if kind == "LIMIT" else ("qty_units",)):
            if type(event[field]) is not int or event[field] <= 0:
                return f"{field} must be a positive integer"
        return None

    def _match(self, event, side, price=None):
        remaining = event["qty_units"]
        fills = []
        while remaining:
            best = None
            for maker in self.orders:
                if maker["side"] == side:
                    continue
                if price is not None and ((side == "BUY" and maker["price_ticks"] > price)
                                          or (side == "SELL" and maker["price_ticks"] < price)):
                    continue
                if best is None:
                    best = maker
                elif side == "BUY":
                    if (maker["price_ticks"], maker["arrival_seq"]) < (best["price_ticks"], best["arrival_seq"]):
                        best = maker
                elif (-maker["price_ticks"], maker["arrival_seq"]) < (-best["price_ticks"], best["arrival_seq"]):
                    best = maker
            if best is None:
                break
            quantity = min(remaining, best["qty_units"])
            fills.append({"maker_id": best["order_id"], "taker_id": event["order_id"],
                          "price_ticks": best["price_ticks"], "qty_units": quantity})
            remaining -= quantity
            best["qty_units"] -= quantity
            if best["qty_units"] == 0:
                self.orders.remove(best)
        return remaining, fills

    def AddLimitOrder(self, event):
        remaining, fills = self._match(event, event["side"], event["price_ticks"])
        if remaining:
            self.orders.append({"order_id": event["order_id"], "side": event["side"],
                                "price_ticks": event["price_ticks"], "qty_units": remaining,
                                "arrival_seq": event["seq"]})
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": "resting" if remaining else "filled",
                "unfilled_qty_units": remaining, "fills": fills}

    def FillMarketSell(self, event):
        remaining, fills = self._match(event, "SELL")
        status = "filled" if not remaining else ("partial" if fills else "unfilled")
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": status, "unfilled_qty_units": remaining, "fills": fills}

    def CancelOrder(self, event):
        for index, order in enumerate(self.orders):
            if order["order_id"] == event["target_order_id"]:
                quantity = order["qty_units"]
                self.orders.pop(index)
                return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                        "status": "cancelled", "cancelled_qty_units": quantity}
        return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                "status": "not_found", "cancelled_qty_units": 0}

    def inspect_book(self):
        return [order.copy() for order in sorted(
            self.orders, key=lambda o: (0, -o["price_ticks"], o["arrival_seq"])
            if o["side"] == "BUY" else (1, o["price_ticks"], o["arrival_seq"]))]
