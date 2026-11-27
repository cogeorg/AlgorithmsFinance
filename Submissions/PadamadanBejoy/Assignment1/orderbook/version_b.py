"""Version B: price levels with FIFO queues, sorted price lists and an order index."""
from bisect import insort
from collections import deque

from orderbook.validation import validate


class OrderBook:
    def __init__(self):
        self.levels = {"BUY": {}, "SELL": {}}     # side -> {price: deque of orders (FIFO)}
        self.prices = {"BUY": [], "SELL": []}     # side -> sorted list of occupied prices (ascending)
        self.index = {}                           # order_id -> order dict (only active orders)
        self.last_seq = 0

    def process_event(self, event):
        reason = validate(event, self.last_seq, self.is_live)
        if reason is not None:
            return {"event_id": event.get("event_id") if isinstance(event, dict) else None,
                    "status": "rejected", "reason": reason}
        self.last_seq = event["seq"]
        if event["type"] == "LIMIT":
            return self.AddLimitOrder(event)
        elif event["type"] == "MARKET_SELL":
            return self.FillMarketSell(event)
        elif event["type"] == "CANCEL":
            return self.CancelOrder(event)

    def is_live(self, order_id):
        return order_id in self.index             # one dictionary lookup, no scan

    def _best_price(self, side):
        prices = self.prices[side]
        if not prices:
            return None
        return prices[-1] if side == "BUY" else prices[0]   # highest bid / lowest ask

    def _remove_level(self, side, price):
        del self.levels[side][price]
        self.prices[side].remove(price)

    def _match(self, taker_id, side, remaining, limit_price):
        other = "SELL" if side == "BUY" else "BUY"
        fills = []
        while remaining > 0:
            price = self._best_price(other)
            if price is None:
                break                                     # other side is empty
            if limit_price is not None:
                if side == "BUY" and price > limit_price:
                    break                                 # best ask too expensive
                if side == "SELL" and price < limit_price:
                    break                                 # best bid too low
            queue = self.levels[other][price]
            maker = queue[0]                              # earliest arrival at this price
            qty = min(remaining, maker["qty_units"])
            fills.append({"maker_id": maker["order_id"], "taker_id": taker_id,
                          "price_ticks": price, "qty_units": qty})
            maker["qty_units"] -= qty
            remaining -= qty
            if maker["qty_units"] == 0:
                queue.popleft()                           # remove used-up maker from the front
                del self.index[maker["order_id"]]
                if not queue:
                    self._remove_level(other, price)      # price level now empty
        return fills, remaining

    def _rest(self, event, qty):
        side, price = event["side"], event["price_ticks"]
        order = {"order_id": event["order_id"], "side": side, "price_ticks": price,
                 "qty_units": qty, "arrival_seq": event["seq"]}
        if price not in self.levels[side]:
            self.levels[side][price] = deque()            # new price level
            insort(self.prices[side], price)              # keep prices sorted
        self.levels[side][price].append(order)            # join the BACK of the queue
        self.index[order["order_id"]] = order

    def AddLimitOrder(self, event):
        fills, remaining = self._match(event["order_id"], event["side"],
                                       event["qty_units"], event["price_ticks"])
        if remaining > 0:
            self._rest(event, remaining)
            status = "resting"
        else:
            status = "filled"
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": status, "unfilled_qty_units": remaining, "fills": fills}

    def FillMarketSell(self, event):
        fills, remaining = self._match(event["order_id"], "SELL", event["qty_units"], None)
        if remaining == 0:
            status = "filled"
        elif len(fills) > 0:
            status = "partial"
        else:
            status = "unfilled"
        return {"event_id": event["event_id"], "order_id": event["order_id"],
                "status": status, "unfilled_qty_units": remaining, "fills": fills}

    def CancelOrder(self, event):
        target = event["target_order_id"]
        order = self.index.pop(target, None)              # find + remove from index in one step
        if order is None:
            return {"event_id": event["event_id"], "target_order_id": target,
                    "status": "not_found", "cancelled_qty_units": 0}
        side, price = order["side"], order["price_ticks"]
        queue = self.levels[side][price]
        queue.remove(order)
        if not queue:
            self._remove_level(side, price)
        return {"event_id": event["event_id"], "target_order_id": target,
                "status": "cancelled", "cancelled_qty_units": order["qty_units"]}

    def snapshot(self):
        result = []
        for price in reversed(self.prices["BUY"]):        # bids: highest price first
            result.extend(dict(o) for o in self.levels["BUY"][price])
        for price in self.prices["SELL"]:                 # asks: lowest price first
            result.extend(dict(o) for o in self.levels["SELL"][price])
        return result