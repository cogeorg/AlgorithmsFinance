from .contract import OrderBookContract


class OrderBook(OrderBookContract):
    """List-based baseline: scan live orders, sort eligible makers per event.

    No historical IDs, trade history, or inactive entries are retained.
    """

    def __init__(self):
        super().__init__()
        self._orders = []

    @staticmethod
    def _positive_integer(value):
        return type(value) is int and value > 0

    def _validation_error(self, event):
        # Complete validation precedes all writes, including last_seq updates.
        if not isinstance(event, dict):
            return "event must be an object"
        if not self._positive_integer(event.get("seq")):
            return "seq must be a positive integer"
        if event["seq"] <= self.last_seq:
            return "seq must exceed the last accepted sequence"
        if not isinstance(event.get("event_id"), str) or not event["event_id"]:
            return "event_id must be a nonempty string"
        kind = event.get("type")
        if kind not in ("LIMIT", "MARKET_SELL", "CANCEL"):
            return "unknown event type"
        id_field = "target_order_id" if kind == "CANCEL" else "order_id"
        if not isinstance(event.get(id_field), str) or not event[id_field]:
            return f"{id_field} must be a nonempty string"
        if kind == "CANCEL":
            return None
        if not self._positive_integer(event.get("qty_units")):
            return "qty_units must be a positive integer"
        if kind == "LIMIT":
            if event.get("side") not in ("BUY", "SELL"):
                return "side must be BUY or SELL"
            if not self._positive_integer(event.get("price_ticks")):
                return "price_ticks must be a positive integer"
        if any(o["order_id"] == event["order_id"] for o in self._orders):
            return "duplicate live order_id"
        return None

    def process_event(self, event: dict) -> dict:
        reason = self._validation_error(event)
        if reason is not None:
            result = {"status": "rejected", "reason": reason}
            if isinstance(event, dict) and "event_id" in event:
                result["event_id"] = event["event_id"]
            return result
        if event["type"] == "CANCEL":
            result = self._cancel(event)
        else:
            result = self._match(event)
        self.last_seq = event["seq"]
        return result

    def _cancel(self, event):
        for index, resting in enumerate(self._orders):
            if resting["order_id"] == event["target_order_id"]:
                removed = self._orders.pop(index)
                return dict(event_id=event["event_id"], target_order_id=event["target_order_id"],
                            status="cancelled", cancelled_qty_units=removed["qty_units"])
        return dict(event_id=event["event_id"], target_order_id=event["target_order_id"],
                    status="not_found", cancelled_qty_units=0)

    def _match(self, event):
        is_limit = event["type"] == "LIMIT"
        side = event["side"] if is_limit else "SELL"
        remaining = event["qty_units"]
        candidates = []
        for resting in self._orders:
            if resting["side"] == side:
                continue
            if is_limit:
                crosses = (resting["price_ticks"] <= event["price_ticks"] if side == "BUY"
                           else resting["price_ticks"] >= event["price_ticks"])
                if not crosses:
                    continue
            candidates.append(resting)
        candidates.sort(key=lambda o: (
            o["price_ticks"] if side == "BUY" else -o["price_ticks"], o["arrival_seq"]))
        fills = []
        for maker in candidates:
            if remaining == 0:
                break
            quantity = min(remaining, maker["qty_units"])
            fills.append(dict(maker_id=maker["order_id"], taker_id=event["order_id"],
                              price_ticks=maker["price_ticks"], qty_units=quantity))
            maker["qty_units"] -= quantity
            remaining -= quantity
        # Remove exhausted makers once, without retaining tombstones.
        self._orders = [o for o in self._orders if o["qty_units"] > 0]
        if is_limit and remaining:
            self._orders.append(dict(order_id=event["order_id"], side=side,
                price_ticks=event["price_ticks"], qty_units=remaining, arrival_seq=event["seq"]))
        if is_limit:
            status = "resting" if remaining else "filled"
        else:
            status = "filled" if not remaining else "partial" if fills else "unfilled"
        return dict(event_id=event["event_id"], order_id=event["order_id"],
                    status=status, unfilled_qty_units=remaining, fills=fills)

    def FillMarketSell(self, event: dict) -> dict:
        """Execute a market-sell event using this implementation's live matcher."""
        return self.process_event(event)

    def inspect_book(self) -> list[dict]:
        def priority(o):
            return (0 if o["side"] == "BUY" else 1,
                    -o["price_ticks"] if o["side"] == "BUY" else o["price_ticks"],
                    o["arrival_seq"])
        return [dict(o) for o in sorted(self._orders, key=priority)]
