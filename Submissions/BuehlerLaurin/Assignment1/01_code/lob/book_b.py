"""Version B1: id index, FIFO deques, sorted signed prices and lazy cancellation.

Prices are ascending in each side's list: bids positive, asks negated, so the
best is always at the tail. Empty levels disappear immediately. Dead records
are skipped during matching or compacted when stale > live and stale > 32.
"""
from bisect import bisect_left
from collections import deque

from lob.validation import rejection, validate


class _Order:
    """One record shared by its FIFO deque and the live id index."""
    __slots__ = ("order_id", "side", "price_ticks", "qty_units", "arrival_seq", "alive")

    def __init__(self, event, remaining):
        self.order_id = event["order_id"]
        self.side = event["side"]
        self.price_ticks = event["price_ticks"]
        self.qty_units = remaining
        self.arrival_seq = event["seq"]
        self.alive = True


class _Level:
    __slots__ = ("queue", "live", "stale")

    def __init__(self):
        self.queue = deque()
        self.live = 0
        self.stale = 0


class _Side:
    __slots__ = ("levels", "prices", "sign")

    def __init__(self, sign):
        self.levels = {}              # actual positive price -> level; never a FIFO
        self.prices = []              # signed prices in ascending order
        self.sign = sign


class OperationCounters:
    """Cumulative accepted-event work, allocated only with count_operations=True.

levels_visited includes a best level inspected but found not to cross.
unfilled_qty_units sums returned submission residuals, including resting limits.
stale_discarded counts dead records freed when an empty level is removed.
Snapshots/quotes/rejections do not change any counters.
"""
    __slots__ = ("accepted_events", "limit_events", "market_sell_events", "cancel_events",
                 "makers_touched", "levels_visited", "fills", "unfilled_qty_units",
                 "stale_skipped", "stale_compacted", "stale_discarded", "compactions",
                 "compaction_records_scanned", "active_order_peak", "price_level_peak",
                 "price_list_shifts")

    def __init__(self):
        for name in self.__slots__:
            setattr(self, name, 0)

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__slots__}


class OrderBookB:
    """Same event API as A; count_operations=False selects the ordinary path."""

    def __init__(self, *, count_operations=False):
        self.orders = {}
        self.bids = _Side(1)
        self.asks = _Side(-1)
        self.last_seq = 0
        self.counters = OperationCounters() if count_operations else None

    def process(self, event):
        return self._process(event)

    def AddLimitOrder(self, event):  # noqa: N802 - required API name
        return self._process(event, expected_type="LIMIT")

    def CancelOrder(self, event):  # noqa: N802 - required API name
        return self._process(event, expected_type="CANCEL")

    def FillMarketSell(self, event):  # noqa: N802 - required API name
        return self._process(event, expected_type="MARKET_SELL")

    def _process(self, event, expected_type=None):
        # Shared validation completes before any book, sequence or counter write.
        reason = validate(event, self.last_seq, self.orders.__contains__, expected_type)
        if reason is not None:
            return rejection(event, reason)
        self.last_seq = event["seq"]
        result = self._cancel(event) if event["type"] == "CANCEL" else self._submit(event)
        c = self.counters
        if c is not None:
            c.accepted_events += 1
            if event["type"] == "LIMIT":
                c.limit_events += 1
            elif event["type"] == "MARKET_SELL":
                c.market_sell_events += 1
            else:
                c.cancel_events += 1
            c.unfilled_qty_units += result.get("unfilled_qty_units", 0)
            c.active_order_peak = max(c.active_order_peak, len(self.orders))
            c.price_level_peak = max(c.price_level_peak, len(self.bids.levels) + len(self.asks.levels))
        return result

    def _cancel(self, event):
        record = self.orders.pop(event["target_order_id"], None)
        qty = 0
        if record is not None:
            qty = record.qty_units
            record.alive = False
            side = self.bids if record.side == "BUY" else self.asks
            level = side.levels[record.price_ticks]
            level.live -= 1
            level.stale += 1
            if level.live == 0:
                self._remove_level(side, record.price_ticks, level)
            else:
                self._compact(level)
        return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                "status": "cancelled" if record is not None else "not_found",
                "cancelled_qty_units": qty}

    def _remove_level(self, side, price, level, *, best=False):
        # Matching empties only the best level; cancellation can empty any level.
        del side.levels[price]
        if best:
            side.prices.pop()
        else:
            i = bisect_left(side.prices, side.sign * price)
            if self.counters is not None:
                self.counters.price_list_shifts += len(side.prices) - i - 1
            del side.prices[i]
        if self.counters is not None:
            self.counters.stale_discarded += level.stale
        # The detached level (and any dead records left in its deque) is freed.

    def _compact(self, level):
        if level.stale > level.live and level.stale > 32:
            if self.counters is not None:
                self.counters.compactions += 1
                self.counters.compaction_records_scanned += len(level.queue)
                self.counters.stale_compacted += level.stale
            # Filtering preserves the relative order and identity of all survivors.
            level.queue = deque(record for record in level.queue if record.alive)
            level.stale = 0

    def _submit(self, event):
        is_limit = event["type"] == "LIMIT"
        side = event["side"] if is_limit else "SELL"
        limit = event["price_ticks"] if is_limit else None
        fills, remaining = self._match(event, side, limit)
        if is_limit:
            if remaining > 0:
                self._rest(event, remaining)
            status = "resting" if remaining > 0 else "filled"
        else:
            status = "filled" if remaining == 0 else ("partial" if fills else "unfilled")
        return {"event_id": event["event_id"], "order_id": event["order_id"], "status": status,
                "unfilled_qty_units": remaining, "fills": fills}

    def _match(self, event, incoming_side, limit):
        side = self.asks if incoming_side == "BUY" else self.bids
        remaining, fills = event["qty_units"], []
        c = self.counters
        while remaining > 0 and side.prices:
            price = side.sign * side.prices[-1]
            level = side.levels[price]
            if c is not None:
                c.levels_visited += 1
            if limit is not None:
                if (incoming_side == "BUY" and price > limit) or (incoming_side == "SELL" and price < limit):
                    break
            # A level always has live orders. Skip cancelled heads before peeking.
            while remaining > 0 and level.live > 0:
                while not level.queue[0].alive:
                    level.queue.popleft()
                    level.stale -= 1
                    if c is not None:
                        c.stale_skipped += 1
                maker = level.queue[0]
                qty = min(remaining, maker.qty_units)
                fills.append({"maker_id": maker.order_id, "taker_id": event["order_id"],
                              "price_ticks": price, "qty_units": qty})
                if c is not None:
                    c.makers_touched += 1
                    c.fills += 1
                remaining -= qty
                maker.qty_units -= qty
                if maker.qty_units == 0:
                    maker.alive = False
                    level.queue.popleft()
                    del self.orders[maker.order_id]
                    level.live -= 1
                # Otherwise maker remains at the front with its original arrival.
            if level.live == 0:
                self._remove_level(side, price, level, best=True)
            else:
                # Fills can lower live below stale even without another cancel.
                self._compact(level)
        return fills, remaining

    def _rest(self, event, remaining):
        side = self.bids if event["side"] == "BUY" else self.asks
        price = event["price_ticks"]
        level = side.levels.get(price)
        if level is None:
            level = _Level()
            side.levels[price] = level
            i = bisect_left(side.prices, side.sign * price)
            if self.counters is not None:
                self.counters.price_list_shifts += len(side.prices) - i
            side.prices.insert(i, side.sign * price)
        record = _Order(event, remaining)
        level.queue.append(record)
        level.live += 1
        self.orders[record.order_id] = record

    def snapshot(self):
        rows = []
        for side in (self.bids, self.asks):
            for signed_price in reversed(side.prices):
                for record in side.levels[side.sign * signed_price].queue:
                    if record.alive:
                        rows.append({"order_id": record.order_id, "side": record.side,
                                     "price_ticks": record.price_ticks, "qty_units": record.qty_units,
                                     "arrival_seq": record.arrival_seq})
        return rows

    def best_bid(self):
        return self.bids.prices[-1] if self.bids.prices else None

    def best_ask(self):
        return -self.asks.prices[-1] if self.asks.prices else None
