"""OWN Q7 bid books and memory-only drifting-price churn; generated outside timing."""
import argparse
import gzip
import hashlib
import json
import random
from pathlib import Path

from datagen.adversarial import TOP_BID, UNIT, _Stream


def rows(kind, size, seed, levels=1000):
    rng, stream = random.Random(seed), _Stream()
    if kind == "liquidation":
        for _ in range(size):
            yield stream.limit_buy(TOP_BID - rng.randrange(levels), rng.randint(1, 100) * UNIT)
    else:
        # One pinned best bid, then distinct worse prices added/cancelled. B <= 2
        # while B3 retains cancelled worse heap keys until they reach the root.
        yield stream.limit_buy(TOP_BID, UNIT)
        while stream.seq < size:
            event = stream.limit_buy(TOP_BID - 1 - stream.seq // 2, UNIT)
            yield event
            if stream.seq < size:
                yield stream.cancel(event["order_id"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kind", choices=("liquidation", "drift"), required=True)
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--levels", type=int, default=1000)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.size < 1 or not 1 <= a.levels < TOP_BID:
        ap.error("size/levels must be positive and prices must remain positive")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with a.out.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
        for event in rows(a.kind, a.size, a.seed, a.levels):
            gz.write((json.dumps(event, separators=(",", ":")) + "\n").encode())
            total += event.get("qty_units", 0) if a.kind == "liquidation" else 0
    meta = {"own": True, "synthetic": True, "kind": a.kind, "events": a.size,
            "seed": a.seed, "levels": a.levels, "bid_qty_units": total,
            "sha256": hashlib.sha256(a.out.read_bytes()).hexdigest()}
    a.out.with_suffix(a.out.suffix + ".metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
