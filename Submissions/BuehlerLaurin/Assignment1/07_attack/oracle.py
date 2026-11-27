"""Independent oracle for the attack (own/attack). Written from SPEC.md only, BEFORE
01_code was opened. Shares no code with the engines. Deliberately naive: one flat list
of order dicts, sorted from scratch for every decision. No imports from 01_code."""

TYPES = ("LIMIT", "MARKET_SELL", "CANCEL")
REQUIRED = {
    "LIMIT": ("event_id", "order_id", "side", "price_ticks", "qty_units"),
    "MARKET_SELL": ("event_id", "order_id", "qty_units"),
    "CANCEL": ("event_id", "target_order_id"),
}
METHOD_TYPE = {"AddLimitOrder": "LIMIT", "FillMarketSell": "MARKET_SELL",
               "CancelOrder": "CANCEL", "process": None}


def _pos_int(x):
    return type(x) is int and x > 0


def _text(x):
    return type(x) is str and x != ""


class Oracle:
    def __init__(self):
        self.live = []          # dicts in snapshot form
        self.last_seq = 0

    # --- SPEC table rules 1..13, in order -------------------------------------
    def reason(self, e, expected=None):
        if type(e) is not dict:
            return "not_an_object"                                   # 1
        if "seq" not in e:
            return "missing_field:seq"                               # 2
        if not _pos_int(e["seq"]):
            return "bad_seq"                                         # 3
        if e["seq"] <= self.last_seq:
            return "nonincreasing_seq"                               # 4
        if "type" not in e:
            return "missing_field:type"                              # 5
        if type(e["type"]) is not str or e["type"] not in TYPES:
            return "unknown_type"                                    # 6
        if expected is not None and e["type"] != expected:
            return "wrong_type_for_method"                           # 7
        for name in REQUIRED[e["type"]]:
            if name not in e:
                return "missing_field:" + name                       # 8
        id_names = ("event_id", "target_order_id" if e["type"] == "CANCEL" else "order_id")
        for name in id_names:
            if not _text(e[name]):
                return "bad_id:" + name                              # 9
        if e["type"] == "LIMIT":
            if type(e["side"]) is not str or e["side"] not in ("BUY", "SELL"):
                return "unknown_side"                                # 10
            if not _pos_int(e["price_ticks"]):
                return "bad_price"                                   # 11
        if e["type"] != "CANCEL":
            if not _pos_int(e["qty_units"]):
                return "bad_qty"                                     # 12
            if any(o["order_id"] == e["order_id"] for o in self.live):
                return "duplicate_live_order_id"                     # 13
        return None

    def call(self, method, e):
        why = self.reason(e, METHOD_TYPE[method])
        if why:
            eid = e.get("event_id") if type(e) is dict else None
            return {"event_id": eid if _text(eid) else None,
                    "status": "rejected", "reason": why}
        self.last_seq = e["seq"]
        if e["type"] == "CANCEL":
            return self._cancel(e)
        return self._submit(e)

    def process(self, e):
        return self.call("process", e)

    # --- matching rules 1..5 --------------------------------------------------
    def _cancel(self, e):
        qty = 0
        for o in self.live:
            if o["order_id"] == e["target_order_id"]:
                qty = o["qty_units"]
        self.live = [o for o in self.live if o["order_id"] != e["target_order_id"]]
        return {"event_id": e["event_id"], "target_order_id": e["target_order_id"],
                "status": "cancelled" if qty else "not_found", "cancelled_qty_units": qty}

    def _submit(self, e):
        market = e["type"] == "MARKET_SELL"
        side = "SELL" if market else e["side"]
        left, fills = e["qty_units"], []
        while left:
            makers = [o for o in self.snapshot() if o["side"] != side]
            if not makers:
                break
            best = makers[0]
            if not market and (best["price_ticks"] > e["price_ticks"] if side == "BUY"
                               else best["price_ticks"] < e["price_ticks"]):
                break
            q = min(left, best["qty_units"])
            fills.append({"maker_id": best["order_id"], "taker_id": e["order_id"],
                          "price_ticks": best["price_ticks"], "qty_units": q})
            left -= q
            for o in self.live:
                if o["order_id"] == best["order_id"]:
                    o["qty_units"] -= q
            self.live = [o for o in self.live if o["qty_units"]]
        res = {"event_id": e["event_id"], "order_id": e["order_id"],
               "unfilled_qty_units": left, "fills": fills}
        if market:
            res["status"] = "filled" if not left else ("partial" if fills else "unfilled")
        else:
            res["status"] = "resting" if left else "filled"
            if left:
                self.live.append({"order_id": e["order_id"], "side": side,
                                  "price_ticks": e["price_ticks"], "qty_units": left,
                                  "arrival_seq": e["seq"]})
        return res

    # --- inspection -----------------------------------------------------------
    def snapshot(self):
        bids = sorted((o for o in self.live if o["side"] == "BUY"),
                      key=lambda o: (-o["price_ticks"], o["arrival_seq"]))
        asks = sorted((o for o in self.live if o["side"] == "SELL"),
                      key=lambda o: (o["price_ticks"], o["arrival_seq"]))
        return [dict(o) for o in bids + asks]

    def best_bid(self):
        return max((o["price_ticks"] for o in self.live if o["side"] == "BUY"), default=None)

    def best_ask(self):
        return min((o["price_ticks"] for o in self.live if o["side"] == "SELL"), default=None)
