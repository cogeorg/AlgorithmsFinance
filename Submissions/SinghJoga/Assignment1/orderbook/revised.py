class OrderBook:
    """Scaffold for the heap- and price-queue-based Version B."""

    def process_event(self, event):
        raise NotImplementedError

    def AddLimitOrder(self, event):
        raise NotImplementedError

    def CancelOrder(self, event):
        raise NotImplementedError

    def FillMarketSell(self, event):
        raise NotImplementedError

    def inspect_book(self):
        raise NotImplementedError

    @property
    def last_accepted_seq(self):
        raise NotImplementedError
import heapq
from collections import OrderedDict
from collections.abc import Mapping
from copy import deepcopy


class OrderBook:
    """Version B: active-order index, FIFO price queues, and price heaps."""

    _HEAP_LEVEL_MULTIPLIER = 2
    _HEAP_STALE_ALLOWANCE = 32

    def __init__(self):
        self._orders_by_id = {}
        self._bids_by_price = {}
        self._asks_by_price = {}
        self._bid_heap = []
        self._ask_heap = []
        self._bid_heap_members = set()
        self._ask_heap_members = set()
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
            order = {
                "order_id": deepcopy(data["order_id"]),
                "side": data["side"],
                "price_ticks": data["price_ticks"],
                "qty_units": remaining,
                "seq": data["seq"],
            }
            self._add_order(order)

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

        active_order = self._orders_by_id.get(data["target_order_id"])
        if active_order is None:
            status = "not_found"
            cancelled_qty_units = 0
        else:
            status = "cancelled"
            cancelled_qty_units = active_order["qty_units"]
            self._remove_order(active_order)

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
        """Return canonical copies of active orders without exposing internals."""
        bids = []
        for price_ticks in sorted(self._bids_by_price, reverse=True):
            bids.extend(
                self._public_order(order)
                for order in self._bids_by_price[price_ticks].values()
            )

        asks = []
        for price_ticks in sorted(self._asks_by_price):
            asks.extend(
                self._public_order(order)
                for order in self._asks_by_price[price_ticks].values()
            )
        return {"bids": bids, "asks": asks}

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
        return order_id in self._orders_by_id

    def _storage_for_side(self, side):
        if side == "BUY":
            return self._bids_by_price, self._bid_heap, self._bid_heap_members
        return self._asks_by_price, self._ask_heap, self._ask_heap_members

    def _add_order(self, order):
        order_id = order["order_id"]
        side = order["side"]
        price_ticks = order["price_ticks"]
        levels, heap, heap_members = self._storage_for_side(side)

        queue = levels.get(price_ticks)
        if queue is None:
            queue = OrderedDict()
            levels[price_ticks] = queue
            heap_value = -price_ticks if side == "BUY" else price_ticks
            if heap_value not in heap_members:
                heapq.heappush(heap, heap_value)
                heap_members.add(heap_value)

        queue[order_id] = order
        self._orders_by_id[order_id] = order

    def _remove_order(self, order):
        order_id = order["order_id"]
        side = order["side"]
        price_ticks = order["price_ticks"]
        levels, _, _ = self._storage_for_side(side)
        queue = levels[price_ticks]

        del queue[order_id]
        del self._orders_by_id[order_id]
        if not queue:
            del levels[price_ticks]
            self._after_level_removed(side)

    def _best_price(self, side):
        levels, heap, heap_members = self._storage_for_side(side)
        while heap:
            heap_value = heap[0]
            price_ticks = -heap_value if side == "BUY" else heap_value
            queue = levels.get(price_ticks)
            if queue:
                return price_ticks

            stale_value = heapq.heappop(heap)
            heap_members.discard(stale_value)
        return None

    def _after_level_removed(self, side):
        levels, heap, heap_members = self._storage_for_side(side)
        if not levels:
            heap.clear()
            heap_members.clear()
            return

        if len(heap) > (
            self._HEAP_LEVEL_MULTIPLIER * len(levels)
            + self._HEAP_STALE_ALLOWANCE
        ):
            heap[:] = [
                -price_ticks if side == "BUY" else price_ticks
                for price_ticks in levels
            ]
            heapq.heapify(heap)
            heap_members.clear()
            heap_members.update(heap)

    def _match(self, taker_id, incoming_side, limit_price_ticks, qty_units):
        maker_side = "SELL" if incoming_side == "BUY" else "BUY"
        levels, _, _ = self._storage_for_side(maker_side)
        remaining = qty_units
        fills = []

        while remaining:
            price_ticks = self._best_price(maker_side)
            if price_ticks is None:
                break
            if incoming_side == "BUY" and price_ticks > limit_price_ticks:
                break
            if incoming_side == "SELL" and limit_price_ticks is not None:
                if price_ticks < limit_price_ticks:
                    break

            queue = levels[price_ticks]
            maker_id = next(iter(queue))
            maker = queue[maker_id]
            fill_qty_units = min(remaining, maker["qty_units"])
            fills.append(
                {
                    "maker_id": deepcopy(maker_id),
                    "taker_id": deepcopy(taker_id),
                    "price_ticks": price_ticks,
                    "qty_units": fill_qty_units,
                }
            )
            maker["qty_units"] -= fill_qty_units
            remaining -= fill_qty_units

            if maker["qty_units"] == 0:
                del queue[maker_id]
                del self._orders_by_id[maker_id]
                if not queue:
                    del levels[price_ticks]
                    self._after_level_removed(maker_side)

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
