"""Correctness outcomes for the dashboard: Version A against Version B after EVERY event.

For each stream (all generated streams up to 10,000 events, plus buildup with 5,000 events at
4 / 16 / 64 / 256 / 1000 / 4000 prices for queue concentration): replay both versions in lock
step; compare every result dict (status, ordered fills, quantities) and the best bid/ask, and the
full canonical book every 200 events and at the end. Writes results/correctness.csv.

    .venv/bin/python -m bench.correctness
"""
from __future__ import annotations

import hashlib
import json

import generate_orders
from bench import common
from bench.common import RESULTS, all_streams, stream_path
from lob.common import load_events
from lob.version_a import OrderBookA
from lob.version_b import OrderBookB
import csv

FIELDS = ["stream", "events", "results_compared", "all_results_equal", "first_difference_event",
          "best_prices_equal", "final_book_equal", "orders_at_end", "results_sha256"]


def compare(name: str, events: list[dict]) -> dict:
    a, b = OrderBookA(), OrderBookB()
    digest = hashlib.sha256()
    first_diff, best_equal, book_equal = "", True, True
    for n, event in enumerate(events, start=1):
        ra, rb = a.process(event), b.process(event)
        digest.update(json.dumps(rb, sort_keys=True).encode())
        if ra != rb and not first_diff:
            first_diff = n
        if (a.best_bid(), a.best_ask()) != (b.best_bid(), b.best_ask()):
            best_equal = False
        if n % 200 == 0 and a.snapshot() != b.snapshot():
            book_equal = False
    final_equal = a.snapshot() == b.snapshot()
    return {"stream": name, "events": len(events), "results_compared": len(events),
            "all_results_equal": first_diff == "", "first_difference_event": first_diff,
            "best_prices_equal": best_equal, "final_book_equal": final_equal and book_equal,
            "orders_at_end": len(b.snapshot()), "results_sha256": digest.hexdigest()}


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "correctness.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for spec in all_streams():
            if spec["events"] > 10000 or spec["levels"] != 1000:
                continue
            row = compare(common.stream_name(**spec), load_events(stream_path(**spec)))
            writer.writerow(row)
            print(row["stream"], row["all_results_equal"], row["final_book_equal"], flush=True)
        for levels in common.CONCENTRATION_LEVELS:
            events = list(generate_orders.events("buildup", 5000, 42, levels))
            row = compare(f"buildup_5000_s42_L{levels} (generated in memory)", events)
            writer.writerow(row)
            print(row["stream"], row["all_results_equal"], row["final_book_equal"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
