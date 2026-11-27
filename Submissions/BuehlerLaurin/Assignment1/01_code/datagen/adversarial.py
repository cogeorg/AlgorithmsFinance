"""OWN adversarial benchmark generator (Phase 4; not supplied by the course).

Writes synthetic event streams that target the weak points of the transparent baseline
(Version A: one unsorted list per side, best order found by scanning) and the costs of
the Version B candidates (SPEC.md, "Own adversarial scenarios"). Same JSON Lines + gzip
format, field names, id/price conventions and units as the supplied generate_orders.py;
outputs are labelled own in their metadata. Generated OUTSIDE timing into
06_data/generated/own/ (git-ignored); commands and sha256 go into the README.

    python run.py datagen.adversarial --scenario deep_book --orders 10000 --sells 1000 --seed 42 --out 06_data/generated/own/deep_book_10000_s42.jsonl.gz
    python run.py datagen.adversarial --scenario mid_queue_cancels --orders 10000 --levels 4 --cancels 10000 --seed 42 --out ...
    python run.py datagen.adversarial --scenario repeated_full_sweeps --orders 1000 --levels 100 --rounds 50 --seed 42 --out ...

The streams contain BUY limits, market sells and cancels only (no asks), so every expected
quantity used below (e.g. the size of a full sweep) follows from the generator's own
submissions without simulating any matching.

Scenarios (only these three; further scenarios need Laurin's OK):
  deep_book             --orders N bids, each at its OWN price (P = N levels), submitted in
                        random price order; then --sells K market sells of 1 unit each.
  mid_queue_cancels     --orders N bids over --levels Q prices (long queues), then --cancels K
                        rounds of: cancel a random live order from the MIDDLE THIRD of its
                        queue, then submit a replacement at the same price (B stays N).
  repeated_full_sweeps  --rounds R rounds of: submit --orders K bids over --levels P prices,
                        then ONE market sell of exactly the total bid quantity (full sweep).
"""
import argparse
import gzip
import hashlib
import json
import platform
import random
import sys
from pathlib import Path

SCENARIOS = ("deep_book", "mid_queue_cancels", "repeated_full_sweeps")
TOP_BID = 6_000_000           # 60,000.00 USD, as in the supplied generator
UNIT = 1_000_000              # 0.01 BTC, as in the supplied generator's quantities


class _Stream:
    """Assigns seq / event_id / order_id like the supplied generator (e%09d)."""

    def __init__(self):
        self.seq = 0

    def _base(self):
        self.seq += 1
        return {"seq": self.seq, "event_id": f"e{self.seq:09d}"}

    def limit_buy(self, price, qty):
        row = self._base()
        row.update(type="LIMIT", order_id=row["event_id"], side="BUY", price_ticks=price, qty_units=qty)
        return row

    def market_sell(self, qty):
        row = self._base()
        row.update(type="MARKET_SELL", order_id=row["event_id"], qty_units=qty)
        return row

    def cancel(self, target):
        row = self._base()
        row.update(type="CANCEL", target_order_id=target)
        return row


def deep_book(rng, orders, sells):
    """Weakness: Version A scans all B orders per fill (O(B) each); B1's sorted price list
    pays an O(P) insertion for each new level that lands in the middle."""
    s = _Stream()
    depths = list(range(orders))
    rng.shuffle(depths)                                  # random price order -> mid-list inserts
    for d in depths:
        yield s.limit_buy(TOP_BID - d, rng.randint(1, 100) * UNIT)
    for _ in range(sells):
        yield s.market_sell(1)                           # touches only the best level


def mid_queue_cancels(rng, orders, levels, cancels):
    """Weakness: Version A's cancel = O(B) scan + O(B) list deletion; B1's lazy cancel leaves
    stale deque entries that later sells must skip (compaction cost); B3 keeps stale levels."""
    s = _Stream()
    queues = {TOP_BID - d: [] for d in range(levels)}    # generator's own live ids per price, FIFO
    for _ in range(orders):
        price = TOP_BID - rng.randrange(levels)
        row = s.limit_buy(price, rng.randint(1, 100) * UNIT)
        queues[price].append(row["order_id"])
        yield row
    for _ in range(cancels):
        price = rng.choice([p for p, q in queues.items() if q])
        q = queues[price]
        lo, hi = len(q) // 3, max(len(q) // 3 + 1, 2 * len(q) // 3)
        target = q.pop(rng.randrange(lo, min(hi, len(q))))
        yield s.cancel(target)
        row = s.limit_buy(price, rng.randint(1, 100) * UNIT)
        q.append(row["order_id"])
        yield row


def repeated_full_sweeps(rng, orders, levels, rounds):
    """Weakness: Version A rescans the list for every fill (O(K*B) per sweep); Version B
    empties and recreates every level each round (level create/delete churn, heap or
    sorted-list maintenance, stale-entry cleanup)."""
    s = _Stream()
    for _ in range(rounds):
        total = 0
        for _ in range(orders):
            qty = rng.randint(1, 100) * UNIT
            total += qty
            yield s.limit_buy(TOP_BID - rng.randrange(levels), qty)
        yield s.market_sell(total)                       # exactly the whole bid side


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", choices=SCENARIOS, required=True)
    ap.add_argument("--orders", type=int, default=10_000)
    ap.add_argument("--levels", type=int, default=4)
    ap.add_argument("--sells", type=int, default=1_000)
    ap.add_argument("--cancels", type=int, default=10_000)
    ap.add_argument("--rounds", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.orders < 1 or not 1 <= a.levels < TOP_BID or min(a.sells, a.cancels, a.rounds) < 0:
        ap.error("orders must be positive, levels between 1 and 5999999, counts nonnegative")
    if a.scenario == "deep_book" and a.orders >= TOP_BID:
        ap.error("deep_book needs orders < 6,000,000 (one positive price per order)")
    rng = random.Random(a.seed)
    if a.scenario == "deep_book":
        rows, params = deep_book(rng, a.orders, a.sells), dict(orders=a.orders, sells=a.sells)
    elif a.scenario == "mid_queue_cancels":
        rows, params = mid_queue_cancels(rng, a.orders, a.levels, a.cancels), dict(orders=a.orders, levels=a.levels, cancels=a.cancels)
    else:
        rows, params = repeated_full_sweeps(rng, a.orders, a.levels, a.rounds), dict(orders=a.orders, levels=a.levels, rounds=a.rounds)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    events = 0
    with a.out.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, separators=(",", ":")) + "\n").encode())
            events += 1
    meta = dict(own=True, synthetic=True, calibrated_to_exchange_data=False,
                generator="01_code/datagen/adversarial.py", scenario=a.scenario, seed=a.seed, events=events,
                **params, python=platform.python_version(), price_tick_usd="0.01", quantity_unit_btc="0.00000001",
                compressed_bytes=a.out.stat().st_size, sha256=hashlib.sha256(a.out.read_bytes()).hexdigest())
    a.out.with_suffix(a.out.suffix + ".metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
