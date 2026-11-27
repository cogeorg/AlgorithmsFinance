"""OWN cases added after Phase 4 from aif-attack; hash_full is excluded."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

TOP = 6_000_000
REGISTRATION = "added after Phase 4 from aif-attack"

SCENARIOS = ("far_end_flicker", "dead_slot_rebuild", "two_side_thrash",
             "spike_purge_at_threshold", "rotating_bursts", "pinned_dead")


class Stream:
    def __init__(self):
        self.seq = 0

    def add(self, oid, price, qty=1, side="BUY"):
        self.seq += 1
        return {"seq": self.seq, "event_id": f"e{self.seq}", "type": "LIMIT", "order_id": oid,
                "side": side, "price_ticks": price, "qty_units": qty}

    def cancel(self, oid):
        self.seq += 1
        return {"seq": self.seq, "event_id": f"e{self.seq}", "type": "CANCEL", "target_order_id": oid}

    def sell(self):
        self.seq += 1
        return {"seq": self.seq, "event_id": f"e{self.seq}", "type": "MARKET_SELL",
                "order_id": f"m{self.seq}", "qty_units": 1}


def build(scenario, n, *, burst=1000, rounds=None):
    """Return prefill and measured events; memory cases have empty prefill."""
    if scenario not in SCENARIOS or n < 1 or burst < 1:
        raise ValueError("known scenario and positive n/burst required")
    s, pre, out = Stream(), [], []
    if scenario == "far_end_flicker":
        pre = [s.add(f"o{i}", TOP+i) for i in range(n)]
        for _ in range(n):
            out += [s.add("x", TOP-1), s.cancel("x")]
    elif scenario == "dead_slot_rebuild":
        pre = [s.add("keep", TOP+2*n)] + [s.add(f"o{i}", TOP+i) for i in range(n-1)]
        pre += [s.cancel(f"o{i}") for i in range(n-1)]
        for i in range(n//2):
            out += [s.add("x", TOP-1-i), s.cancel("x")]
    elif scenario == "two_side_thrash":
        pre = [s.add(f"a{i}", TOP+10+i, 1, "SELL") for i in range(n)] + [s.add("keep", TOP)]
        for i in range(n+1):
            pre += [s.add("x", TOP-1-i), s.cancel("x")]
        for i in range(n):
            out += [s.add("y", TOP+10+n+i, 1, "SELL"), s.cancel("y")]
    elif scenario == "spike_purge_at_threshold":
        pre = [s.add(f"k{i}", TOP-n+i, 2) for i in range(n)]
        pre += [s.add(f"o{i}", TOP+i) for i in range(n)]
        pre += [s.cancel(f"o{i}") for i in range(n)]
        out = [s.sell()]
    elif scenario == "rotating_bursts":
        out = [s.add(f"k{j}", TOP+j) for j in range(n)]
        for j in range(2*n if rounds is None else rounds):
            out += [s.add(f"x{i}", TOP+j % n) for i in range(burst)]
            out += [s.cancel(f"x{i}") for i in range(burst)]
    else:  # pinned_dead: 32 dead records stay behind one live record per level.
        out = [s.add(f"k{j}", TOP+j) for j in range(n)]
        for d in range(32):
            for j in range(n):
                oid = f"pinned-dead-record-{d}-{j}"
                out += [s.add(oid, TOP+j), s.cancel(oid)]
    return pre, out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--burst", type=int, default=1000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    pre, work = build(args.scenario, args.n, burst=args.burst)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
        for event in pre+work:
            stream.write((json.dumps(event, separators=(",", ":"))+"\n").encode())
    metadata = {"own": True, "registration": REGISTRATION, "scenario": args.scenario,
                "n": args.n, "burst": args.burst, "prefill_events": len(pre),
                "events": len(pre)+len(work), "query_events": len(work),
                "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest()}
    args.out.with_suffix(args.out.suffix+".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
