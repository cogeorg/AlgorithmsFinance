from collections.abc import Mapping
from copy import deepcopy


class OrderBook:
    """Version A: a transparent list containing only active resting orders."""

    def __init__(self):
        self._orders = []
        self._last_accepted_seq = None

    @property
    def last_accepted_seq(self):
        """Return the last accepted sequence, or None before any acceptance."""
        return self._last_accepted_seq

    def process_event(self, event):
        """Validate and dispatch one LIMIT, MARKET_SELL, or CANCEL event."""
        if not isinstance(event, Mapping):
            return self._rejected(event, "event must be a mapping")

        event_type = event.get("type")
        if event_type == "LIMIT":
            return self.AddLimitOrder(event)
        if event_type == "MARKET_SELL":
            return self.FillMarketSell(event)
        if event_type == "CANCEL":
            return self.CancelOrder(event)
        return self._rejected(event, "unknown event type")

    def AddLimitOrder(self, event):
        """Validate and process one LIMIT event."""
        data, reason = self._validate_event(event, "LIMIT")
        if reason is not None:
            return self._rejected(event, reason)

        fills, remaining = self._match(
            taker_id=data["order_id"],
            incoming_side=data["side"],
            limit_price_ticks=data["price_ticks"],
            qty_units=data["qty_units"],
        )
        if remaining:
            self._orders.append(
                {
                    "order_id": deepcopy(data["order_id"]),
                    "side": data["side"],
                    "price_ticks": data["price_ticks"],
                    "qty_units": remaining,
                    "seq": data["seq"],
                }
            )

        self._last_accepted_seq = data["seq"]
        return {
            "event_id": deepcopy(data["event_id"]),
            "order_id": deepcopy(data["order_id"]),
            "status": "filled" if remaining == 0 else "resting",
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def CancelOrder(self, event):
        """Validate and process one CANCEL event."""
        data, reason = self._validate_event(event, "CANCEL")
        if reason is not None:
            return self._rejected(event, reason)

        active_order = next(
            (
                order
                for order in self._orders
                if order["order_id"] == data["target_order_id"]
            ),
            None,
        )
        if active_order is None:
            status = "not_found"
            cancelled_qty_units = 0
        else:
            status = "cancelled"
            cancelled_qty_units = active_order["qty_units"]
            self._orders.remove(active_order)

        self._last_accepted_seq = data["seq"]
        return {
            "event_id": deepcopy(data["event_id"]),
            "target_order_id": deepcopy(data["target_order_id"]),
            "status": status,
            "cancelled_qty_units": cancelled_qty_units,
        }

    def FillMarketSell(self, event):
        """Validate and process one MARKET_SELL event."""
        data, reason = self._validate_event(event, "MARKET_SELL")
        if reason is not None:
            return self._rejected(event, reason)

        fills, remaining = self._match(
            taker_id=data["order_id"],
            incoming_side="SELL",
            limit_price_ticks=None,
            qty_units=data["qty_units"],
        )
        if remaining == 0:
            status = "filled"
        elif fills:
            status = "partial"
        else:
            status = "unfilled"

        self._last_accepted_seq = data["seq"]
        return {
            "event_id": deepcopy(data["event_id"]),
            "order_id": deepcopy(data["order_id"]),
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def inspect_book(self):
        """Return canonical copies of active orders, never internal order dicts."""
        bids = sorted(
            (order for order in self._orders if order["side"] == "BUY"),
            key=lambda order: (-order["price_ticks"], order["seq"]),
        )
        asks = sorted(
            (order for order in self._orders if order["side"] == "SELL"),
            key=lambda order: (order["price_ticks"], order["seq"]),
        )
        return {
            "bids": [self._public_order(order) for order in bids],
            "asks": [self._public_order(order) for order in asks],
        }

    def _validate_event(self, event, expected_type):
        if not isinstance(event, Mapping):
            return None, "event must be a mapping"

        for field in ("seq", "event_id", "type"):
            if field not in event:
                return None, f"missing required field: {field}"

        seq = event["seq"]
        if not self._is_positive_integer(seq):
            return None, "seq must be a positive integer"
        if self._last_accepted_seq is not None and seq <= self._last_accepted_seq:
            return None, "seq must be strictly increasing"
        if event["type"] != expected_type:
            return None, f"event type must be {expected_type}"

        required_fields = {
            "LIMIT": ("order_id", "side", "price_ticks", "qty_units"),
            "MARKET_SELL": ("order_id", "qty_units"),
            "CANCEL": ("target_order_id",),
        }[expected_type]
        for field in required_fields:
            if field not in event:
                return None, f"missing required field: {field}"

        if expected_type == "LIMIT":
            if event["side"] not in ("BUY", "SELL"):
                return None, "side must be BUY or SELL"
            if not self._is_positive_integer(event["price_ticks"]):
                return None, "price_ticks must be a positive integer"
            if not self._is_positive_integer(event["qty_units"]):
                return None, "qty_units must be a positive integer"
            submission_id = event["order_id"]
        elif expected_type == "MARKET_SELL":
            if not self._is_positive_integer(event["qty_units"]):
                return None, "qty_units must be a positive integer"
            submission_id = event["order_id"]
        else:
            submission_id = None

        if expected_type in ("LIMIT", "MARKET_SELL") and self._has_live_id(
            submission_id
        ):
            return None, "duplicate live submission order_id"

        data = {
            "seq": seq,
            "event_id": event["event_id"],
        }
        for field in required_fields:
            data[field] = event[field]
        return data, None

    @staticmethod
    def _is_positive_integer(value):
        return type(value) is int and value > 0

    def _has_live_id(self, order_id):
        return any(order["order_id"] == order_id for order in self._orders)

    def _match(self, taker_id, incoming_side, limit_price_ticks, qty_units):
        maker_side = "SELL" if incoming_side == "BUY" else "BUY"
        makers = []
        for order in self._orders:
            if order["side"] != maker_side:
                continue
            if incoming_side == "BUY" and limit_price_ticks is not None:
                if order["price_ticks"] > limit_price_ticks:
                    continue
            elif incoming_side == "SELL" and limit_price_ticks is not None:
                if order["price_ticks"] < limit_price_ticks:
                    continue
            makers.append(order)

        if incoming_side == "BUY":
            makers.sort(key=lambda order: (order["price_ticks"], order["seq"]))
        else:
            makers.sort(key=lambda order: (-order["price_ticks"], order["seq"]))

        remaining = qty_units
        fills = []
        for maker in makers:
            if remaining == 0:
                break

            fill_qty_units = min(remaining, maker["qty_units"])
            fills.append(
                {
                    "maker_id": deepcopy(maker["order_id"]),
                    "taker_id": deepcopy(taker_id),
                    "price_ticks": maker["price_ticks"],
                    "qty_units": fill_qty_units,
                }
            )
            maker["qty_units"] -= fill_qty_units
            remaining -= fill_qty_units
            if maker["qty_units"] == 0:
                self._orders.remove(maker)

        return fills, remaining

    @staticmethod
    def _public_order(order):
        return {
            "order_id": deepcopy(order["order_id"]),
            "side": order["side"],
            "price_ticks": order["price_ticks"],
            "qty_units": order["qty_units"],
            "seq": order["seq"],
        }

    @staticmethod
    def _rejected(event, reason):
        result = {"status": "rejected", "reason": reason}
        if isinstance(event, Mapping) and "event_id" in event:
            result["event_id"] = deepcopy(event["event_id"])
        return result
