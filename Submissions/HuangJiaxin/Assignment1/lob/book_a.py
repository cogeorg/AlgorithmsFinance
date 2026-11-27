"""Version A: transparent baseline.

Data organization: ONE Python list `self.orders` holding every active order (both sides)
in arrival order. Each order is a small dict. Nothing else is indexed.

    best opposite order  = scan the whole list for the best price, ties -> smallest seq
    cancel / live check  = scan the list for the identifier
    remove an order      = list.remove (shifts the later elements)

Pseudocode (B = active orders, F = maker fills of one event):
    AddLimitOrder(e):  validate; while e has quantity and best opposite crosses:
                           trade min(q_in, q_rest) at the resting price; remove exhausted maker
                       if quantity remains: append e to the list (arrival rank = e.seq)
    FillMarketSell(e): validate; while quantity remains and a bid exists:
                           trade with the best bid as above; residual is discarded
    CancelOrder(e):    validate; find the target by scanning; remove it if found
Cost: every fill scans the list, O(B), and removing a maker is O(B), so one event costs
O((F + 1) * B). Cancel and the duplicate-id check are O(B). Space: O(B) for the book,
O(F) for the returned fills; no history is kept.
"""
from . import validation
from .interface import (STATUS_CANCELLED, STATUS_FILLED, STATUS_NOT_FOUND,
                        STATUS_PARTIAL, STATUS_RESTING, STATUS_UNFILLED)


class OrderBookA:
    name = "A"

    def __init__(self):
        self.orders = []          # active orders in arrival order: dicts
        self.last_seq = None      # last accepted seq

    # ------------------------------------------------------------------ helpers
    def _find(self, order_id):
        for o in self.orders:
            if o["order_id"] == order_id:
                return o
        return None

    def _is_live(self, order_id):
        return self._find(order_id) is not None

    def _best(self, side):
        """Best active order on `side`: highest bid / lowest ask, ties by arrival."""
        best = None
        for o in self.orders:
            if o["side"] != side:
                continue
            if best is None:
                best = o
            elif side == "BUY" and o["price_ticks"] > best["price_ticks"]:
                best = o
            elif side == "SELL" and o["price_ticks"] < best["price_ticks"]:
                best = o
            elif o["price_ticks"] == best["price_ticks"] and o["arrival_seq"] < best["arrival_seq"]:
                best = o
        return best

    def _validate(self, event, expected_type=None):
        reason = validation.check(event, self.last_seq, self._is_live)
        if reason is None and expected_type and event["type"] != expected_type:
            reason = f"expected a {expected_type} event"
        return reason

    def _match(self, taker_id, opposite_side, quantity, limit_price=None):
        """Trade against the best opposite orders; return (fills, remaining quantity)."""
        fills = []
        while quantity > 0:
            maker = self._best(opposite_side)
            if maker is None:
                break
            if limit_price is not None:
                if opposite_side == "SELL" and maker["price_ticks"] > limit_price:
                    break
                if opposite_side == "BUY" and maker["price_ticks"] < limit_price:
                    break
            traded = min(quantity, maker["qty_units"])
            fills.append({"maker_id": maker["order_id"], "taker_id": taker_id,
                          "price_ticks": maker["price_ticks"], "qty_units": traded})
            quantity -= traded
            maker["qty_units"] -= traded
            if maker["qty_units"] == 0:
                self.orders.remove(maker)
        return fills, quantity

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
            self.orders.append({"order_id": event["order_id"], "side": side,
                                "price_ticks": price, "qty_units": rest,
                                "arrival_seq": event["seq"]})
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
        target = self._find(event["target_order_id"])
        if target is None:
            return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                    "status": STATUS_NOT_FOUND, "cancelled_qty_units": 0}
        self.orders.remove(target)
        return {"event_id": event["event_id"], "target_order_id": event["target_order_id"],
                "status": STATUS_CANCELLED, "cancelled_qty_units": target["qty_units"]}

    def snapshot(self):
        bids = sorted((o for o in self.orders if o["side"] == "BUY"),
                      key=lambda o: (-o["price_ticks"], o["arrival_seq"]))
        asks = sorted((o for o in self.orders if o["side"] == "SELL"),
                      key=lambda o: (o["price_ticks"], o["arrival_seq"]))
        return {"bids": [dict(o) for o in bids], "asks": [dict(o) for o in asks]}

    def best_bid(self):
        o = self._best("BUY")
        return o["price_ticks"] if o else None

    def best_ask(self):
        o = self._best("SELL")
        return o["price_ticks"] if o else None

    def active_order_count(self):
        return len(self.orders)

    def price_level_count(self):
        return len({(o["side"], o["price_ticks"]) for o in self.orders})

    AddLimitOrder = add_limit_order
    CancelOrder = cancel_order
    FillMarketSell = fill_market_sell
