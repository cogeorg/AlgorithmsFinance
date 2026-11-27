"""Version A: individual orders in a list, with explicit price-time scans."""
from .common import Engine, canonical


class OrderBook(Engine):
    def __init__(self, instrument=False):
        super().__init__(instrument)
        self.orders = []

    def _contains(self, ident):
        self.count("id_scan_upper_bound", len(self.orders))
        return any(row["order_id"] == ident for row in self.orders)

    def _insert(self, row):
        self.orders.append(row)
        self.count("inserts")

    def _cancel(self, ident):
        for index, row in enumerate(self.orders):
            if row["order_id"] == ident:
                self.count("cancel_entries_scanned", index + 1)
                self.count("list_entries_shifted", len(self.orders) - index - 1)
                return self.orders.pop(index)["qty_units"]
        self.count("cancel_entries_scanned", len(self.orders))
        return 0

    def _match(self, event):
        remaining, fills = event["qty_units"], []
        buy = event["type"] == "LIMIT" and event["side"] == "BUY"
        opposite = "SELL" if buy else "BUY"
        limit_price = event.get("price_ticks") if event["type"] == "LIMIT" else None
        prices = set() if self.metrics is not None else None
        while remaining:
            best, best_key, best_index = None, None, None
            self.count("matching_entries_scanned", len(self.orders))
            for index, row in enumerate(self.orders):
                if row["side"] != opposite:
                    continue
                price = row["price_ticks"]
                if limit_price is not None and ((buy and price > limit_price) or
                                                 (not buy and price < limit_price)):
                    continue
                key = (price if buy else -price, row["arrival_seq"])
                if best_key is None or key < best_key:
                    best, best_key, best_index = row, key, index
            if best is None:
                break
            qty = min(remaining, best["qty_units"])
            fills.append(dict(maker_id=best["order_id"], taker_id=event["order_id"],
                              price_ticks=best["price_ticks"], qty_units=qty))
            if prices is not None:
                prices.add(best["price_ticks"])
            remaining -= qty
            best["qty_units"] -= qty
            self.count("maker_fills")
            if not best["qty_units"]:
                self.count("list_entries_shifted", len(self.orders) - best_index - 1)
                self.orders.pop(best_index)
        if prices is not None:
            self.count("filled_price_levels", len(prices))
        return fills, remaining

    def inspect(self):
        return canonical(self.orders)

    def storage(self):
        return dict(active_orders=len(self.orders), stored_orders=len(self.orders),
                    occupied_prices=len({(r["side"], r["price_ticks"]) for r in self.orders}),
                    stale_entries=0)
