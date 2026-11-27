"""Build a standalone dashboard from saved results. No benchmarks are run."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

BASE = Path(__file__).resolve().parent


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    integer_fields = {"n", "q", "repeat", "repeats", "calls_in_group",
                      "current_traced_bytes", "peak_traced_bytes"}
    float_fields = {"hit_rate", "median_seconds", "min_seconds", "max_seconds",
                    "group_elapsed_seconds", "seconds_per_batch"}
    boolean_fields = {"supplementary", "input_included", "prepared_structure_included", "output_included"}
    for row in rows:
        for key, value in row.items():
            if key in integer_fields:
                row[key] = int(value)
            elif key in float_fields:
                row[key] = float(value) if value else None
            elif key in boolean_fields:
                if value not in ("True", "False"):
                    raise ValueError(f"Invalid Boolean: {key}={value}")
                row[key] = value == "True"
    return rows


def build_payload(results):
    payload = {
        "summary": read_csv(results / "timing_summary.csv"),
        "raw": read_csv(results / "timing_raw.csv"),
        "memory": read_csv(results / "memory.csv"),
        "metadata": json.loads((results / "metadata.json").read_text()),
    }
    meta = payload["metadata"]
    for key, count_key in (("summary", "summary_rows"), ("raw", "raw_timing_rows"), ("memory", "memory_rows")):
        if len(payload[key]) != meta["counts"][count_key]:
            raise ValueError(f"Unexpected number of {key} rows")
        if any(row["run_id"] != meta["run_id"] for row in payload[key]):
            raise ValueError("Result files contain inconsistent run IDs")
    groups = {}
    for row in payload["raw"]:
        key = tuple(row[k] for k in ("case_id", "version", "method", "metric"))
        groups.setdefault(key, []).append(row)
    for row in payload["summary"]:
        key = tuple(row[k] for k in ("case_id", "version", "method", "metric"))
        repeats = groups[key]
        if len(repeats) != 5 or {r["repeat"] for r in repeats} != {1, 2, 3, 4, 5}:
            raise ValueError("Each summary must have exactly five raw repeats")
        if statistics.median(r["seconds_per_batch"] for r in repeats) != row["median_seconds"]:
            raise ValueError("Summary median differs from raw values")
    # Surface stale local files without hiding a valid historical measurement.
    mismatches = []
    for name, expected in meta["source_sha256"].items():
        path = BASE / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            mismatches.append(name)
    payload["source_mismatches_at_build"] = mismatches
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=BASE / "results")
    parser.add_argument("--output", type=Path, default=BASE / "dashboard.html")
    args = parser.parse_args()
    payload = build_payload(args.results_dir)
    template = (BASE / "dashboard_template.html").read_text(encoding="utf-8")
    # Prevent embedded data from terminating its script element.
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    marker = "__SAVED_RESULTS_JSON__"
    if template.count(marker) != 1:
        raise ValueError("Expected exactly one data placeholder")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace(marker, encoded), encoding="utf-8")
    print(f"Dashboard saved: {args.output}")
    print("Open this HTML file in a browser; all data and charts work offline.")
    print("Rebuild after changing measurements. No algorithm or benchmark was executed.")


if __name__ == "__main__":
    main()
