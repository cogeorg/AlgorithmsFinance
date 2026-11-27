"""Larger differential campaign (own/attack). python -B 07_attack/campaign.py [seeds] [events]
Every registered version vs oracle.py after EVERY event (result, snapshot, best bid/ask,
last_seq), plus a pass with inspection only every 97 events (so quotes cannot clean lazily)."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "01_code"), str(ROOT / "07_attack")]
from fuzz import REGIMES, compare, gen, shrink  # noqa: E402
from lob import METHODS  # noqa: E402
from oracle import Oracle  # noqa: E402

seeds, n = int(sys.argv[1]), int(sys.argv[2])


# fuzzer power check: each planted bug must be found
class Lifo(Oracle):
    def snapshot(self):
        k = lambda o: (o["price_ticks"], -o["arrival_seq"])  # noqa: E731
        return (sorted((o for o in self.live if o["side"] == "BUY"), key=lambda o: (-o["price_ticks"], -o["arrival_seq"]))
                + sorted((o for o in self.live if o["side"] == "SELL"), key=k))


class SeqOnReject(Oracle):
    def call(self, m, e):
        r = super().call(m, e)
        if r["status"] == "rejected" and isinstance(e, dict) and type(e.get("seq")) is int and e["seq"] > self.last_seq:
            self.last_seq = e["seq"]
        return r


class RestMarket(Oracle):
    def _submit(self, e):
        return super()._submit(e if e["type"] == "LIMIT" else {**e, "type": "LIMIT", "side": "SELL", "price_ticks": 1})


class StrictCross(Oracle):
    def _submit(self, e):
        if e["type"] == "LIMIT":
            p = e["price_ticks"] + (-1 if e["side"] == "BUY" else 1)
            r = super()._submit({**e, "price_ticks": p})
            for o in self.live:
                if o["order_id"] == e["order_id"]:
                    o["price_ticks"] = e["price_ticks"]
            return r
        return super()._submit(e)


class OneEntryCancelZero(Oracle):
    def _cancel(self, e):
        r = super()._cancel(e)
        if r["status"] == "cancelled" and len(self.live) > 40:
            r["cancelled_qty_units"] += 1
        return r


t0 = time.time()
for mut in (Lifo, SeqOnReject, RestMarket, StrictCross, OneEntryCancelZero):
    hit = next(((reg, s) for s in range(30) for reg in REGIMES if compare(mut, gen(s, n, reg))), None)
    print("planted bug", mut.__name__, "found at" if hit else "NOT FOUND", hit, flush=True)
    assert hit
bad = 0
for (_, v), f in METHODS.items():
    for reg in REGIMES:
        ev_total = 0
        for s in range(seeds):
            ev = gen(10_000 + s, n, reg)
            ev_total += len(ev)
            for kw in ({}, {"inspect": False}):
                d = compare(f, ev, **kw)
                if d:
                    bad += 1
                    print("BREAK", v, reg, s, kw, d, shrink(f, ev, **kw), flush=True)
                    break
        print(f"{v:3} {reg:7} seeds 10000..{10_000 + seeds - 1} x {n} events = {ev_total} events, 2 passes: breaks so far {bad}", flush=True)
print("total breaks", bad, "seconds", round(time.time() - t0))
