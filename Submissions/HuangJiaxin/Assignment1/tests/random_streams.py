"""Small random event streams for property and equivalence tests (test helper only)."""
import random


def random_stream(seed, n_events=300, n_prices=6, invalid_share=0.05):
    """Mixed LIMIT / MARKET_SELL / CANCEL events on few prices (to create queues and
    crossings), some cancels of filled or unknown orders, and some invalid events."""
    rng = random.Random(seed)
    events, ids, seq = [], [], 0
    for i in range(n_events):
        seq += rng.choice([1, 1, 1, 2])
        u = rng.random()
        if u < invalid_share:
            e = {"seq": seq, "event_id": f"x{i}", "type": "LIMIT", "order_id": f"bad{i}",
                 "side": rng.choice(["BUY", "SELL", "HOLD"]), "price_ticks": rng.choice([0, -1, 100]),
                 "qty_units": rng.choice([0, -3, 1.5, 10])}
            if rng.random() < 0.3:
                e["seq"] = max(1, seq - 5)           # nonincreasing seq
        elif u < 0.25 and ids:
            target = rng.choice(ids + ["unknown"])
            e = {"seq": seq, "event_id": f"x{i}", "type": "CANCEL", "target_order_id": target}
        elif u < 0.40:
            e = {"seq": seq, "event_id": f"x{i}", "type": "MARKET_SELL", "order_id": f"m{i}",
                 "qty_units": rng.randint(1, 40)}
        else:
            side = rng.choice(["BUY", "SELL"])
            base = 1000 if side == "BUY" else 1003
            price = base + rng.randint(-n_prices // 2, n_prices // 2)    # sometimes crosses
            oid = f"o{rng.randint(0, 10**9)}"                            # spelling unrelated to arrival
            e = {"seq": seq, "event_id": f"x{i}", "type": "LIMIT", "order_id": oid,
                 "side": side, "price_ticks": price, "qty_units": rng.randint(1, 20)}
            ids.append(oid)
        events.append(e)
    return events
