"""Phase 6c (4): flood peaks. For the flood scenarios `buildup` and `crowded`: the peak number of
active orders B and the peak number of price levels P, per stream, read from
results/workload_peaks.csv (made by bench.peaks, independent of any timing). Also B / M.
Writes results/flood_peaks.csv.

    .venv/bin/python -m bench.bench_flood
"""
from __future__ import annotations

import csv

from bench.common import RESULTS, read_csv

OUT = RESULTS / "flood_peaks.csv"
FIELDS = ["scenario", "seed", "events", "levels", "peak_active_orders_B", "peak_price_levels_P",
          "peak_B_per_event", "final_active_orders", "final_price_levels"]


def main() -> int:
    rows = []
    for r in read_csv(RESULTS / "workload_peaks.csv"):
        if r["scenario"] in ("buildup", "crowded"):
            m, b = int(r["events"]), int(r["peak_active_orders"])
            rows.append({"scenario": r["scenario"], "seed": r["seed"], "events": m,
                         "levels": r["levels"], "peak_active_orders_B": b,
                         "peak_price_levels_P": r["peak_price_levels"],
                         "peak_B_per_event": round(b / m, 4),
                         "final_active_orders": r["final_active_orders"],
                         "final_price_levels": r["final_price_levels"]})
    rows.sort(key=lambda d: (d["scenario"], int(d["levels"]), int(d["events"]), int(d["seed"])))
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows), "rows ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
