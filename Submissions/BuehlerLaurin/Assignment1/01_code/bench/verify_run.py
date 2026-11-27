"""Verify a completed smoke artifact; performs no engine replay."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from bench.run_all import rows_from


def verify(directory):
    cells = rows_from(directory/"cells.csv")
    assert len(cells) == 216 and {r["status"] for r in cells} == {"ok"}
    assert {r["size"] for r in cells} == {"1000"} and {r["seed"] for r in cells} == {"42"}
    assert {r["version"] for r in cells} == {"A", "B1", "B2", "B3"}
    assert len({r["case_id"] for r in cells}) == 15
    assert {r["experiment"] for r in cells} == {"official", "queue", "liquidation", "adversarial", "churn"}
    assert not rows_from(directory/"stops.csv")
    timing = rows_from(directory/"timing.csv")
    repeats = defaultdict(list)
    for row in timing:
        assert row["status"] == "ok" and float(row["seconds"]) > 0
        repeats[(row["case_id"], row["version"], row["phase"])].append(row)
    assert len(repeats) == 208
    for (case, version, phase), rows in repeats.items():
        if phase == "parse":
            assert len(rows) == 1
        else:
            assert sorted(int(r["repeat"]) for r in rows) == [-1, 0, 1, 2, 3, 4]
    summaries = rows_from(directory/"summary.csv")
    assert len(summaries) == 208 and {r["status"] for r in summaries} == {"ok"}
    for row in summaries:
        assert row["completed_repeats"] == row["repeats_requested"]
        assert math.isfinite(float(row["median_s"])) and float(row["median_s"]) > 0
    latency = rows_from(directory/"latency.csv")
    assert {r["segment"] for r in latency} == {"all", "early", "late"}
    for row in latency:
        assert row["convention"] == "nearest-rank" and int(row["n"]) > 0
        assert 0 < int(row["p50_ns"]) <= int(row["p95_ns"]) <= int(row["p99_ns"]) <= int(row["max_ns"])
    checks = rows_from(directory/"checks.csv")
    assert len(checks) == 216
    counts = rows_from(directory/"counts.csv")
    semantic = defaultdict(dict)
    names = {"accepted_events", "fills", "unfilled_qty_units", "active_order_peak", "price_level_peak"}
    for row in counts:
        if row["phase"] == "replay" and row["counter"] in names:
            semantic[(row["case_id"], row["counter"])][row["version"]] = row["value"]
    assert semantic and all(len(values) == 4 and len(set(values.values())) == 1 for values in semantic.values())
    memory = rows_from(directory/"memory.csv")
    assert memory and all(int(r["peak_bytes"]) > 0 for r in memory)
    drift = [r for r in memory if r["workload"] == "drift" and r["measure"] == "curve"]
    observations = {}
    for version in ("A", "B1", "B2", "B3"):
        rows = [r for r in drift if r["version"] == version]
        assert len(rows) >= 50 and max(int(r["live_orders"]) for r in rows) <= 2
        early = next(r for r in rows if int(r["processed"]) >= 200)
        last = rows[-1]
        observations[version] = {"at_200_bytes": int(early["current_bytes"]),
                                 "at_1000_bytes": int(last["current_bytes"]),
                                 "live_orders_final": int(last["live_orders"]),
                                 "heap_entries_final": int(last["heap_entries"])}
    report = {"cells": len(cells), "cell_status": dict(Counter(r["status"] for r in cells)),
              "cases": 15, "size": 1000, "seed": 42, "raw_timing_rows": len(timing),
              "phase_summaries": len(summaries), "latency_rows": len(latency),
              "memory_rows": len(memory), "count_rows": len(counts),
              "sample_checks": len(checks), "drift_memory_smoke_only": observations}
    (directory/"verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("RESULT: PASS (all smoke cells/repeats/metrics/counter parity verified; no engine replay above 1000)")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    verify(parser.parse_args().run_dir)
