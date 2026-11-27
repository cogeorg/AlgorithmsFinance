#!/usr/bin/env python3
"""Small adversarial event streams for the A-vs-B equivalence tests (Phase 4).

Own generator (standard library only). It knows nothing about the book: it only picks
random events from small pools, so that many events collide on purpose:
  - few prices and small quantities    -> many crossings, partial fills, sweeps over levels
  - a small pool of order ids          -> ids reused after fill/cancel (valid), duplicate live
                                          ids (rejected), cancels of live / filled / unknown ids
  - ids whose text order differs from arrival order (priority must follow `seq`)
  - market sells larger than the whole book
  - gaps in `seq` (valid) and repeated / decreasing `seq` (rejected)
  - optional corrupted events (wrong types, missing fields, bool/float numbers, ...)

Usage:
    python tools/gen_small.py --seed 3 --events 40 --profile tight          # JSON Lines to stdout
    python tools/gen_small.py --seed 3 --events 40 --profile dirty --out small.jsonl

Same seed, count and profile always give the same events (random.Random only).
"""
from __future__ import annotations

import argparse
import json
import random
import sys

# profile -> (price range, max qty, id pool size, P(cancel), P(market sell), P(corrupt))
PROFILES = {
    "tight": dict(prices=(100, 104), max_qty=5, pool=25, cancel=0.20, msell=0.12, corrupt=0.0),
    "wide": dict(prices=(90, 110), max_qty=20, pool=60, cancel=0.15, msell=0.10, corrupt=0.0),
    "single_level": dict(prices=(100, 100), max_qty=4, pool=40, cancel=0.15, msell=0.10,
                         corrupt=0.0),
    "dirty": dict(prices=(100, 104), max_qty=5, pool=25, cancel=0.20, msell=0.12, corrupt=0.30),
}

_BAD_VALUES = [None, True, False, 0, -1, 2**70, 1.0, 2.5, "", "x", "buy", [], {}, (1,)]


def _id_pool(rng: random.Random, size: int) -> list[str]:
    """Ids with text order unrelated to arrival order (shuffled, mixed width)."""
    ids = [f"{rng.choice('abxyz')}{n}" for n in range(size)]
    rng.shuffle(ids)
    return ids


def _corrupt(rng: random.Random, event: dict) -> dict:
    event = dict(event)
    for _ in range(rng.choice((1, 1, 2))):
        key = rng.choice(list(event) + ["type", "seq"])
        roll = rng.random()
        if roll < 0.25:
            event.pop(key, None)
        elif roll < 0.35:
            event[key] = rng.choice(("LIMIT", "CANCEL", "MARKET_SELL", "MARKET_BUY", "BUY", "SELL"))
        else:
            event[key] = rng.choice(_BAD_VALUES)
    return event


def generate(seed: int, count: int, profile: str = "tight") -> list:
    """Return `count` raw events (dicts; a few non-dict values only in profile 'dirty')."""
    cfg = PROFILES[profile]
    rng = random.Random(seed)
    pool = _id_pool(rng, cfg["pool"])
    lo, hi = cfg["prices"]
    events: list = []
    seq = 0
    for i in range(1, count + 1):
        roll = rng.random()                      # seq: mostly +1, sometimes a gap, sometimes bad
        if roll < 0.80:
            seq += 1
        elif roll < 0.92:
            seq += rng.randint(2, 4)
        else:
            seq = max(0, seq - rng.randint(0, 2))      # repeated or lower seq -> rejected
        event = {"seq": seq, "event_id": f"e{i}"}
        kind = rng.random()
        if kind < cfg["cancel"]:
            target = rng.choice(pool) if rng.random() < 0.85 else f"ghost{rng.randint(1, 3)}"
            event.update(type="CANCEL", target_order_id=target)
        elif kind < cfg["cancel"] + cfg["msell"]:
            qty = rng.randint(1, cfg["max_qty"] * rng.choice((1, 2, 6)))   # sometimes > book
            event.update(type="MARKET_SELL", order_id=rng.choice(pool), qty_units=qty)
        else:
            event.update(type="LIMIT", order_id=rng.choice(pool),
                         side=rng.choice(("BUY", "SELL")),
                         price_ticks=rng.randint(lo, hi), qty_units=rng.randint(1, cfg["max_qty"]))
        if rng.random() < cfg["corrupt"]:
            event = _corrupt(rng, event)
        events.append(event)
    if cfg["corrupt"] > 0:                        # a few events that are not dicts at all
        for _ in range(max(1, count // 40)):
            events[rng.randrange(count)] = rng.choice((None, 7, "text", [], {"_parse_error": 1}))
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--events", type=int, default=40)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="tight")
    parser.add_argument("--out", help="output file (default: stdout)")
    args = parser.parse_args(argv)
    lines = (json.dumps(e, separators=(",", ":")) for e in generate(args.seed, args.events,
                                                                      args.profile))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.writelines(line + "\n" for line in lines)
    else:
        sys.stdout.writelines(line + "\n" for line in lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
