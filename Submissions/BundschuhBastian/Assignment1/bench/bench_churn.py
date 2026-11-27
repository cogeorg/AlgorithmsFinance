"""Phase 6c (3): cancel churn versus M, time and memory ("no growth").

For M in {1,000; 10,000; 100,000; 1,000,000} (seed 42), Version A and B:
  time    median replay seconds of the timing run 2 (results/time_raw.csv, same stream, same
          conditions, canaries), and seconds per event;
  memory  a fresh `tracemalloc` run (bench.bench_memory.memory_worker): bytes held after the
          replay, peak bytes, bytes at every 10% of the events, orders still active at the end.
"No growth" means: bytes held after the replay and at the checkpoints stay flat while M grows
by 1,000 times (the book never holds more than a handful of orders in this scenario).
A block per M with a canary before and after. Writes results/cancel_churn_scaling.csv.

    .venv/bin/python -m bench.bench_churn
"""
from __future__ import annotations

import argparse
import json

from bench import common
from bench.bench_memory import memory_worker
from bench.blocks import canary_around, stamp
from bench.common import RESULTS, append_csv, read_csv
from bench.harness import run_limited

OUT = RESULTS / "cancel_churn_scaling.csv"
SIZES = (1000, 10000, 100000, 1000000)
FIELDS = ["start_utc", "power_source", "battery_percent", "low_power_mode", "version", "events",
          "status", "reason", "time_median_seconds", "time_per_event_ns", "time_source",
          "final_bytes", "peak_bytes", "max_checkpoint_bytes", "checkpoints_bytes",
          "active_orders_end"]


def time_median(version: str, events: int) -> str:
    row = common.run_result(read_csv(RESULTS / "time_raw.csv"), version, "cancel_churn", 42,
                            events, 1000)
    return row["median_seconds"] if row and row["status"] == "ok" else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    args = parser.parse_args(argv)
    done = {(r["version"], r["events"]) for r in read_csv(OUT)}
    for events in SIZES:
        todo = [v for v in ("A", "B") if (v, str(events)) not in done]
        if not todo:
            continue
        with canary_around(f"cancel_churn_{events}"):
            for version in todo:
                st0 = stamp()
                res = run_limited(memory_worker, (version, "cancel_churn", events),
                                  args.limit_seconds)
                msgs = [m for m in res["messages"] if m[0] == "unit_done"]
                row = {**st0, "version": version, "events": events}
                med = time_median(version, events)
                if med:
                    row.update(time_median_seconds=med, time_per_event_ns=float(med) / events * 1e9,
                               time_source="results/time_raw.csv (timing run 2)")
                if res["outcome"] == "end" and msgs:
                    p = msgs[0][2]
                    row.update(status="ok", final_bytes=p["final_bytes"], peak_bytes=p["peak_bytes"],
                               max_checkpoint_bytes=max(p["checkpoints_bytes"]),
                               checkpoints_bytes=json.dumps(p["checkpoints_bytes"]),
                               active_orders_end=p["active_orders_end"])
                else:
                    row.update(status=res["outcome"], reason=res["error"] or "limit reached")
                append_csv(OUT, FIELDS, row)
                print(version, events, row["status"], row.get("final_bytes", ""), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
