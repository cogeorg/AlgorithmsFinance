"""Independent reference LOB (written by Claude chat, not by the coding agent) to cross-check the own expected files."""
import json, sys, glob, os

TYPES = ("LIMIT", "MARKET_SELL", "CANCEL")
REQ = {"LIMIT": ["event_id", "order_id", "side", "price_ticks", "qty_units"],
       "MARKET_SELL": ["event_id", "order_id", "qty_units"],
       "CANCEL": ["event_id", "target_order_id"]}

def posint(x):
    return type(x) is int and x > 0

class Book:
    def __init__(self):
        self.orders = []  # dicts: id, side, price, qty, seq
        self.last_seq = 0

    def live(self, oid):
        return any(o["id"] == oid for o in self.orders)

    def validate(self, e):
        if not isinstance(e, dict): return "not_an_object"
        if "seq" not in e: return "missing_field:seq"
        if not posint(e["seq"]): return "bad_seq"
        if e["seq"] <= self.last_seq: return "nonincreasing_seq"
        if "type" not in e: return "missing_field:type"
        t = e["type"]
        if t not in TYPES: return "unknown_type"
        for f in REQ[t]:
            if f not in e: return "missing_field:" + f
        for f in ("event_id", "order_id", "target_order_id"):
            if f in REQ[t] and not (isinstance(e[f], str) and e[f] != ""):
                return "bad_id:" + f
        if t == "LIMIT" and e["side"] not in ("BUY", "SELL"): return "unknown_side"
        if t == "LIMIT" and not posint(e["price_ticks"]): return "bad_price"
        if t in ("LIMIT", "MARKET_SELL") and not posint(e["qty_units"]): return "bad_qty"
        if t in ("LIMIT", "MARKET_SELL") and self.live(e["order_id"]): return "duplicate_live_order_id"
        return None

    def best(self, side):
        c = [o for o in self.orders if o["side"] == side]
        if not c: return None
        if side == "BUY":
            return min(c, key=lambda o: (-o["price"], o["seq"]))
        return min(c, key=lambda o: (o["price"], o["seq"]))

    def match(self, taker_id, maker_side, qty, limit):
        fills = []
        while qty > 0:
            m = self.best(maker_side)
            if m is None: break
            if limit is not None:
                if maker_side == "SELL" and not (limit >= m["price"]): break
                if maker_side == "BUY" and not (limit <= m["price"]): break
            q = min(qty, m["qty"])
            fills.append({"maker_id": m["id"], "taker_id": taker_id, "price_ticks": m["price"], "qty_units": q})
            qty -= q; m["qty"] -= q
            if m["qty"] == 0: self.orders.remove(m)
        return fills, qty

    def process(self, e):
        r = self.validate(e)
        if r:
            eid = e.get("event_id") if isinstance(e, dict) else None
            if not (isinstance(eid, str) and eid): eid = None
            return {"event_id": eid, "status": "rejected", "reason": r}
        self.last_seq = e["seq"]
        t = e["type"]
        if t == "CANCEL":
            for o in self.orders:
                if o["id"] == e["target_order_id"]:
                    self.orders.remove(o)
                    return {"event_id": e["event_id"], "target_order_id": e["target_order_id"], "status": "cancelled", "cancelled_qty_units": o["qty"]}
            return {"event_id": e["event_id"], "target_order_id": e["target_order_id"], "status": "not_found", "cancelled_qty_units": 0}
        if t == "MARKET_SELL":
            fills, rest = self.match(e["order_id"], "BUY", e["qty_units"], None)
            st = "filled" if rest == 0 else ("partial" if fills else "unfilled")
            return {"event_id": e["event_id"], "order_id": e["order_id"], "status": st, "unfilled_qty_units": rest, "fills": fills}
        opp = "SELL" if e["side"] == "BUY" else "BUY"
        fills, rest = self.match(e["order_id"], opp, e["qty_units"], e["price_ticks"])
        if rest > 0:
            self.orders.append({"id": e["order_id"], "side": e["side"], "price": e["price_ticks"], "qty": rest, "seq": e["seq"]})
        return {"event_id": e["event_id"], "order_id": e["order_id"], "status": "resting" if rest else "filled", "unfilled_qty_units": rest, "fills": fills}

    def snapshot(self):
        b = sorted([o for o in self.orders if o["side"] == "BUY"], key=lambda o: (-o["price"], o["seq"]))
        a = sorted([o for o in self.orders if o["side"] == "SELL"], key=lambda o: (o["price"], o["seq"]))
        return [{"order_id": o["id"], "side": o["side"], "price_ticks": o["price"], "qty_units": o["qty"], "arrival_seq": o["seq"]} for o in b + a]

def run(jsonl, expfile):
    exp = json.load(open(expfile))
    bk = Book(); res = []
    for line in open(jsonl):
        if line.strip():
            res.append(bk.process(json.loads(line)))
    probs = []
    if len(res) != len(exp["results"]): probs.append(f"len {len(res)} vs {len(exp['results'])}")
    for i, (a, b) in enumerate(zip(res, exp["results"])):
        if a != b: probs.append(f"event {i}: ref={a} exp={b}")
    if bk.snapshot() != exp.get("final_book"): probs.append("final_book differs")
    bb = bk.best("BUY"); ba = bk.best("SELL")
    if (bb and bb["price"]) != exp.get("best_bid") or (ba and ba["price"]) != exp.get("best_ask"): probs.append("best differs")
    return probs

if __name__ == "__main__":
    d = sys.argv[1]
    for j in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        name = os.path.basename(j)[:-6]
        e = os.path.join(d, name + ".expected.json")
        if not os.path.exists(e):
            e = os.path.join(d, name.replace("example", "expected") + ".json")
        p = run(j, e)
        print(("OK  " if not p else "FAIL"), name, len(p))
        for x in p[:5]: print("   ", x)
