"""Shared validation/result contract; matching is implemented by each engine."""


def positive_integer(value):
    return type(value) is int and value > 0


def identifier(value):
    return isinstance(value, str) and bool(value)


def order_from(event, qty):
    return dict(order_id=event["order_id"], side=event["side"],
                price_ticks=event["price_ticks"], qty_units=qty,
                arrival_seq=event["seq"])


class Engine:
    def __init__(self, instrument=False):
        self.last_seq = 0
        self.metrics = {} if instrument else None

    def count(self, key, amount=1):
        if self.metrics is not None:
            self.metrics[key] = self.metrics.get(key, 0) + amount

    def validate(self, event):
        if not isinstance(event, dict):
            return "event must be an object"
        if not positive_integer(event.get("seq")) or event["seq"] <= self.last_seq:
            return "seq must be a strictly increasing positive integer"
        if not identifier(event.get("event_id")):
            return "event_id must be a nonempty string"
        kind = event.get("type")
        if kind not in ("LIMIT", "MARKET_SELL", "CANCEL"):
            return "unknown event type"
        if kind == "CANCEL":
            return None if identifier(event.get("target_order_id")) else "invalid cancel target"
        if not identifier(event.get("order_id")):
            return "order_id must be a nonempty string"
        if not positive_integer(event.get("qty_units")):
            return "qty_units must be a positive integer"
        if kind == "LIMIT":
            if event.get("side") not in ("BUY", "SELL"):
                return "unknown side"
            if not positive_integer(event.get("price_ticks")):
                return "price_ticks must be a positive integer"
        if self._contains(event["order_id"]):
            return "duplicate live order_id"
        return None

    def process(self, event):
        reason = self.validate(event)
        if reason:
            result = dict(status="rejected", reason=reason)
            if isinstance(event, dict) and "event_id" in event:
                result["event_id"] = event["event_id"]
            return result
        if event["type"] == "CANCEL":
            qty = self._cancel(event["target_order_id"])
            result = dict(event_id=event["event_id"], target_order_id=event["target_order_id"],
                          status="cancelled" if qty else "not_found", cancelled_qty_units=qty)
        else:
            fills, remaining = self._match(event)
            if event["type"] == "LIMIT":
                if remaining:
                    self._insert(order_from(event, remaining))
                status = "resting" if remaining else "filled"
            else:
                status = "filled" if not remaining else "partial" if fills else "unfilled"
            result = dict(event_id=event["event_id"], order_id=event["order_id"], status=status,
                          unfilled_qty_units=remaining, fills=fills)
        self.last_seq = event["seq"]
        return result

    def _typed(self, event, kind):
        if isinstance(event, dict) and event.get("type") == kind:
            return self.process(event)
        result = dict(status="rejected", reason=f"expected {kind} event")
        if isinstance(event, dict) and "event_id" in event:
            result["event_id"] = event["event_id"]
        return result

    def AddLimitOrder(self, event):
        return self._typed(event, "LIMIT")

    def CancelOrder(self, event):
        return self._typed(event, "CANCEL")

    def FillMarketSell(self, event):
        return self._typed(event, "MARKET_SELL")


def canonical(orders):
    return [dict(row) for row in sorted(orders, key=lambda r: (
        0 if r["side"] == "BUY" else 1,
        -r["price_ticks"] if r["side"] == "BUY" else r["price_ticks"],
        r["arrival_seq"]))]
