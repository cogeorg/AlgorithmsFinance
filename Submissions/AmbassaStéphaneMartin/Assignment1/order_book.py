"""Shared order book routing and explicit implementation selection.

BaselineOrderBook implements matching, validation, cancellation and inspection
using a list of individual orders. RevisedOrderBook stores active orders in FIFO
deques grouped by side and integer price, with an order-ID index and price heaps.
Cancellation is logical and immediate; inactive queue entries have bounded cleanup.
ComparedOrderBook checks both versions after each event, including rejected
events and calls to public handlers.
"""

from collections import deque
from copy import deepcopy
import heapq


IMPLEMENTATIONS = ("baseline", "revised", "compare")


class OrderBook:
    """Common interface for a sequential BTC order book."""

    def process_event(self, event: dict) -> dict:
        """Route an event to its public handler, which validates its fields."""
        if not isinstance(event, dict):
            reason = "event must be a dictionary"
        else:
            event_type = event.get("type")
            if event_type == "LIMIT":
                return self.AddLimitOrder(event)
            if event_type == "MARKET_SELL":
                return self.FillMarketSell(event)
            if event_type == "CANCEL":
                return self.CancelOrder(event)
            reason = "type must be LIMIT, MARKET_SELL or CANCEL"

        result = {"status": "rejected", "reason": reason}
        if isinstance(event, dict) and "event_id" in event:
            result["event_id"] = deepcopy(event["event_id"])
        return result

    def AddLimitOrder(self, event: dict) -> dict:
        """Match a limit order and rest any remaining quantity."""
        raise NotImplementedError("Implement limit order matching.")

    def FillMarketSell(self, event: dict) -> dict:
        """Match a market sell against bids in price-time order."""
        raise NotImplementedError("Implement market sell matching.")

    def CancelOrder(self, event: dict) -> dict:
        """Cancel the target's remaining quantity, or return not_found."""
        raise NotImplementedError("Implement order cancellation.")

    def inspect_book(self) -> dict:
        """Return {"bids": [...], "asks": [...]} in canonical price-time order."""
        raise NotImplementedError("Implement book inspection.")


class BaselineOrderBook(OrderBook):
    """Version A: scan individual orders for matching, lookup and removal."""

    def __init__(self):
        self._last_seq = 0
        self._initialize_storage()

    def _initialize_storage(self):
        self._orders = []

    def AddLimitOrder(self, event: dict) -> dict:
        """Match at eligible resting prices, then rest any incoming residual."""
        return self._handle(event, "LIMIT")

    def FillMarketSell(self, event: dict) -> dict:
        """Sell into the best bids; discard any unsold residual."""
        return self._handle(event, "MARKET_SELL")

    def CancelOrder(self, event: dict) -> dict:
        """Remove the target's remaining quantity, if the order is still live."""
        return self._handle(event, "CANCEL")

    def inspect_book(self) -> dict:
        """Return independent snapshots sorted by price, then arrival sequence."""
        bids, asks = [], []
        for order in self._active_orders():
            snapshot = dict(order)
            if order["side"] == "BUY":
                bids.append(snapshot)
            else:
                asks.append(snapshot)
        bids.sort(key=lambda order: (-order["price_ticks"], order["arrival_seq"]))
        asks.sort(key=lambda order: (order["price_ticks"], order["arrival_seq"]))
        return {"bids": bids, "asks": asks}

    @staticmethod
    def _valid_id(value):
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _positive_integer(value):
        # bool is an int subclass, so isinstance(value, int) is too permissive.
        return type(value) is int and value > 0

    def _validate(self, event, expected_type):
        if not isinstance(event, dict):
            return "An event must be a dictionary."
        for field in ("seq", "event_id", "type"):
            if field not in event:
                return f"Missing required field: {field}."
        if not self._valid_id(event["event_id"]):
            return "event_id must be a nonblank string."
        if not self._positive_integer(event["seq"]):
            return "seq must be a positive built-in integer."
        if event["seq"] <= self._last_seq:
            return "seq must exceed the last accepted sequence."
        if event["type"] != expected_type:
            return f"This handler requires an event of type {expected_type}."

        if expected_type == "LIMIT":
            required = ("order_id", "side", "price_ticks", "qty_units")
        elif expected_type == "MARKET_SELL":
            required = ("order_id", "qty_units")
        else:
            required = ("target_order_id",)
        for field in required:
            if field not in event:
                return f"Missing required field: {field}."

        if expected_type == "CANCEL":
            if not self._valid_id(event["target_order_id"]):
                return "target_order_id must be a nonblank string."
            return None

        if not self._valid_id(event["order_id"]):
            return "order_id must be a nonblank string."
        if not self._positive_integer(event["qty_units"]):
            return "qty_units must be a positive built-in integer."
        if expected_type == "LIMIT":
            if event["side"] not in ("BUY", "SELL"):
                return "side must be BUY or SELL."
            if not self._positive_integer(event["price_ticks"]):
                return "price_ticks must be a positive built-in integer."
        if self._find_order(event["order_id"]) is not None:
            return "A submission with this order_id is already live."
        return None

    @staticmethod
    def _reject(event, reason):
        result = {"status": "rejected", "reason": reason}
        if isinstance(event, dict) and "event_id" in event:
            result["event_id"] = deepcopy(event["event_id"])
        return result

    def _handle(self, event, expected_type):
        # Complete validation before any matching, storage or sequence mutation.
        reason = self._validate(event, expected_type)
        if reason is not None:
            return self._reject(event, reason)
        if expected_type == "LIMIT":
            result = self._apply_limit(event)
        elif expected_type == "MARKET_SELL":
            result = self._apply_market_sell(event)
        else:
            result = self._apply_cancel(event)
        self._last_seq = event["seq"]
        return result

    @staticmethod
    def _submission_result(event, status, fills, remaining):
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def _match(self, side, quantity, taker_id, price_limit=None):
        opposite = "SELL" if side == "BUY" else "BUY"
        fills = []
        remaining = quantity
        while remaining > 0:
            maker = self._best_order(opposite)
            if maker is None:
                break
            price = maker["price_ticks"]
            if price_limit is not None:
                if side == "BUY" and price > price_limit:
                    break
                if side == "SELL" and price < price_limit:
                    break

            executed = min(remaining, maker["qty_units"])
            fills.append({
                "maker_id": maker["order_id"],
                "taker_id": taker_id,
                "price_ticks": price,
                "qty_units": executed,
            })
            remaining -= executed
            maker["qty_units"] -= executed
            if maker["qty_units"] == 0:
                self._remove_order(maker["order_id"])
            # A partial maker stays in its original list/queue position.
        return fills, remaining

    def _apply_limit(self, event):
        fills, remaining = self._match(
            event["side"], event["qty_units"], event["order_id"],
            price_limit=event["price_ticks"],
        )
        if remaining:
            self._rest_order({
                "order_id": event["order_id"],
                "side": event["side"],
                "price_ticks": event["price_ticks"],
                "qty_units": remaining,
                "arrival_seq": event["seq"],
            })
        status = "filled" if remaining == 0 else "resting"
        return self._submission_result(event, status, fills, remaining)

    def _apply_market_sell(self, event):
        fills, remaining = self._match(
            "SELL", event["qty_units"], event["order_id"],
        )
        if remaining == 0:
            status = "filled"
        else:
            status = "partial" if fills else "unfilled"
        return self._submission_result(event, status, fills, remaining)

    def _apply_cancel(self, event):
        target = self._find_order(event["target_order_id"])
        if target is None:
            status, quantity = "not_found", 0
        else:
            status, quantity = "cancelled", target["qty_units"]
            self._remove_order(event["target_order_id"])
        return {
            "event_id": event["event_id"],
            "target_order_id": event["target_order_id"],
            "status": status,
            "cancelled_qty_units": quantity,
        }

    # Baseline storage: every lookup, best-price selection and removal scans.
    def _active_orders(self):
        return iter(self._orders)

    def _find_order(self, order_id):
        return next(
            (order for order in self._orders if order["order_id"] == order_id),
            None,
        )

    def _best_order(self, side):
        candidates = (order for order in self._orders if order["side"] == side)
        if side == "BUY":
            key = lambda order: (-order["price_ticks"], order["arrival_seq"])
        else:
            key = lambda order: (order["price_ticks"], order["arrival_seq"])
        return min(candidates, key=key, default=None)

    def _rest_order(self, order):
        self._orders.append(order)

    def _remove_order(self, order_id):
        for index, order in enumerate(self._orders):
            if order["order_id"] == order_id:
                return self._orders.pop(index)
        return None


class RevisedOrderBook(BaselineOrderBook):
    """Stage 4: lazy order cancellation with bounded queue and heap storage."""

    _HEAP_REBUILD_SLACK = 32
    _QUEUE_REBUILD_SLACK = 32

    def _initialize_storage(self):
        self.orders_by_id = {}
        self.bids_by_price = {}
        self.asks_by_price = {}
        self.bid_price_heap = []
        self.ask_price_heap = []
        self._bid_heap_keys = set()
        self._ask_heap_keys = set()
        self._bid_live_counts = {}
        self._ask_live_counts = {}

    def _active_orders(self):
        return self.orders_by_id.values()

    def _find_order(self, order_id):
        return self.orders_by_id.get(order_id)

    def _is_active(self, order):
        # Identity prevents a reused ID from reviving an older cancelled object.
        return self.orders_by_id.get(order["order_id"]) is order

    def _price_index(self, side):
        if side == "BUY":
            return self.bids_by_price, self.bid_price_heap, self._bid_heap_keys
        return self.asks_by_price, self.ask_price_heap, self._ask_heap_keys

    def _live_counts(self, side):
        return self._bid_live_counts if side == "BUY" else self._ask_live_counts

    def _best_order(self, side):
        levels, heap, retained_keys = self._price_index(side)
        while heap:
            key = heap[0]
            price = -key if side == "BUY" else key
            queue = levels.get(price)
            if queue is not None:
                while queue and not self._is_active(queue[0]):
                    queue.popleft()
                if not queue:
                    raise AssertionError("An active price level has no live maker.")
                return queue[0]
            heapq.heappop(heap)
            retained_keys.remove(key)
        return None

    def _rest_order(self, order):
        side, price = order["side"], order["price_ticks"]
        levels, heap, retained_keys = self._price_index(side)
        counts = self._live_counts(side)
        if price not in levels:
            levels[price] = deque()
            counts[price] = 0
            key = -price if side == "BUY" else price
            if key not in retained_keys:
                heapq.heappush(heap, key)
                retained_keys.add(key)
        levels[price].append(order)
        self.orders_by_id[order["order_id"]] = order
        counts[price] += 1
        self._maybe_rebuild_price_heap(side)

    def _remove_order(self, order_id):
        # Logical removal is immediate and never searches for the deque position.
        order = self.orders_by_id.pop(order_id, None)
        if order is None:
            return None
        side, price = order["side"], order["price_ticks"]
        levels, _, _ = self._price_index(side)
        counts = self._live_counts(side)
        queue = levels[price]
        counts[price] -= 1
        if queue[0] is order:
            queue.popleft()
        if counts[price] == 0:
            # Release inactive entries when the final live order leaves a level.
            queue.clear()
            del levels[price]
            del counts[price]
        else:
            self._maybe_rebuild_price_queue(side, price)
        self._maybe_rebuild_price_heap(side)
        return order

    def _maybe_rebuild_price_queue(self, side, price):
        """Bound a price queue even while an old live order remains at its head."""
        levels, _, _ = self._price_index(side)
        queue = levels[price]
        live_count = self._live_counts(side)[price]
        if len(queue) > 2 * live_count + self._QUEUE_REBUILD_SLACK:
            active_orders = [order for order in queue if self._is_active(order)]
            # Stable filtering retains FIFO and the original shared order objects.
            queue.clear()
            queue.extend(active_orders)

    def _maybe_rebuild_price_heap(self, side):
        """Bound retained keys to 2 * active levels + slack after each operation."""
        levels, heap, retained_keys = self._price_index(side)
        if not levels:
            heap.clear()
            retained_keys.clear()
        elif len(heap) > 2 * len(levels) + self._HEAP_REBUILD_SLACK:
            heap[:] = [-price if side == "BUY" else price for price in levels]
            heapq.heapify(heap)
            retained_keys.clear()
            retained_keys.update(heap)


def _same_value(left, right):
    """Compare nested values without treating 1, 1.0 and True as identical."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_value(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_value(a, b) for a, b in zip(left, right)
        )
    return left == right


def _comparable_result(result):
    if not isinstance(result, dict):
        raise AssertionError("An event handler must return a dictionary.")
    if result.get("status") == "rejected":
        reason = result.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise AssertionError("A rejected result needs a nonempty reason.")
        # Each version may explain the same rejection in its own words.
        return {key: value for key, value in result.items() if key != "reason"}
    return result


def _book_snapshot(book):
    snapshot = book.inspect_book()
    if not isinstance(snapshot, dict) or not all(
        isinstance(snapshot.get(side), list) for side in ("bids", "asks")
    ):
        raise AssertionError("inspect_book() must return bids and asks lists.")
    return deepcopy(snapshot)


class ComparedOrderBook(OrderBook):
    """Run separate Baseline and Revised books and detect their first difference."""

    def __init__(self, baseline=None, revised=None):
        self.baseline = BaselineOrderBook() if baseline is None else baseline
        self.revised = RevisedOrderBook() if revised is None else revised
        if self.baseline is self.revised:
            raise ValueError("Comparison requires two separate book instances.")

    def _call(self, method_name, event):
        left = deepcopy(getattr(self.baseline, method_name)(deepcopy(event)))
        right = deepcopy(getattr(self.revised, method_name)(deepcopy(event)))
        event_id = event.get("event_id") if isinstance(event, dict) else None

        # Check state immediately, even when this event was rejected.
        try:
            self.inspect_book()
        except AssertionError as error:
            raise AssertionError(
                f"{method_name}, event_id={event_id!r}: {error}"
            ) from error

        if not _same_value(_comparable_result(left), _comparable_result(right)):
            raise AssertionError(
                f"{method_name}, event_id={event_id!r}: result mismatch; "
                f"Baseline={left!r}; Revised={right!r}"
            )
        return deepcopy(left)

    def process_event(self, event: dict) -> dict:
        return self._call("process_event", event)

    def AddLimitOrder(self, event: dict) -> dict:
        return self._call("AddLimitOrder", event)

    def FillMarketSell(self, event: dict) -> dict:
        return self._call("FillMarketSell", event)

    def CancelOrder(self, event: dict) -> dict:
        return self._call("CancelOrder", event)

    def inspect_book(self) -> dict:
        left = _book_snapshot(self.baseline)
        right = _book_snapshot(self.revised)
        if not _same_value(left, right):
            raise AssertionError(
                f"book state mismatch; Baseline={left!r}; Revised={right!r}"
            )
        return left


def create_order_book(implementation="baseline"):
    """Select baseline, revised or compare; never silently fall back."""
    if implementation == "baseline":
        return BaselineOrderBook()
    if implementation == "revised":
        return RevisedOrderBook()
    if implementation == "compare":
        return ComparedOrderBook()
    raise ValueError(
        f"Unknown implementation {implementation!r}; choose from {IMPLEMENTATIONS}."
    )
