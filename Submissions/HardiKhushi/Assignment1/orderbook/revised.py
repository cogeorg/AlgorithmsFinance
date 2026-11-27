"""Version B: sorted occupied prices, FIFO OrderedDicts and an identifier index.

No tombstones, delayed cleanup or retained event/trade history. Price-list
insertion/removal costs O(P); hash operations use expected O(1) assumptions.
"""
from bisect import bisect_left, insort
from collections import OrderedDict
from .common import Engine, canonical


class OrderBook(Engine):
    def __init__(self, instrument=False):
        super().__init__(instrument)
        self.by_id = {}
        self.levels = {"BUY": {}, "SELL": {}}
        self.prices = {"BUY": [], "SELL": []}

    def _contains(self, ident):
        self.count("id_lookups")
        return ident in self.by_id

    def _insert(self, row):
        side, price = row["side"], row["price_ticks"]
        if price not in self.levels[side]:
            position = bisect_left(self.prices[side], price)
            self.count("price_entries_shifted", len(self.prices[side]) - position)
            insort(self.prices[side], price)
            self.levels[side][price] = OrderedDict()
        self.levels[side][price][row["order_id"]] = row
        self.by_id[row["order_id"]] = row
        self.count("inserts")

    def _erase(self, row):
        side, price, ident = row["side"], row["price_ticks"], row["order_id"]
        queue = self.levels[side][price]
        del queue[ident]
        del self.by_id[ident]
        if not queue:
            del self.levels[side][price]
            position = bisect_left(self.prices[side], price)
            self.count("price_entries_shifted", len(self.prices[side]) - position - 1)
            self.prices[side].pop(position)
            if not self.levels[side]:
                self.levels[side].clear()
        if not self.by_id:
            self.by_id.clear()

    def _cancel(self, ident):
        self.count("cancel_lookups")
        row = self.by_id.get(ident)
        if row is None:
            return 0
        qty = row["qty_units"]
        self._erase(row)
        return qty

    def _match(self, event):
        remaining, fills = event["qty_units"], []
        buy = event["type"] == "LIMIT" and event["side"] == "BUY"
        side = "SELL" if buy else "BUY"
        prices, levels = self.prices[side], self.levels[side]
        limit_price = event.get("price_ticks") if event["type"] == "LIMIT" else None
        previous_price = None
        while remaining and prices:
            self.count("best_price_reads")
            price = prices[0] if buy else prices[-1]
            if limit_price is not None and ((buy and price > limit_price) or
                                             (not buy and price < limit_price)):
                break
            queue = levels[price]
            maker_id = next(iter(queue))
            maker = queue[maker_id]
            qty = min(remaining, maker["qty_units"])
            fills.append(dict(maker_id=maker_id, taker_id=event["order_id"],
                              price_ticks=price, qty_units=qty))
            if previous_price != price:
                self.count("filled_price_levels")
                previous_price = price
            self.count("maker_fills")
            remaining -= qty
            maker["qty_units"] -= qty
            if not maker["qty_units"]:
                self._erase(maker)
        return fills, remaining

    def inspect(self):
        return canonical(self.by_id.values())

    def storage(self):
        return dict(active_orders=len(self.by_id), stored_orders=sum(
            len(queue) for levels in self.levels.values() for queue in levels.values()),
            occupied_prices=sum(len(prices) for prices in self.prices.values()),
            stale_entries=0)
