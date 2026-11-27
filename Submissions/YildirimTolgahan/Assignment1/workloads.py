"""Additional synthetic workloads and dataset files, all generated outside timing.

The five supplied families come unchanged from generate_orders.py. Added here:
  mass_cancel   build a two-sided passive book, then cancel all but about 1% of it
  bid book      a fresh one-sided book for the fixed-book sale experiments
Like the supplied data these are stylized teaching inputs, not exchange records.
"""
import gzip
import hashlib
import json
from pathlib import Path
import platform
import random

import generate_orders

HERE = Path(__file__).resolve().parent
SUPPLIED = generate_orders.SCENARIOS
SCENARIOS = SUPPLIED + ("mass_cancel",)
REFERENCE_PRICE = 6_000_000              # 60,000 dollars in cents, as in generate_orders.py
QTY_STEP = 1_000_000                     # 0.01 BTC


def mass_cancel_events(count, seed, levels):
    """First half: passive limits on both sides. Second half: cancellations in random order.

    max(2, count // 100) orders are spared, so about 1% of the events stay active.
    The same number of trailing cancellations re-target orders that are already
    gone and must return not_found.
    """
    if count < 8:
        raise ValueError("mass_cancel needs at least 8 events")
    rng = random.Random(seed)
    adds = count // 2
    spared = max(2, count // 100)
    identifiers = []
    for seq in range(1, adds + 1):
        event_id = f"e{seq:09d}"
        side = rng.choice(("BUY", "SELL"))
        depth = rng.randrange(levels)
        yield {"seq": seq, "event_id": event_id, "type": "LIMIT", "order_id": event_id, "side": side,
               "price_ticks": REFERENCE_PRICE - depth if side == "BUY" else REFERENCE_PRICE + 100 + depth,
               "qty_units": rng.randint(1, 100) * QTY_STEP}
        identifiers.append(event_id)
    rng.shuffle(identifiers)
    targets = identifiers[:adds - spared]
    repeats = [rng.choice(targets) for _ in range(count - adds - len(targets))]
    for seq, target in enumerate(targets + repeats, adds + 1):
        yield {"seq": seq, "event_id": f"e{seq:09d}", "type": "CANCEL", "target_order_id": target}


def scenario_events(scenario, count, seed, levels):
    if scenario == "mass_cancel":
        return mass_cancel_events(count, seed, levels)
    return generate_orders.events(scenario, count, seed, levels)


def build_boundary(scenario, count):
    """Event index after which a stream stops building its book, or None if it never does."""
    if scenario == "sweep":
        return max(1, count * 4 // 5)
    if scenario == "mass_cancel":
        return count // 2
    return None


def bid_book_events(orders, levels, seed):
    """`orders` passive buy limits spread uniformly over `levels` prices at and below 60,000 dollars."""
    rng = random.Random(seed)
    for seq in range(1, orders + 1):
        event_id = f"e{seq:09d}"
        yield {"seq": seq, "event_id": event_id, "type": "LIMIT", "order_id": event_id, "side": "BUY",
               "price_ticks": REFERENCE_PRICE - rng.randrange(levels),
               "qty_units": rng.randint(1, 100) * QTY_STEP}


def sale_quantity(total_bid_qty, percent):
    """Integer share of the available bid quantity, rounded up to at least one unit."""
    return max(1, -(-total_bid_qty * percent // 100))


def plan_market_sell(bid_events, qty, taker_id):
    """Read-only fill plan by sorting, as in the lecture: the independent expectation for a sale."""
    fills = []
    for bid in sorted(bid_events, key=lambda e: (-e["price_ticks"], e["seq"])):
        if not qty:
            break
        traded = min(qty, bid["qty_units"])
        fills.append({"maker_id": bid["order_id"], "taker_id": taker_id,
                      "price_ticks": bid["price_ticks"], "qty_units": traded})
        qty -= traded
    return fills, qty


# ------------------------------------------------------------ dataset files
def content_sha256(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dataset_path(scenario, count, seed, levels=1000):
    supplied = HERE / "data" / f"{scenario}_{count}.jsonl.gz"
    if scenario in SUPPLIED and count == 10_000 and seed == 42 and levels == 1000 and supplied.exists():
        return supplied                                      # the file shipped with the assignment
    return HERE / "data" / "generated" / f"{scenario}_{count}_seed{seed}_levels{levels}.jsonl.gz"


def ensure_dataset(scenario, count, seed, levels=1000):
    """Create the event file if needed and return its description with checksums."""
    path = dataset_path(scenario, count, seed, levels)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        generate_orders.write_stream(path, scenario_events(scenario, count, seed, levels))
    relative = path.relative_to(HERE).as_posix()
    if scenario in SUPPLIED:
        command = (f"python generate_orders.py --scenario {scenario} --events {count} --levels {levels} "
                   f"--seed {seed} --out {relative}")
    else:
        command = (f"python workloads.py --scenario {scenario} --events {count} --levels {levels} "
                   f"--seed {seed} --out {relative}")
    return {"scenario": scenario, "events": count, "seed": seed, "levels": levels, "file": relative,
            "supplied_with_assignment": path.parent.name == "data",
            "compressed_bytes": path.stat().st_size,
            "sha256_compressed": hashlib.sha256(path.read_bytes()).hexdigest(),
            "sha256_uncompressed": content_sha256(path),
            "generator_python": platform.python_version(), "command": command}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Write one additional workload as gzip JSON Lines.")
    parser.add_argument("--scenario", choices=("mass_cancel",), default="mass_cancel")
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--levels", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.events < 8 or not 1 <= args.levels < REFERENCE_PRICE:
        parser.error("events must be at least 8; levels must be between 1 and 5999999")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    generate_orders.write_stream(args.out, scenario_events(args.scenario, args.events, args.seed, args.levels))
    print(json.dumps({"synthetic": True, "calibrated_to_exchange_data": False, "scenario": args.scenario,
                      "events": args.events, "seed": args.seed, "levels": args.levels,
                      "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
                      "sha256_uncompressed": content_sha256(args.out)}))


if __name__ == "__main__":
    main()
