import sys, gzip, json, glob, os, random
sys.path.insert(0, sys.argv[1] + "/01_code"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lob import METHODS
from reference_oracle import Book
VERS = ["B3r", "B3r_fast"]
for f in sorted(glob.glob(sys.argv[1] + "/06_data/supplied/*_10000.jsonl.gz")):
    bs = {v: METHODS[("lob", v)]() for v in VERS}; r = Book(); bad = {v: 0 for v in VERS}; n = 0
    for line in gzip.open(f, "rt"):
        e = json.loads(line); n += 1; rr = r.process(dict(e))
        for v, b in bs.items():
            if b.process(dict(e)) != rr: bad[v] += 1
        if n % 500 == 0:
            s = r.snapshot()
            for v, b in bs.items():
                if b.snapshot() != s: bad[v] += 1
    print(f"{os.path.basename(f):28s}", bad, all(b.snapshot() == r.snapshot() for b in bs.values()))
def fuzz(prices_buy, prices_sell, label, runs=30, steps=1500, seed=7):
    rng = random.Random(seed); bad = {v: 0 for v in VERS}; total = 0
    for run in range(runs):
        bs = {v: METHODS[("lob", v)]() for v in VERS}; r = Book(); seq = 0; ids = []; nid = 0
        for step in range(steps):
            seq += 1 if rng.random() > 0.02 else 0
            u = rng.random()
            if u < 0.45:
                nid += 1; oid = rng.choice(ids) if ids and rng.random() < 0.05 else f"o{nid}"
                side = "BUY" if rng.random() < 0.6 else "SELL"
                p = rng.choice(prices_buy(step)) if side == "BUY" else rng.choice(prices_sell(step))
                e = {"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": oid, "side": side, "price_ticks": p, "qty_units": rng.randint(1, 5)}; ids.append(oid)
            elif u < 0.85 and ids:
                e = {"seq": seq, "event_id": f"e{seq}", "type": "CANCEL", "target_order_id": rng.choice(ids)}
            elif u < 0.97:
                nid += 1; e = {"seq": seq, "event_id": f"e{seq}", "type": "MARKET_SELL", "order_id": f"m{nid}", "qty_units": rng.randint(1, 40)}
            else:
                e = {"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": rng.choice([0, True, 1.0, 100]), "qty_units": 1}
            total += 1; rr = r.process(dict(e)); s = r.snapshot()
            bb = (r.best("BUY") or {}).get("price"); ba = (r.best("SELL") or {}).get("price")
            for v, b in bs.items():
                if b.process(dict(e)) != rr or b.snapshot() != s or b.best_bid() != bb or b.best_ask() != ba: bad[v] += 1
    print(f"fuzz {label}: events={total}", bad)
fuzz(lambda s: [98, 99, 100], lambda s: [100, 101, 102, 103], "few prices / long queues")
fuzz(lambda s: list(range(50, 100)), lambda s: list(range(95, 150)), "many prices, crossing", seed=8)
fuzz(lambda s: list(range(1000 - s // 3, 1010 - s // 3)), lambda s: list(range(1005 - s // 3, 1020 - s // 3)), "drifting prices (heap stale keys)", seed=9)
