"""Version A: transparent baseline limit order book.

Data organisation: ONE plain Python list `self.orders` holding every active
order (both sides) as a small dict

    {"order_id", "side", "price_ticks", "qty_units", "arrival_seq"}

in arrival order. Nothing is indexed or kept sorted. To find the best
resting order the whole list is scanned; to find an order by id the whole
list is scanned too. This is deliberately simple so every step is easy to
check by hand. Costs (B = active orders, F = fills of one event):

    AddLimitOrder   O(B) duplicate-id scan + O(B) scan per fill  -> O(B * (F + 1))
    FillMarketSell  O(B) scan per fill                           -> O(B * (F + 1))
    CancelOrder     O(B) scan to find the target, O(B) list delete
    inspect_book    O(B log B) sort (copies every order)

Units are integers throughout: price_ticks = cents per BTC, qty_units =
1e-8 BTC. Only the current event's fills are returned; no trade history is
stored.

Use `process_event(event)` for raw events: it validates the event first.
The three public operations (AddLimitOrder, FillMarketSell, CancelOrder)
assume their arguments were already validated by process_event.
"""

from validation import validate_event


class OrderBook:
    """Version A order book. Start empty; feed events in seq order."""

    def __init__(self):
        self.orders = []        # every active order, both sides, arrival order
        self.last_seq = 0       # seq of the last accepted (valid) event

    # ----- public operations ---------------------------------------------

    def AddLimitOrder(self, event_id, order_id, side, price_ticks, qty_units, seq):
        """Submit a limit order.

        AddLimitOrder(event_id: str, order_id: str, side: "BUY" | "SELL",
                      price_ticks: int > 0, qty_units: int > 0, seq: int) -> dict

        Matches against the opposite side while prices cross (best price
        first, then earliest arrival_seq), each trade at the resting order's
        price. Any residual rests with arrival_seq = seq.
        Returns {"event_id", "order_id", "status": "filled" | "resting",
                 "unfilled_qty_units", "fills"}.
        """
        fills, remaining = self._match(order_id, side, qty_units, price_ticks)
        if remaining > 0:
            self.orders.append({
                "order_id": order_id,
                "side": side,
                "price_ticks": price_ticks,
                "qty_units": remaining,
                "arrival_seq": seq,
            })
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
        """Sell into the live bids: highest price first, then earliest arrival.

        FillMarketSell(event_id: str, order_id: str, qty_units: int > 0) -> dict

        Mutates the book (makers lose exactly their filled quantity). The
        unfilled residual is discarded and never rests.
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
        Unknown, fully filled or already cancelled targets give not_found, 0.
        """
        for i, order in enumerate(self.orders):
            if order["order_id"] == target_order_id:
                del self.orders[i]
                return {
                    "event_id": event_id,
                    "target_order_id": target_order_id,
                    "status": "cancelled",
                    "cancelled_qty_units": order["qty_units"],
                }
        return {
            "event_id": event_id,
            "target_order_id": target_order_id,
            "status": "not_found",
            "cancelled_qty_units": 0,
        }

    def process_event(self, event):
        """Validate one event and dispatch it.

        process_event(event: dict) -> dict

        Invalid events return {"event_id", "status": "rejected", "reason"}
        and change neither the book nor last_seq.
        """
        reason = validate_event(event, self.last_seq, self._is_live)
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
        Bids first (price desc, then arrival_seq), then asks (price asc,
        then arrival_seq).
        """
        bids = [dict(o) for o in self.orders if o["side"] == "BUY"]
        asks = [dict(o) for o in self.orders if o["side"] == "SELL"]
        bids.sort(key=lambda o: (-o["price_ticks"], o["arrival_seq"]))
        asks.sort(key=lambda o: (o["price_ticks"], o["arrival_seq"]))
        return bids + asks

    def assert_invariants(self):
        """Raise AssertionError if the stored book breaks a structural invariant.

        Checks: valid side, positive integer quantity, no order_id stored
        twice, and no crossed book (best bid < best ask when both exist).
        """
        seen = set()
        best_bid = None
        best_ask = None
        for o in self.orders:
            assert o["side"] in ("BUY", "SELL"), o
            assert type(o["qty_units"]) is int and o["qty_units"] > 0, o
            assert o["order_id"] not in seen, f"stored twice: {o['order_id']}"
            seen.add(o["order_id"])
            p = o["price_ticks"]
            if o["side"] == "BUY":
                best_bid = p if best_bid is None else max(best_bid, p)
            else:
                best_ask = p if best_ask is None else min(best_ask, p)
        if best_bid is not None and best_ask is not None:
            assert best_bid < best_ask, f"crossed book: {best_bid} >= {best_ask}"

    # ----- internals -------------------------------------------------------

    def _is_live(self, order_id):
        """True if order_id is an active order. O(B) scan."""
        for o in self.orders:
            if o["order_id"] == order_id:
                return True
        return False

    def _best_index(self, maker_side):
        """Index of the best resting order on maker_side, or None. O(B) scan.

        Bids: highest price, then earliest arrival_seq.
        Asks: lowest price, then earliest arrival_seq.
        """
        best_i = None
        best_key = None
        for i, o in enumerate(self.orders):
            if o["side"] != maker_side:
                continue
            if maker_side == "BUY":
                key = (-o["price_ticks"], o["arrival_seq"])
            else:
                key = (o["price_ticks"], o["arrival_seq"])
            if best_key is None or key < best_key:
                best_i, best_key = i, key
        return best_i

    def _match(self, taker_id, taker_side, qty_units, limit_price):
        """Trade an incoming order against the book.

        limit_price None means a market order (no price limit).
        Returns (fills, remaining_qty).
        """
        maker_side = "SELL" if taker_side == "BUY" else "BUY"
        fills = []
        remaining = qty_units
        while remaining > 0:
            i = self._best_index(maker_side)
            if i is None:
                break
            maker = self.orders[i]
            price = maker["price_ticks"]
            if limit_price is not None:
                if taker_side == "BUY" and limit_price < price:
                    break
                if taker_side == "SELL" and limit_price > price:
                    break
            traded = min(remaining, maker["qty_units"])
            fills.append({
                "maker_id": maker["order_id"],
                "taker_id": taker_id,
                "price_ticks": price,
                "qty_units": traded,
            })
            remaining -= traded
            maker["qty_units"] -= traded
            if maker["qty_units"] == 0:
                del self.orders[i]
        return fills, remaining
