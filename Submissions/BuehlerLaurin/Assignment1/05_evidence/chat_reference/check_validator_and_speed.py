import sys, random, json, gzip, glob, time, statistics
sys.path.insert(0, sys.argv[1] + "/01_code")
from lob import METHODS
from lob.validation import validate
from lob.book_b3r_fast import validate_fast
# 1) validator equivalence on random odd events
rng = random.Random(1); odd = [True, False, 0, -1, 1, 5, 1.0, "5", "", "x", None, [], {}, 10**40, -10**40, "BUY", "SELL", "LIMIT", "CANCEL", "MARKET_SELL", "buy"]
class SubInt(int): pass
odd += [SubInt(5)]
fields = ["seq", "type", "event_id", "order_id", "target_order_id", "side", "price_ticks", "qty_units"]
n = diff = 0
for _ in range(300_000):
    e = {}
    base = {"seq": rng.randint(1, 9), "type": rng.choice(["LIMIT", "MARKET_SELL", "CANCEL"]), "event_id": "e", "order_id": rng.choice(["o1", "o2"]),
            "target_order_id": "o1", "side": rng.choice(["BUY", "SELL"]), "price_ticks": rng.randint(1, 9), "qty_units": rng.randint(1, 9)}
    for f in fields:
        r = rng.random()
        if r < 0.75: e[f] = base[f]
        elif r < 0.95: e[f] = rng.choice(odd)
    live = rng.choice([set(), {"o1"}, {"o1", "o2"}]).__contains__
    last = rng.randint(0, 6); n += 1
    if validate(e, last, live) != validate_fast(e, last, live): diff += 1
print(f"validator equivalence: {n} random events, differences={diff}")
# 2) speed B3r vs B3r_fast on supplied streams
files = sorted(glob.glob(sys.argv[1] + "/06_data/supplied/*_10000.jsonl.gz"))
for f in files:
    ev = [json.loads(l) for l in gzip.open(f, "rt")]; res = {}
    for v in ("B3r", "B3r_fast"):
        ts = []
        for _ in range(9):
            b = METHODS[("lob", v)](); s = time.perf_counter()
            for e in ev: b.process(e)
            ts.append(time.perf_counter() - s)
        res[v] = statistics.median(ts)
    print(f"{f.split('/')[-1][:-15]:14s} B3r {res['B3r']*1e3:6.1f} ms  fast {res['B3r_fast']*1e3:6.1f} ms  ratio {res['B3r_fast']/res['B3r']:.2f}")
