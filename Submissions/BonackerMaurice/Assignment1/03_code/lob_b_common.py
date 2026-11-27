"""Version B shared core: hashing for ids, FIFO deques per price level.

Both B variants (lob_b_sorted.py, lob_b_heap.py) use this core and differ
ONLY in the price index that answers "best occupied price on this side?".
Design, pseudocode and costs: 07_docs/REVISIONS.md, Revision 1.

Data organisation:
    orders        dict order_id -> Order          live orders only
    levels[side]  dict price -> Level             occupied levels only
    Level.queue   deque of Order in arrival order (FIFO)
    Level.live_count / Level.live_qty             live orders / their quantity

Cancel is lazy inside a level: the order leaves `orders`, its quantity is
set to 0 ("dead") and it stays in the deque until matching reaches it, the
level empties, or compaction rebuilds the deque (more than half dead).

Units are integers throughout (price_ticks, qty_units). Only the current
event's fills are returned; no trade history is stored.

Use `process_event(event)` for raw events: it validates first (shared
validation.py). AddLimitOrder, FillMarketSell and CancelOrder assume
validated arguments.
"""

from collections import deque

from validation import validate_event

SIDES = ("BUY", "SELL")


class Order:
    """One resting order. qty_units == 0 means cancelled (dead) in a queue."""
    __slots__ = ("order_id", "side", "price_ticks", "qty_units", "arrival_seq")

    def __init__(self, order_id, side, price_ticks, qty_units, arrival_seq):
        self.order_id = order_id
        self.side = side
        self.price_ticks = price_ticks
        self.qty_units = qty_units
        self.arrival_seq = arrival_seq


class Level:
    """All orders at one price on one side, in arrival order."""
    __slots__ = ("queue", "live_count", "live_qty")

    def __init__(self):
        self.queue = deque()
        self.live_count = 0
        self.live_qty = 0


class OrderBookB:
    """Shared Version B core. Subclasses supply the price index:

        _init_index()                     create empty index for both sides
        _best_price(side) -> int | None   best occupied price on side
        _index_add(side, price)           a new level was created
        _index_remove_best(side, price)   matching emptied the best level
        _index_remove(side, price)        a cancel emptied a level (any)
        _ordered_prices(side) -> list     occupied prices, best first
        _check_index()                    assert index invariants
    """

    def __init__(self):
        self.orders = {}
        self.levels = {"BUY": {}, "SELL": {}}
        self.last_seq = 0
        self._init_index()

    # ----- public operations ---------------------------------------------

    def AddLimitOrder(self, event_id, order_id, side, price_ticks, qty_units, seq):
        """Submit a limit order.

        AddLimitOrder(event_id: str, order_id: str, side: "BUY" | "SELL",
                      price_ticks: int > 0, qty_units: int > 0, seq: int) -> dict

        Matches while prices cross (best price first, FIFO inside a level),
        each trade at the resting order's price; any residual rests at the
        back of its price level with arrival_seq = seq.
        Returns {"event_id", "order_id", "status": "filled" | "resting",
                 "unfilled_qty_units", "fills"}.
        """
        fills, remaining = self._match(order_id, side, qty_units, price_ticks)
        if remaining > 0:
            order = Order(order_id, side, price_ticks, remaining, seq)
            self.orders[order_id] = order
            side_levels = self.levels[side]
            level = side_levels.get(price_ticks)
            if level is None:
                level = Level()
                side_levels[price_ticks] = level
                self._index_add(side, price_ticks)
            level.queue.append(order)
            level.live_count += 1
            level.live_qty += remaining
            status = "resting"
        else:
            status = "filled"
        return {
            "event_id": event_id,
            "order_id": order_id,
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def FillMarketSell(self, event_id, order_id, qty_units):
        """Sell into the live bids: highest price first, FIFO inside a level.

        FillMarketSell(event_id: str, order_id: str, qty_units: int > 0) -> dict

        Mutates the book; the unfilled residual is discarded, never rests.
        Returns {"event_id", "order_id",
                 "status": "filled" | "partial" | "unfilled",
                 "unfilled_qty_units", "fills"}.
        """
        fills, remaining = self._match(order_id, "SELL", qty_units, None)
        if remaining == 0:
            status = "filled"
        elif fills:
            status = "partial"
        else:
            status = "unfilled"
        return {
            "event_id": event_id,
            "order_id": order_id,
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def CancelOrder(self, event_id, target_order_id):
        """Remove the target's entire remaining quantity, if it is active.

        CancelOrder(event_id: str, target_order_id: str) -> dict

        Returns {"event_id", "target_order_id",
                 "status": "cancelled" | "not_found", "cancelled_qty_units"}.
        """
        order = self.orders.pop(target_order_id, None)
        if order is None:
            return {
                "event_id": event_id,
                "target_order_id": target_order_id,
                "status": "not_found",
                "cancelled_qty_units": 0,
            }
        level = self.levels[order.side][order.price_ticks]
        qty = order.qty_units
        order.qty_units = 0            # dead: stays in the deque (lazy deletion)
        level.live_count -= 1
        level.live_qty -= qty
        self._tidy(order.side, order.price_ticks, level, best=False)
        return {
            "event_id": event_id,
            "target_order_id": target_order_id,
            "status": "cancelled",
            "cancelled_qty_units": qty,
        }

    def process_event(self, event):
        """Validate one event and dispatch it.

        process_event(event: dict) -> dict

        Invalid events return {"event_id", "status": "rejected", "reason"}
        and change neither the book nor last_seq.
        """
        reason = validate_event(event, self.last_seq, self.orders.__contains__)
        if reason is not None:
            event_id = event.get("event_id") if isinstance(event, dict) else None
            return {"event_id": event_id, "status": "rejected", "reason": reason}

        self.last_seq = event["seq"]
        kind = event["type"]
        if kind == "LIMIT":
            return self.AddLimitOrder(event["event_id"], event["order_id"],
                                      event["side"], event["price_ticks"],
                                      event["qty_units"], event["seq"])
        if kind == "MARKET_SELL":
            return self.FillMarketSell(event["event_id"], event["order_id"],
                                       event["qty_units"])
        return self.CancelOrder(event["event_id"], event["target_order_id"])

    def inspect_book(self):
        """Active orders in canonical order (copies).

        inspect_book() -> list[dict]  each {"order_id", "side", "price_ticks",
                                            "qty_units", "arrival_seq"}
        Bids first (price desc, then arrival), then asks (price asc, then
        arrival). Built from the levels and their FIFO queues, so it also
        shows the structure's own priority order.
        """
        out = []
        for side in SIDES:
            side_levels = self.levels[side]
            for price in self._ordered_prices(side):
                for o in side_levels[price].queue:
                    if o.qty_units > 0:
                        out.append({
                            "order_id": o.order_id,
                            "side": o.side,
                            "price_ticks": o.price_ticks,
                            "qty_units": o.qty_units,
                            "arrival_seq": o.arrival_seq,
                        })
        return out

    def assert_invariants(self):
        """Raise AssertionError if the stored book breaks an invariant.

        Shared checks: every live order sits in exactly one queue, at its own
        side and price, in arrival order; live_count / live_qty match the
        live entries; no empty level; dead entries are not in `orders`;
        queue length <= 2 * live_count (compaction bound); quantities are
        positive integers; the book is not crossed. Then the variant's own
        index checks (_check_index).
        """
        seen = set()
        for side in SIDES:
            for price, level in self.levels[side].items():
                assert level.live_count > 0, f"empty level {side} {price}"
                assert len(level.queue) <= 2 * level.live_count, \
                    f"compaction bound broken at {side} {price}"
                live_qty = 0
                live_count = 0
                last_seq = 0
                for o in level.queue:
                    assert o.side == side and o.price_ticks == price, o.order_id
                    assert o.arrival_seq > last_seq, f"FIFO order broken at {price}"
                    last_seq = o.arrival_seq
                    if o.qty_units == 0:
                        assert self.orders.get(o.order_id) is not o, \
                            f"dead entry still live: {o.order_id}"
                        continue
                    assert type(o.qty_units) is int and o.qty_units > 0
                    assert o.order_id not in seen, f"stored twice: {o.order_id}"
                    assert self.orders.get(o.order_id) is o, \
                        f"queue entry not in orders: {o.order_id}"
                    seen.add(o.order_id)
                    live_qty += o.qty_units
                    live_count += 1
                assert live_count == level.live_count, f"live_count at {price}"
                assert live_qty == level.live_qty, f"live_qty at {price}"
        assert len(seen) == len(self.orders), "orders dict and queues disagree"
        bids, asks = self.levels["BUY"], self.levels["SELL"]
        if bids and asks:
            assert max(bids) < min(asks), f"crossed book: {max(bids)} >= {min(asks)}"
        self._check_index()

    # ----- shared internals --------------------------------------------------

    def _match(self, taker_id, taker_side, qty_units, limit_price):
        """Trade an incoming order against the book. limit_price None = market.

        Returns (fills, remaining_qty).
        """
        maker_side = "SELL" if taker_side == "BUY" else "BUY"
        maker_levels = self.levels[maker_side]
        orders = self.orders
        fills = []
        remaining = qty_units
        while remaining > 0:
            price = self._best_price(maker_side)
            if price is None:
                break
            if limit_price is not None:
                if taker_side == "BUY" and limit_price < price:
                    break
                if taker_side == "SELL" and limit_price > price:
                    break
            level = maker_levels[price]
            queue = level.queue
            while remaining > 0 and level.live_count > 0:
                maker = queue[0]
                if maker.qty_units == 0:          # dead (cancelled) entry
                    queue.popleft()
                    continue
                traded = remaining if remaining < maker.qty_units else maker.qty_units
                fills.append({
                    "maker_id": maker.order_id,
                    "taker_id": taker_id,
                    "price_ticks": price,
                    "qty_units": traded,
                })
                remaining -= traded
                maker.qty_units -= traded
                level.live_qty -= traded
                if maker.qty_units == 0:          # maker exhausted
                    queue.popleft()
                    del orders[maker.order_id]
                    level.live_count -= 1
            self._tidy(maker_side, price, level, best=True)
        return fills, remaining

    def _tidy(self, side, price, level, best):
        """Remove an empty level, or compact a queue that is mostly dead."""
        if level.live_count == 0:
            del self.levels[side][price]
            if best:
                self._index_remove_best(side, price)
            else:
                self._index_remove(side, price)
        elif len(level.queue) > 2 * level.live_count:
            level.queue = deque(o for o in level.queue if o.qty_units > 0)
