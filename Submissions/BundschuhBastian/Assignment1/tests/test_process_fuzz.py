"""A and B must give identical results (also for invalid events) on fuzzed streams.

Validation is shared code, but Version B has a fast path in process(); this test checks that
the fast path and the reference validate() agree through the whole process() entry point.
"""
import random

from lob.version_a import OrderBookA
from lob.version_b import OrderBookB

BAD = [None, True, False, 0, -1, 1, 7, 2**70, 1.0, "", "x", "BUY", "SELL", "o1", "o2",
       "LIMIT", "CANCEL", "MARKET_SELL", [], {}, (1,)]


def random_event(rng, seq):
    kind = rng.choice(["LIMIT", "LIMIT", "MARKET_SELL", "CANCEL"])
    oid = f"o{rng.randint(1, 12)}"
    ev = {"seq": seq, "event_id": f"e{seq}", "type": kind}
    if kind == "LIMIT":
        ev.update(order_id=oid, side=rng.choice(["BUY", "SELL"]),
                  price_ticks=rng.randint(95, 105), qty_units=rng.randint(1, 5))
    elif kind == "MARKET_SELL":
        ev.update(order_id=oid, qty_units=rng.randint(1, 8))
    else:
        ev["target_order_id"] = f"o{rng.randint(1, 12)}"
    for _ in range(rng.choice([0, 0, 0, 1, 2])):          # corrupt some events
        key = rng.choice(list(ev) + ["extra"])
        if rng.random() < 0.3:
            ev.pop(key, None)
        else:
            ev[key] = rng.choice(BAD)
    return ev


def test_a_and_b_agree_on_fuzzed_streams():
    for seed in range(60):
        rng = random.Random(seed)
        a, b = OrderBookA(), OrderBookB()
        seq = 0
        for _ in range(300):
            seq += rng.choice([1, 1, 1, 2, 0, -1])          # sometimes not increasing
            ev = random_event(rng, max(seq, 0))
            if rng.random() < 0.02:
                ev = rng.choice([None, 5, "x", [], {"_parse_error": 3}])
            assert a.process(ev) == b.process(ev), (seed, ev)
            assert a.snapshot() == b.snapshot(), (seed, ev)
