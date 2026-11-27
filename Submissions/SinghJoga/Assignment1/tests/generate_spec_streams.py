import json
import random
from pathlib import Path


SEEDS = (13, 37, 91)
EVENTS_PER_STREAM = 18
PRICE_TICKS = (5990000, 6000000, 6010000)
QUANTITIES = (10000000, 25000000, 50000000)
EVENT_CYCLE = ("LIMIT", "LIMIT", "MARKET_SELL", "CANCEL", "LIMIT", "MARKET_SELL")


def generate_event_stream(seed):
    rng = random.Random(seed)
    events = []
    submitted_order_ids = []

    for seq in range(1, EVENTS_PER_STREAM + 1):
        event_type = EVENT_CYCLE[(seq - 1) % len(EVENT_CYCLE)]
        event = {
            "seq": seq,
            "event_id": f"generated-{seed}-event-{seq}",
            "type": event_type,
        }

        if event_type == "LIMIT":
            order_id = f"generated-{seed}-order-{seq}"
            event.update(
                {
                    "order_id": order_id,
                    "side": rng.choice(("BUY", "SELL")),
                    "price_ticks": rng.choice(PRICE_TICKS),
                    "qty_units": rng.choice(QUANTITIES),
                }
            )
            submitted_order_ids.append(order_id)
        elif event_type == "MARKET_SELL":
            order_id = f"generated-{seed}-order-{seq}"
            event.update(
                {
                    "order_id": order_id,
                    "qty_units": rng.choice(QUANTITIES),
                }
            )
            submitted_order_ids.append(order_id)
        elif submitted_order_ids and rng.randrange(2) == 0:
            event["target_order_id"] = rng.choice(submitted_order_ids)
        else:
            event["target_order_id"] = f"unknown-{seed}-{seq}"

        events.append(event)

    return events


def main():
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    fixture_dir.mkdir(exist_ok=True)
    for seed in SEEDS:
        path = fixture_dir / f"generated_seed_{seed}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            for event in generate_event_stream(seed):
                stream.write(json.dumps(event, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
