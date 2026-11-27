"""Check the saved results for completeness and internal consistency.

    python verify_results.py

Verifies: every planned cell is present; medians equal the medians of the raw
repeats; CSV files agree with the JSON; recorded source hashes match the files
in this folder; supplied data match the assignment's checksums; both versions
agree wherever both finished; the tuning comparison, if present, is consistent
and was taken with the current sources; the dashboard rebuilds byte-for-byte.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import tempfile

import benchmark
from dashboard import build
import workloads

HERE = Path(__file__).resolve().parent

if not __debug__:
    raise SystemExit("Verification requires assertions. Run Python without -O or -OO.")


def close(a, b):
    return a == b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0.0)


def verify(folder, check_sources=True):
    source = folder / "measurements.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    meta, settings = data["metadata"], data["metadata"]["settings"]
    assert meta["schema_version"] == benchmark.SCHEMA_VERSION and data["complete"] is True
    repeats = settings["repeats"]
    assert repeats >= 5

    if check_sources:
        for name, digest in meta["source_sha256"].items():
            assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, f"{name} changed after measuring"

    # Planned cells, without generating any data.
    streams = {(sc, n, seed) for sc in workloads.SCENARIOS for n in settings["sizes"] for seed in settings["seeds"]}
    streams |= {(sc, n, settings["seeds"][0]) for sc in workloads.SCENARIOS for n in settings["single_seed_sizes"]}
    books = {(n, settings["levels"], seed) for n in settings["sizes"] for seed in settings["seeds"]}
    books |= {(n, settings["levels"], settings["seeds"][0]) for n in settings["fixed_single_seed_sizes"]}
    books |= {(settings["concentration_orders"], lv, seed) for lv in settings["concentration_levels"]
              for seed in settings["concentration_seeds"]}
    assert {(r["scenario"], r["events"], r["seed"]) for r in data["read_parse"]} == streams
    assert len(data["read_parse"]) == len(streams)
    assert sorted((r["scenario"], r["events"], r["seed"], r["version"]) for r in data["replay"]) == \
        sorted((*s, v) for s in streams for v in "AB")
    assert sorted((r["book_orders"], r["levels"], r["seed"], r["sale_pct"], r["version"]) for r in data["fixed_book"]) == \
        sorted((*b, p, v) for b in books for p in settings["sale_percents"] for v in "AB")
    assert {(d["scenario"], d["events"], d["seed"]) for d in data["datasets"]} == streams

    # Supplied files are byte-identical to the assignment package; generated ones match if present.
    for d in data["datasets"]:
        path = HERE / d["file"]
        if d["supplied_with_assignment"]:
            recorded = json.loads(Path(str(path) + ".metadata.json").read_text(encoding="utf-8"))
            assert d["sha256_compressed"] == recorded["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.exists():
            assert workloads.content_sha256(path) == d["sha256_uncompressed"], d["file"]

    counts = {"ok": 0, "stopped": 0}
    for row in data["read_parse"]:
        assert row["status"] == "ok" and [r["repeat"] for r in row["repeats"]] == list(range(1, repeats + 1))
        assert all(r["events"] == row["events"] and r["elapsed_seconds"] > 0 for r in row["repeats"])
        assert close(row["read_parse_seconds_median"], statistics.median(r["elapsed_seconds"] for r in row["repeats"]))

    for row in data["replay"]:
        assert row["status"] in counts, row.get("error")
        counts[row["status"]] += 1
        raw = row["repeats"]
        if row["status"] == "ok":
            assert [r["repeat"] for r in raw] == list(range(1, repeats + 1))
            assert all(r["status"] == "ok" and r["events_completed"] == row["events"] for r in raw)
            assert all(len(r["checkpoint_seconds"]) == benchmark.CHECKPOINTS and
                       close(r["checkpoint_seconds"][-1], r["elapsed_seconds"]) for r in raw)
            median = statistics.median(r["elapsed_seconds"] for r in raw)
            assert close(row["replay_seconds_median"], median)
            assert close(row["throughput_events_per_second"], row["events"] / median)
            latency, outcome, memory = row["latency"], row["outcome"], row["memory"]
            assert latency["overall"]["count"] == row["events"] == sum(outcome["statuses"].values())
            assert latency["overall"]["p50_ns"] <= latency["overall"]["p95_ns"] <= latency["overall"]["p99_ns"]
            assert sum(sum(h) for h in latency["histogram_by_type"].values()) == row["events"]
            assert memory["status"] == "ok" and memory["peak_bytes"] >= memory["final_current_bytes"] >= 0
            assert memory["final_active_orders"] == outcome["final_active_orders"] <= outcome["peak_active_orders"]
            assert (row["counters"] is not None) == (row["events"] <= benchmark.COUNTER_MAX_EVENTS)
        else:
            assert raw and raw[-1]["status"] == "stopped" and raw[-1]["events_completed"] < row["events"]
            assert raw[-1]["elapsed_seconds"] > row["replay_limit_seconds"]
            assert row["latency"] is None and row["memory"] is None and "replay_seconds_median" not in row

    equal_streams = comparable_streams = 0
    b_rows = {(r["scenario"], r["events"], r["seed"]): r for r in data["replay"] if r["version"] == "B"}
    for a in (r for r in data["replay"] if r["version"] == "A" and r["status"] == "ok"):
        b = b_rows[a["scenario"], a["events"], a["seed"]]
        if b["status"] == "ok":
            comparable_streams += 1
            same = all(a["outcome"][k] == b["outcome"][k] for k in
                       ("results_sha256", "book_sha256", "statuses", "fill_count", "filled_qty_units",
                        "gross_value_tick_units", "peak_active_orders", "final_active_orders", "final_price_levels"))
            assert same, f"versions disagree on {a['scenario']} {a['events']} seed {a['seed']}"
            equal_streams += 1

    plans = equal_sales = 0
    b_books = {(r["book_orders"], r["levels"], r["seed"], r["sale_pct"]): r for r in data["fixed_book"] if r["version"] == "B"}
    for row in data["fixed_book"]:
        assert row["status"] in counts, row.get("error")
        counts[row["status"]] += 1
        assert row["requested_qty_units"] == workloads.sale_quantity(row["available_bid_qty_units"], row["sale_pct"])
        if row["status"] == "ok":
            assert [r["repeat"] for r in row["repeats"]] == list(range(1, repeats + 1))
            assert close(row["sell_seconds_median"], statistics.median(r["sell_seconds"] for r in row["repeats"]))
            assert close(row["construction_seconds_median"],
                         statistics.median(r["construction_seconds"] for r in row["repeats"]))
            o = row["outcome"]
            assert o["matches_sorted_fill_plan"] is True and o["fill_count"] == row["expected_fill_count"]
            assert o["filled_qty_units"] + o["unfilled_qty_units"] == row["requested_qty_units"]
            assert o["makers_touched"] == o["fill_count"]
            plans += 1
            b = b_books[row["book_orders"], row["levels"], row["seed"], row["sale_pct"]]
            if row["version"] == "A" and b["status"] == "ok":
                assert all(o[k] == b["outcome"][k] for k in ("fills_sha256", "book_sha256", "unfilled_qty_units"))
                equal_sales += 1
        else:
            assert row["repeats"] and row["repeats"][-1]["sell_seconds"] is None

    assert all(w["matches_expected"] and w["gross_proceeds_usd"] == "359400.00" for w in data["worked_example"])

    # CSV files are exactly the tables derived from the JSON.
    for name, table, columns in (("raw_repeats.csv", benchmark.raw_rows(data), benchmark.RAW_COLUMNS),
                                 ("summary.csv", benchmark.summary_rows(data), benchmark.SUMMARY_COLUMNS)):
        with (folder / name).open(newline="", encoding="utf-8") as stream:
            saved = list(csv.DictReader(stream))
        expected = [{c: ("" if row.get(c) is None else str(row.get(c))) for c in columns} for row in table]
        assert saved == expected, f"{name} differs from measurements.json"
    raw_count = len(benchmark.raw_rows(data))

    rebuilt = None
    if (folder / "dashboard.html").exists():
        with tempfile.NamedTemporaryFile(dir=folder, suffix=".html", delete=False) as handle:
            temporary = Path(handle.name)
        try:
            build(source, temporary)
            rebuilt = temporary.read_bytes() == (folder / "dashboard.html").read_bytes()
            assert rebuilt, "dashboard.html is not what dashboard.py builds from the saved results"
        finally:
            temporary.unlink()

    tuning_checked = None
    if (folder / "tuning.json").exists():
        tuning = json.loads((folder / "tuning.json").read_text(encoding="utf-8"))
        for row in tuning["rows"]:
            assert row["identical_results_and_book"] is True
            for engine in tuning["engines"]:
                assert len(row["repeat_seconds"][engine]) == tuning["repeats"]
                assert close(row["median_seconds"][engine], statistics.median(row["repeat_seconds"][engine]))
        if check_sources:
            for name, digest in tuning["source_sha256"].items():
                assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, \
                    f"{name} changed after tuning.py ran"
        tuning_checked = len(tuning["rows"])

    report = {"cells": {"read_parse": len(data["read_parse"]), "replay": len(data["replay"]),
                        "fixed_book": len(data["fixed_book"])},
              "cells_ok": counts["ok"], "cells_stopped_at_declared_limit": counts["stopped"],
              "raw_csv_rows": raw_count,
              "stream_workloads_identical_between_versions": f"{equal_streams} of {comparable_streams} comparable",
              "single_sales_identical_between_versions": equal_sales,
              "completed_sales_matching_sorted_fill_plan": plans,
              "medians_csv_coverage_and_checksums": "PASS",
              "source_hashes_match_measured_code": check_sources,
              "tuning_rows_checked": tuning_checked,
              "dashboard_byte_identical_rebuild": rebuilt}
    (folder / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=HERE / "results")
    verify(parser.parse_args().results)
