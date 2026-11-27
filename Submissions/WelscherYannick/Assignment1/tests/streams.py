"""Small random event streams for tests (own generator, separate from generate_orders.py).

Few prices so queues, crossings, partial fills, stale cancels and invalid events are common.
"""
import random


def random_stream(seed, n=200, prices=4, invalid_rate=0.06):
    rng = random.Random(seed)
    seq = 0
    ids = []
    out = []
    for i in range(n):
        seq += rng.choice((1, 1, 1, 2, 7))  # gaps are allowed; only increase matters
        ev = {"seq": seq, "event_id": f"x{seed}_{i}"}
        r = rng.random()
        if r < 0.20 and ids:
            ev.update(type="CANCEL", target_order_id=rng.choice(ids + ["never-submitted"]))
        elif r < 0.35:
            oid = f"{rng.choice('zyxabm')}{i}"  # spelling order differs from arrival order
            ev.update(type="MARKET_SELL", order_id=oid, qty_units=rng.randint(1, 40))
            ids.append(oid)
        else:
            side = rng.choice(("BUY", "SELL"))
            offset = rng.randrange(prices)
            price = 100 - offset if side == "BUY" else 101 + offset
            if rng.random() < 0.25:  # cross the spread
                price = price + prices + 1 if side == "BUY" else price - prices - 1
            oid = f"{rng.choice('zyxabm')}{i}"
            ev.update(type="LIMIT", order_id=oid, side=side, price_ticks=price,
                      qty_units=rng.randint(1, 20))
            ids.append(oid)
        if rng.random() < invalid_rate:
            ev = _corrupt(rng, ev, seq, ids)
        out.append(ev)
    return out


def _corrupt(rng, ev, seq, ids):
    ev = dict(ev)
    choice = rng.randrange(10)
    if choice == 0:
        ev["seq"] = max(0, seq - rng.randint(1, 3))  # nonincreasing (may or may not be)
    elif choice == 1:
        ev["type"] = "MARKET_BUY"
    elif choice == 2 and ev["type"] == "LIMIT":
        ev["side"] = rng.choice(("buy", "HOLD", None))
    elif choice == 3 and "qty_units" in ev:
        ev["qty_units"] = rng.choice((0, -5, 1.0, True, "5", None))
    elif choice == 4 and ev["type"] == "LIMIT":
        ev["price_ticks"] = rng.choice((0, -100, 100.5, 100.0, True, "100", None))
    elif choice == 5 and ids and ev["type"] in ("LIMIT", "MARKET_SELL"):
        ev["order_id"] = rng.choice(ids)  # duplicate if still live, otherwise historical reuse
    elif choice == 6:
        ev["seq"] = rng.choice((True, 1.5, "9", None))
    elif choice == 7:
        del ev["event_id"]
    elif choice == 8 and ev["type"] == "CANCEL":
        ev["target_order_id"] = rng.choice((None, 7, ""))
    else:
        ev.pop("order_id", None)
    return ev
