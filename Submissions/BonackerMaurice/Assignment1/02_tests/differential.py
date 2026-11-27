"""Differential test: Version A vs B-sorted vs B-heap after EVERY event.

Usage (from Assignment1/):
    python 02_tests/differential.py [--streams 300] [--first-seed 0]

Generates seeded random event streams (separate from the engines), feeds
the same events to every version, and after every event requires:
  - identical result dicts (status, fills in order, quantities, reasons),
  - identical inspect_book() and last_seq,
  - each book's assert_invariants() passes,
  - the per-event conservation / price-time check (invariants.check_event)
    passes on the reference result.
Agreement between versions is evidence, not proof: all versions could share
a misunderstanding of the spec. The hand-calculated tests guard against that.

Writes 05_results/differential_tests.csv (one row per stream). Exit code 1
if any stream mismatches. test_differential.py runs the same streams.
"""

import argparse
import csv
import importlib
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "03_code") not in sys.path:
    sys.path.insert(0, str(ROOT / "03_code"))

from invariants import check_event  # noqa: E402

VERSIONS = ["lob_a", "lob_b_sorted", "lob_b_heap"]   # first = reference
OUT = ROOT / "05_results" / "differential_tests.csv"
MID = 6_000_000
FIELDS = ["seed", "events", "price_levels_used", "accepted", "rejected",
          "limits", "crossing_limits", "market_sells", "cancels", "cancelled",
          "not_found", "fills", "peak_active_orders", "versions",
          "mismatching_events", "invariant_failures", "result", "first_problem"]


# ----- stream generation (no engine involved) ------------------------------

def _invalid_event(rng, seq, i, submitted):
    """One deliberately invalid (or suspicious) event."""
    base = {"seq": seq, "event_id": f"ev{i}", "type": "LIMIT",
            "order_id": f"o{i}", "side": rng.choice(["BUY", "SELL"]),
            "price_ticks": MID, "qty_units": 1_000_000}
    kind = rng.randrange(14)
    if kind == 0:
        base["qty_units"] = 0
    elif kind == 1:
        base["qty_units"] = -rng.randint(1, 10**6)
    elif kind == 2:
        base["qty_units"] = 1.5e6                       # float
    elif kind == 3:
        base["qty_units"] = True                        # bool
    elif kind == 4:
        base["price_ticks"] = rng.choice([0, -MID, 6_000_000.0, "6000000", None])
    elif kind == 5:
        base["side"] = rng.choice(["buy", "", None, "BID"])
    elif kind == 6:
        base["type"] = rng.choice(["MARKET_BUY", "limit", None])
    elif kind == 7:
        base["seq"] = rng.randint(0, max(0, seq - 1))   # maybe non-increasing
    elif kind == 8:
        del base["event_id"]
    elif kind == 9:
        base["order_id"] = rng.choice([5, None])
    elif kind == 10 and submitted:
        base["order_id"] = rng.choice(submitted)        # duplicate if still live
    elif kind == 11:
        base = {"seq": seq, "event_id": f"ev{i}", "type": "MARKET_SELL",
                "order_id": rng.choice(submitted) if submitted else f"o{i}",
                "qty_units": rng.choice([0, 5_000_000])}
    elif kind == 12:
        base = {"seq": seq, "event_id": f"ev{i}", "type": "CANCEL",
                "target_order_id": rng.choice([7, None])}
    else:
        base = rng.choice([[], "LIMIT", None])          # not an object
    return base


def random_stream(seed):
    """A seeded stream of 50-300 events on a narrow price band (crossing)."""
    rng = random.Random(seed)
    n_events = rng.randint(50, 300)
    n_prices = rng.choice([1, 2, 3, 5, 10, 30])
    prices = [MID + d for d in range(n_prices)]
    p_invalid = rng.choice([0.0, 0.05, 0.15])
    p_cancel = rng.choice([0.1, 0.25, 0.4])
    p_market = rng.choice([0.05, 0.15, 0.3])
    unit = rng.choice([1, 1_000_000])
    submitted = []
    events = []
    seq = 0
    for i in range(n_events):
        seq += rng.choice([1, 1, 1, 2, 5])            # gaps are allowed
        u = rng.random()
        if u < p_invalid:
            events.append(_invalid_event(rng, seq, i, submitted))
        elif u < p_invalid + p_cancel:
            r = rng.random()
            if submitted and r < 0.4:
                target = rng.choice(submitted)        # live or already gone
            elif submitted and r < 0.7:
                target = submitted[-1]                # most recent
            else:
                target = f"unknown{rng.randint(0, 99)}"
            events.append({"seq": seq, "event_id": f"ev{i}", "type": "CANCEL",
                           "target_order_id": target})
        elif u < p_invalid + p_cancel + p_market:
            events.append({"seq": seq, "event_id": f"ev{i}", "type": "MARKET_SELL",
                           "order_id": f"o{i}",
                           "qty_units": rng.randint(1, 40) * unit})
        else:
            events.append({"seq": seq, "event_id": f"ev{i}", "type": "LIMIT",
                           "order_id": f"o{i}", "side": rng.choice(["BUY", "SELL"]),
                           "price_ticks": rng.choice(prices),
                           "qty_units": rng.randint(1, 10) * unit})
            submitted.append(f"o{i}")
    return events, n_prices


# ----- comparison ------------------------------------------------------------

def compare_stream(seed, versions=VERSIONS):
    events, n_prices = random_stream(seed)
    modules = [importlib.import_module(v) for v in versions]
    books = [m.OrderBook() for m in modules]
    row = {k: 0 for k in FIELDS}
    row.update(seed=seed, events=len(events), price_levels_used=n_prices,
               versions="|".join(versions), first_problem="")

    def problem(text):
        if not row["first_problem"]:
            row["first_problem"] = text

    before = books[0].inspect_book()
    for k, event in enumerate(events):
        results = [b.process_event(event) for b in books]
        snaps = [b.inspect_book() for b in books]
        ref = results[0]
        if any(r != ref for r in results[1:]) or any(s != snaps[0] for s in snaps[1:]) \
                or len({b.last_seq for b in books}) != 1:
            row["mismatching_events"] += 1
            problem(f"event {k}: versions disagree")
        for v, b in zip(versions, books):
            try:
                b.assert_invariants()
            except AssertionError as exc:
                row["invariant_failures"] += 1
                problem(f"event {k}: {v} invariant: {exc}")
        try:
            check_event(before, event, ref, snaps[0])
        except AssertionError as exc:
            row["invariant_failures"] += 1
            problem(f"event {k}: conservation/priority: {exc}")
        before = snaps[0]

        status = ref["status"]
        row["rejected"] += status == "rejected"
        row["accepted"] += status != "rejected"
        if status != "rejected":
            kind = event["type"]
            row["limits"] += kind == "LIMIT"
            row["crossing_limits"] += kind == "LIMIT" and bool(ref["fills"])
            row["market_sells"] += kind == "MARKET_SELL"
            row["cancels"] += kind == "CANCEL"
        row["cancelled"] += status == "cancelled"
        row["not_found"] += status == "not_found"
        row["fills"] += len(ref.get("fills", []))
        row["peak_active_orders"] = max(row["peak_active_orders"], len(snaps[0]))
    ok = row["mismatching_events"] == 0 and row["invariant_failures"] == 0
    row["result"] = "pass" if ok else "fail"
    return row


def run_streams(n_streams=300, first_seed=0):
    return [compare_stream(seed) for seed in range(first_seed, first_seed + n_streams)]


def main(argv=None):
    parser = argparse.ArgumentParser(description="A vs B differential test")
    parser.add_argument("--streams", type=int, default=300)
    parser.add_argument("--first-seed", type=int, default=0)
    args = parser.parse_args(argv)
    rows = run_streams(args.streams, args.first_seed)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    total = lambda k: sum(r[k] for r in rows)  # noqa: E731
    failed = [r["seed"] for r in rows if r["result"] != "pass"]
    print(f"streams {len(rows)}, events {total('events')}, accepted {total('accepted')}, "
          f"rejected {total('rejected')}, fills {total('fills')}, "
          f"crossing limits {total('crossing_limits')}, market sells {total('market_sells')}, "
          f"cancelled {total('cancelled')}, not_found {total('not_found')}")
    print(f"mismatching events {total('mismatching_events')}, "
          f"invariant failures {total('invariant_failures')}, failed streams {failed}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
