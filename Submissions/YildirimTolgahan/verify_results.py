"""Verify saved experiment coverage, CSV agreement, hashes and HTML rebuild."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import tempfile

from algorithms import METHODS
from benchmark import TIME_KEYS, CALL_KEYS, workload_specs
from dashboard import build

HERE = Path(__file__).resolve().parent

if not __debug__:
    raise SystemExit("Verification requires assertions. Run Python without -O or -OO.")


def verify(folder):
    source = folder / "measurements.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    metadata, rows = data["metadata"], data["rows"]
    settings = metadata["settings"]
    assert metadata["schema_version"] == 2
    specs = workload_specs(settings["sizes"], settings["query_counts"], settings["hit_rates"], settings["duplicate_policies"])
    assert len(rows) == len(specs) * len(METHODS)
    expected_methods = {(m.name, m.version) for m in METHODS}
    for name, digest in metadata["source_sha256"].items():
        relative = metadata.get("source_paths", {}).get(name, name)
        path = (HERE / relative).resolve()
        assert path.is_relative_to(HERE)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, relative
    for name, digest in metadata.get("presentation_sha256", {}).items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, name
    groups = defaultdict(list)
    for row in rows:
        groups[row["n"], row["q"], row["requested_hit_rate"], row["duplicate_policy"]].append(row)
        assert row["actual_hit_rate"] == row["requested_hit_rate"]
        assert row["peak_traced_bytes"] >= row["current_traced_bytes"] >= 0
        raw = row["raw_repeats"]
        assert [r["repeat"] for r in raw] == list(range(1, settings["repeats"] + 1))
        for key in TIME_KEYS:
            assert row[key] == statistics.median(r[key] for r in raw)
            assert all(math.isfinite(r[key]) and r[key] >= 0 for r in raw)
        for key in CALL_KEYS:
            assert all(1 <= r[key] <= 20000 for r in raw)
    assert set(groups) == set(specs)
    for group in groups.values():
        assert {(r["method"], r["version"]) for r in group} == expected_methods
        assert len({r["seed"] for r in group}) == len({r["order_seed"] for r in group}) == 1
        rng = random.Random(group[0]["order_seed"])
        for repeat in range(settings["repeats"]):
            order = list(METHODS)
            rng.shuffle(order)
            positions = {(m.name, m.version): index for index, m in enumerate(order, 1)}
            for row in group:
                assert row["raw_repeats"][repeat]["method_position"] == positions[row["method"], row["version"]]
    with (folder / "summary.csv").open(newline="", encoding="utf-8") as f:
        csv_summary = list(csv.DictReader(f))
    assert csv_summary == [{key: str(value) for key, value in row.items() if key != "raw_repeats"} for row in rows]
    with (folder / "raw_repeats.csv").open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        csv_raw = list(reader)
    expected_raw = []
    for row in rows:
        for sample in row["raw_repeats"]:
            merged = {**row, **sample}
            expected_raw.append({key: str(merged[key]) for key in columns})
    assert csv_raw == expected_raw
    reuse_path = folder / "reuse.json"
    if reuse_path.exists():
        reuse = json.loads(reuse_path.read_text(encoding="utf-8"))
        for name, digest in reuse["metadata"]["source_sha256"].items():
            assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, name
        assert set(reuse["scenarios"]) == {"rebuild_each_batch", "build_once"}
        for scenario in reuse["scenarios"].values():
            samples = scenario["raw_repeats"]
            assert len(samples) == reuse["metadata"]["repeats"] >= 5
            assert [sample["repeat"] for sample in samples] == list(range(1, len(samples) + 1))
            assert scenario["median_ms"] == statistics.median(sample["ms"] for sample in samples)
            assert all(math.isfinite(sample["ms"]) and sample["ms"] >= 0 and 1 <= sample["calls"] <= 20000 for sample in samples)
        for index in range(reuse["metadata"]["repeats"]):
            assert sorted(s["raw_repeats"][index]["position"] for s in reuse["scenarios"].values()) == [1, 2]
    speed_path = folder / "speed_budget.json"
    if speed_path.exists():
        speed = json.loads(speed_path.read_text(encoding="utf-8"))
        assert speed["measurements_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert speed["units"] == "seconds" and speed["passed"] is True
        assert speed["saved_sample_count"] == len(csv_raw)
        saved_maximum = max(sample["total_ms"] / 1000 for row in rows for sample in row["raw_repeats"])
        assert speed["saved_maximum_seconds"] == saved_maximum < speed["limit_seconds"]
        assert all(math.isfinite(t) and 0 <= t < speed["limit_seconds"] for t in speed["live"]["samples_seconds"])
        for name, digest in speed["source_sha256"].items():
            assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, name
    with tempfile.NamedTemporaryFile(dir=folder, suffix=".html", delete=False) as f:
        temporary = Path(f.name)
    try:
        build(source, temporary)
        assert temporary.read_bytes() == (folder / "dashboard.html").read_bytes()
    finally:
        temporary.unlink()
    report = {"summary_rows": len(rows), "raw_repeat_rows": len(csv_raw),
              "independent_phase_samples": len(csv_raw) * len(TIME_KEYS),
              "coverage_csv_medians_order_and_hashes": "PASS",
              "dashboard_byte_identical_rebuild": True,
              "reuse_scenarios_verified": reuse_path.exists(),
              "speed_budget_verified": speed_path.exists()}
    (folder / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=HERE / "results")
    verify(parser.parse_args().results)
