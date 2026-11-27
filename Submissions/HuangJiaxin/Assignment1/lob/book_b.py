"""Version B: revised data organization (price levels + FIFO queues + heaps + id index).

Data organization, per side (BUY, SELL):
    levels[side][price] -> deque of orders at that price, in arrival order (FIFO queue)
    live[side][price]   -> number of ACTIVE orders in that deque
    heaps[side]         -> heap of occupied prices (bids stored as -price, so the top
                           is always the best price); may contain stale prices
and one dictionary for both sides:
    index[order_id]     -> the active order object (O(1) cancel and duplicate check)

Cancellation is LAZY: the order is marked inactive and removed from `index`, but its entry
stays in the deque until it reaches the front. A price level whose live count drops to zero
is deleted at once (with all its stale entries). Two compaction rules bound the leftovers:
    * a deque is rebuilt when it holds more than 2 * live + 8 entries;
    * a heap is rebuilt from the occupied prices when it holds more than 2 * levels + 16.
Each rebuild costs O(size) but happens only after at least as many cheap operations
added the garbage, so the cost per operation stays O(1) amortized. `compact=False` turns
both rules off (used only to measure what stale entries cost; see the report).

Pseudocode (P = occupied price levels, F = maker fills, B = active orders):
    AddLimitOrder(e):  validate (O(1) with `index`)
                       while quantity remains and best opposite price crosses e's limit:
                           take the front order of that level's deque (skip stale ones)
                           trade min(q_in, q_rest) at the resting price
                           pop the maker if exhausted; delete the level if no live order left
                       residual: append to its price deque; push the price if the level is new
    FillMarketSell(e): the same loop on the bid side without a limit; residual is discarded
    CancelOrder(e):    order = index.pop(id); mark inactive; live -= 1; delete or compact level
Cost: non-crossing insertion O(log P) (heap push for a new level, else O(1));
cancel O(1) amortized; a sale O(F + L log P) for F fills and L emptied levels, plus O(1)
amortized for skipping stale entries. Space: O(B + P) after compaction.
"""
import heapq
from collections import deque

from . import validation
from .interface import (STATUS_CANCELLED, STATUS_FILLED, STATUS_NOT_FOUND,
                        STATUS_PARTIAL, STATUS_RESTING, STATUS_UNFILLED)


class _Order:
    __slots__ = ("order_id", "side", "price", "qty", "seq", "active")

    def __init__(self, order_id, side, price, qty, seq):
        self.order_id, self.side, self.price, self.qty, self.seq = order_id, side, price, qty, seq
        self.active = True


class OrderBookB:
    name = "B"

    def __init__(self, compact=True):
        self.compact = compact
        self.index = {}
        self.levels = {"BUY": {}, "SELL": {}}
        self.live = {"BUY": {}, "SELL": {}}
        self.heaps = {"BUY": [], "SELL": []}
        self.last_seq = None

    # ------------------------------------------------------------------ price levels
    @staticmethod
    def _key(side, price):
        return -price if side == "BUY" else price

    def _best_price(self, side):
        heap, levels = self.heaps[side], self.levels[side]
        while heap:
            price = -heap[0] if side == "BUY" else heap[0]
            if price in levels:
                return price
            heapq.heappop(heap)                       # stale price: level was deleted
        return None

    def _drop_level(self, side, price):
        del self.levels[side][price]
        del self.live[side][price]
        if self.compact and len(self.heaps[side]) > 2 * len(self.levels[side]) + 16:
            self.heaps[side] = [self._key(side, p) for p in self.levels[side]]
            heapq.heapify(self.heaps[side])

    def _rest(self, order):
        side, price = order.side, order.price
        level = self.levels[side].get(price)
        if level is None:
            level = self.levels[side][price] = deque()
            self.live[side][price] = 0
            heapq.heappush(self.heaps[side], self._key(side, price))
        level.append(order)
        self.live[side][price] += 1
        self.index[order.order_id] = order

    # ------------------------------------------------------------------ matching
    def _match(self, taker_id, opposite, quantity, limit_price=None):
        fills = []
        levels, live = self.levels[opposite], self.live[opposite]
        while quantity > 0:
            price = self._best_price(opposite)
            if price is None:
                break
            if limit_price is not None and (
                    (opposite == "SELL" and price > limit_price) or
                    (opposite == "BUY" and price < limit_price)):
                break
            queue = levels[price]
            while quantity > 0 and live[price] > 0:
                maker = queue[0]
                if not maker.active:                  # lazily cancelled entry
                    queue.popleft()
                    continue
                traded = min(quantity, maker.qty)
                fills.append({"maker_id": maker.order_id, "taker_id": taker_id,
                              "price_ticks": price, "qty_units": traded})
                quantity -= traded
                maker.qty -= traded
                if maker.qty == 0:
                    maker.active = False
                    queue.popleft()
                    del self.index[maker.order_id]
                    live[price] -= 1
            if live[price] == 0:
                self._drop_level(opposite, price)
        return fills, quantity

    def _validate(self, event, expected_type=None):
        reason = validation.check(event, self.last_seq, self.index.__contains__)
        if reason is None and expected_type and event["type"] != expected_type:
            reason = f"expected a {expected_type} event"
        return reason

    # ------------------------------------------------------------------ public API
    def process(self, event):
        """Event dispatcher."""
        kind = event.get("type") if isinstance(event, dict) else None
        if kind == "LIMIT":
            return self.add_limit_order(event)
        if kind == "MARKET_SELL":
            return self.fill_market_sell(event)
        if kind == "CANCEL":
            return self.cancel_order(event)
        reason = self._validate(event) or f"unknown event type {kind!r}"
        return validation.rejected(event, reason)

    def add_limit_order(self, event):
        reason = self._validate(event, "LIMIT")
        if reason:
            return validation.rejected(event, reason)
        self.last_seq = event["seq"]
        side, price = event["side"], event["price_ticks"]
        opposite = "SELL" if side == "BUY" else "BUY"
        fills, rest = self._match(event["order_id"], opposite, event["qty_units"], price)
        if rest > 0:
            self._rest(_Order(event["order_id"], side, price, rest, event["seq"]))
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": STATUS_RESTING if rest else STATUS_FILLED,
                "unfilled_qty_units": rest, "fills": fills}

    def fill_market_sell(self, event):
        reason = self._validate(event, "MARKET_SELL")
        if reason:
            return validation.rejected(event, reason)
        self.last_seq = event["seq"]
        fills, rest = self._match(event["order_id"], "BUY", event["qty_units"])
        status = STATUS_FILLED if rest == 0 else (STATUS_PARTIAL if fills else STATUS_UNFILLED)
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": status, "unfilled_qty_units": rest, "fills": fills}

    def cancel_order(self, event):
        reason = self._validate(event, "CANCEL")
        if reason:
            return validation.rejected(event, reason)
        self.last_seq = event["seq"]
        target_id = event["target_order_id"]
        order = self.index.pop(target_id, None)
        if order is None:
            return {"event_id": event["event_id"], "target_order_id": target_id,
                    "status": STATUS_NOT_FOUND, "cancelled_qty_units": 0}
        order.active = False
        side, price = order.side, order.price
        self.live[side][price] -= 1
        live = self.live[side][price]
        if live == 0:
            self._drop_level(side, price)
        elif self.compact and len(self.levels[side][price]) > 2 * live + 8:
            self.levels[side][price] = deque(o for o in self.levels[side][price] if o.active)
        return {"event_id": event["event_id"], "target_order_id": target_id,
                "status": STATUS_CANCELLED, "cancelled_qty_units": order.qty}

    # ------------------------------------------------------------------ inspection
    def snapshot(self):
        out = {}
        for side, key in (("BUY", "bids"), ("SELL", "asks")):
            prices = sorted(self.levels[side], reverse=(side == "BUY"))
            out[key] = [{"order_id": o.order_id, "side": side, "price_ticks": p,
                         "qty_units": o.qty, "arrival_seq": o.seq}
                        for p in prices for o in self.levels[side][p] if o.active]
        return out

    def best_bid(self):
        return self._best_price("BUY")

    def best_ask(self):
        return self._best_price("SELL")

    def active_order_count(self):
        return len(self.index)

    def price_level_count(self):
        return len(self.levels["BUY"]) + len(self.levels["SELL"])

    def stale_entries(self):
        """Inactive entries still stored in deques plus stale heap entries (diagnostics)."""
        in_deques = sum(len(q) for side in self.levels.values() for q in side.values()) - len(self.index)
        in_heaps = sum(len(h) for h in self.heaps.values()) - self.price_level_count()
        return in_deques, in_heaps

    AddLimitOrder = add_limit_order
    CancelOrder = cancel_order
    FillMarketSell = fill_market_sell
