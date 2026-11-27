"""Compare Version A and Version B after EVERY event on small random event streams
(spec: "Add small generated tests and compare your two versions after every event")."""
import random

from orderbook.version_a import OrderBook as BookA
from orderbook.version_b import OrderBook as BookB


def random_events(seed, n_events=300):
    """Small random stream: limits on both sides around 60,000 USD, market sells,
    cancels (sometimes of unknown or already-filled orders) and a few invalid events."""
    rng = random.Random(seed)
    events = []
    ids = []
    for seq in range(1, n_events + 1):
        r = rng.random()
        if r < 0.55:
            oid = f"o{seq}"
            ids.append(oid)
            events.append({"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": oid,
                           "side": rng.choice(["BUY", "SELL"]),
                           "price_ticks": 6_000_000 + rng.randint(-5, 5) * 1_000,
                           "qty_units": rng.randint(1, 5) * 10_000_000})
        elif r < 0.75:
            events.append({"seq": seq, "event_id": f"e{seq}", "type": "MARKET_SELL",
                           "order_id": f"m{seq}", "qty_units": rng.randint(1, 15) * 10_000_000})
        elif r < 0.95:
            target = rng.choice(ids) if ids and rng.random() < 0.8 else "unknown"
            events.append({"seq": seq, "event_id": f"e{seq}", "type": "CANCEL",
                           "target_order_id": target})
        else:
            events.append({"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": f"bad{seq}",
                           "side": "BUY", "price_ticks": 0, "qty_units": 10_000_000})
    return events


def test_versions_agree_after_every_event():
    for seed in range(20):
        a, b = BookA(), BookB()
        for event in random_events(seed):
            result_a = a.process_event(event)
            result_b = b.process_event(event)
            assert result_a == result_b, (seed, event)            # same status, fills (in order), quantities
            assert a.snapshot() == b.snapshot(), (seed, event)    # same remaining book, ids and quantities