"""Price heaps, cancellable FIFO queues, and a live order index."""
from collections import OrderedDict
import heapq
from .contract import OrderBookContract


class OrderBook(OrderBookContract):
    """Heap entries may outlive levels, but periodic rebuilds bound their count."""

    def __init__(self):
        super().__init__()
        self._orders = {}
        self._levels = {"BUY": {}, "SELL": {}}
        self._heaps = {"BUY": [], "SELL": []}
        self._heap_keys = {"BUY": set(), "SELL": set()}

    @staticmethod
    def _positive_integer(value):
        return type(value) is int and value > 0

    def _validation_error(self, event):
        # Validation is read-only, including when stale heap entries exist.
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
        if event["order_id"] in self._orders:
            return "duplicate live order_id"
        return None

    def process_event(self, event: dict) -> dict:
        reason = self._validation_error(event)
        if reason is not None:
            result = {"status": "rejected", "reason": reason}
            if isinstance(event, dict) and "event_id" in event:
                result["event_id"] = event["event_id"]
            return result
        result = self._cancel(event) if event["type"] == "CANCEL" else self._match(event)
        self.last_seq = event["seq"]
        return result

    @staticmethod
    def _price_key(side, price):
        return -price if side == "BUY" else price

    def _best_price(self, side):
        heap = self._heaps[side]
        while heap:
            key = heap[0]
            price = -key if side == "BUY" else key
            if price in self._levels[side]:
                return price
            heapq.heappop(heap)
            self._heap_keys[side].remove(key)
        return None

    def _drop_empty_level(self, side, price):
        del self._levels[side][price]
        heap, keys, levels = self._heaps[side], self._heap_keys[side], self._levels[side]
        if not levels:
            heap.clear()
            keys.clear()
        elif len(heap) > 2 * len(levels) + 64:
            # Rebuild from live prices; no order queues or arrival ranks change.
            heap[:] = [self._price_key(side, p) for p in levels]
            heapq.heapify(heap)
            keys.clear()
            keys.update(heap)

    def _rest(self, event, remaining):
        side, price = event["side"], event["price_ticks"]
        levels = self._levels[side]
        if price not in levels:
            levels[price] = OrderedDict()
            key = self._price_key(side, price)
            # A reactivated price can still have its old heap entry.
            if key not in self._heap_keys[side]:
                heapq.heappush(self._heaps[side], key)
                self._heap_keys[side].add(key)
        record = dict(order_id=event["order_id"], side=side, price_ticks=price,
                      qty_units=remaining, arrival_seq=event["seq"])
        self._orders[event["order_id"]] = record
        levels[price][event["order_id"]] = record

    def _cancel(self, event):
        oid = event["target_order_id"]
        record = self._orders.pop(oid, None)
        quantity = 0
        if record is not None:
            side, price = record["side"], record["price_ticks"]
            queue = self._levels[side][price]
            del queue[oid]
            quantity = record["qty_units"]
            if not queue:
                self._drop_empty_level(side, price)
        return dict(event_id=event["event_id"], target_order_id=oid,
                    status="cancelled" if record is not None else "not_found",
                    cancelled_qty_units=quantity)

    def _match(self, event):
        is_limit = event["type"] == "LIMIT"
        side = event["side"] if is_limit else "SELL"
        opposite = "SELL" if side == "BUY" else "BUY"
        remaining, fills = event["qty_units"], []
        while remaining:
            price = self._best_price(opposite)
            if price is None:
                break
            if is_limit and ((side == "BUY" and price > event["price_ticks"])
                             or (side == "SELL" and price < event["price_ticks"])):
                break
            queue = self._levels[opposite][price]
            maker = next(iter(queue.values()))
            quantity = min(remaining, maker["qty_units"])
            fills.append(dict(maker_id=maker["order_id"], taker_id=event["order_id"],
                              price_ticks=price, qty_units=quantity))
            maker["qty_units"] -= quantity
            remaining -= quantity
            if not maker["qty_units"]:
                queue.popitem(last=False)
                del self._orders[maker["order_id"]]
                if not queue:
                    self._drop_empty_level(opposite, price)
        if is_limit:
            if remaining:
                self._rest(event, remaining)
            status = "resting" if remaining else "filled"
        else:
            status = "filled" if not remaining else "partial" if fills else "unfilled"
        return dict(event_id=event["event_id"], order_id=event["order_id"],
                    status=status, unfilled_qty_units=remaining, fills=fills)

    def FillMarketSell(self, event: dict) -> dict:
        """Mutate the live indexed queues through the common validation boundary."""
        return self.process_event(event)

    def inspect_book(self) -> list[dict]:
        result = []
        for side in ("BUY", "SELL"):
            for price in sorted(self._levels[side], reverse=side == "BUY"):
                result.extend(dict(o) for o in self._levels[side][price].values())
        return result
