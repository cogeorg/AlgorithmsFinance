"""Workload facts per stream, independent of the timing runs: peaks of active orders and price
levels, fill count, outcome counts. Computed with Version B (fast); the replay is NOT timed.

    .venv/bin/python -m bench.peaks            # writes results/workload_peaks.csv
"""
from __future__ import annotations

import collections

from bench.common import RESULTS, all_streams, stream_path
from lob.common import load_events
from lob.version_b import OrderBookB
import csv

FIELDS = ["scenario", "seed", "events", "levels", "peak_active_orders", "peak_price_levels",
          "final_active_orders", "final_price_levels", "total_fills", "total_filled_qty_units",
          "accepted", "rejected", "resting", "filled", "partial", "unfilled", "cancelled",
          "not_found"]


def peaks_for(events: list[dict]) -> dict:
    book = OrderBookB()
    process, index = book.process, book._index
    bids, asks = book._bids.levels, book._asks.levels
    peak_orders = peak_levels = fills = qty = 0
    status = collections.Counter()
    for e in events:
        r = process(e)
        status[r["status"]] += 1
        for f in r["fills"]:
            fills += 1
            qty += f["qty_units"]
        n = len(index)
        if n > peak_orders:
            peak_orders = n
        lv = len(bids) + len(asks)
        if lv > peak_levels:
            peak_levels = lv
    rejected = status["rejected"]
    return {"peak_active_orders": peak_orders, "peak_price_levels": peak_levels,
            "final_active_orders": len(index), "final_price_levels": len(bids) + len(asks),
            "total_fills": fills, "total_filled_qty_units": qty, "accepted": len(events) - rejected,
            "rejected": rejected, **{k: status[k] for k in ("resting", "filled", "partial",
                                                           "unfilled", "cancelled", "not_found")}}


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "workload_peaks.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for spec in all_streams():
            row = {**spec, **peaks_for(load_events(stream_path(**spec)))}
            writer.writerow(row)
            print(spec["scenario"], spec["events"], spec["seed"], spec["levels"],
                  row["peak_active_orders"], row["peak_price_levels"], row["total_fills"],
                  flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
