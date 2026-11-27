"""Build an offline interactive dashboard from saved measurements only."""

import csv
import json
import statistics
from pathlib import Path


NUMERIC_FIELDS = {
    "n", "queries", "seed", "effective_seed", "hit_rate", "hit_count", "distinct_ids", "repeats",
    "median_prepare_ms", "min_prepare_ms", "max_prepare_ms",
    "median_query_ms", "min_query_ms", "max_query_ms",
    "median_total_ms", "min_total_ms", "max_total_ms",
    "median_current_bytes", "min_current_bytes", "max_current_bytes",
    "median_peak_bytes", "min_peak_bytes", "max_peak_bytes",
}


def write_summary(directory, rows, metadata):
    """Generate measured findings from the same validated data as the dashboard."""
    key = lambda row: (row["n"], row["queries"], row["scenario"],
                       row["duplicate_policy"], row["algorithm"], row["version"])
    index = {key(row): row for row in rows}
    lines = ["# Measured findings", "",
             f"Run `{metadata['run_id']}`; source SHA-256 `{metadata['code_version']}`.", "",
             f"{metadata['workload_count']} workloads, {len(rows)} method/version configurations. "
             f"{metadata['settings']['repeats']} repeats per timing phase and memory case.", "",
             "## Revision comparison across saved workloads", "",
             "Ratios are original median total time / revised median total time. "
             "Values above 1 favor the revision. Each workload has equal weight in "
             "the median ratio; this is not a confidence interval or a universal speedup.", "",
             "| Method | Lower revised total median | Median time ratio | Lower revised peak memory |",
             "| --- | --- | --- | --- |"]
    for method in ("linear", "binary", "set"):
        originals = [row for row in rows if row["version"] == "original" and row["algorithm"] == method]
        pairs = [(row, index[(*key(row)[:-1], "revised")]) for row in originals]
        ratios = [old["median_total_ms"] / new["median_total_ms"] for old, new in pairs]
        lower_time = sum(ratio > 1 for ratio in ratios)
        lower_memory = sum(old["median_peak_bytes"] > new["median_peak_bytes"] for old, new in pairs)
        lines.append(f"| {method} | {lower_time}/{len(pairs)} | {statistics.median(ratios):.3f}x "
                     f"| {lower_memory}/{len(pairs)} |")
    max_n, max_q = max(row["n"] for row in rows), max(row["queries"] for row in rows)
    policies = list(dict.fromkeys(row["duplicate_policy"] for row in rows))
    policy = "unique" if "unique" in policies else policies[0]
    lines += ["", f"## Largest input example: n={max_n:,.0f}, q={max_q:.0f}, {policy} IDs", "",
              "Time is milliseconds per complete batch, including preparation. Memory "
              "is median peak newly traced allocation in KiB, with prepared state and "
              "output alive and existing inputs excluded.", "",
              "| Queries | Method | Original total ms | Revised total ms | Original peak KiB | Revised peak KiB |",
              "| --- | --- | --- | --- | --- | --- |"]
    for scenario in dict.fromkeys(row["scenario"] for row in rows):
        for method in ("linear", "binary", "set"):
            old = index[(max_n, max_q, scenario, policy, method, "original")]
            new = index[(max_n, max_q, scenario, policy, method, "revised")]
            lines.append(f"| {scenario} | {method} | {old['median_total_ms']:.5f} "
                         f"| {new['median_total_ms']:.5f} | {old['median_peak_bytes']/1024:.2f} "
                         f"| {new['median_peak_bytes']/1024:.2f} |")
    lines += ["", "## Interpretation and limits", "",
              "Linear search's early exit reduces work on hits; misses still require "
              "a full scan. Removing defensive copies reduces newly allocated memory. "
              "Binary search retains its sorting cost; set lookups retain the hash-table "
              "memory cost. Compare total time when preparation cannot be reused.", "",
              "Every regression remains in the saved results. A smaller median on a "
              "single machine is descriptive evidence, not proof of an improvement on "
              "all data. One seed was used, versions ran sequentially, and scheduling, "
              "cache warmth, allocator state, and batching overhead can affect ratios.", "",
              "Preparation, query-only, and total timings are independent measurements; "
              "their medians need not add up. Query-only timing reuses prepared state "
              "within a timed repeat. Memory tracing is separate and is not process RSS.", "",
              "See `timing_raw.csv`, `memory_raw.csv`, and `environment.json` for the "
              "raw repeats, batching divisors, actual hit rates, settings, and code identity. "
              "The dashboard and this report are generated from the saved CSVs; no "
              "measurements run when viewing or filtering them.", ""]
    (Path(directory) / "results" / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def generate_dashboard(directory):
    directory = Path(directory)
    results = directory / "results"

    def read(name):
        with (results / name).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            for field in NUMERIC_FIELDS & row.keys():
                row[field] = float(row[field])
        return rows

    timing, memory = read("timing.csv"), read("memory.csv")
    if not timing or not memory:
        raise ValueError("Timing and memory files must contain measurements")
    memory_index = {row["case_id"]: row for row in memory}
    if len(memory_index) != len(memory) or len({row["case_id"] for row in timing}) != len(timing):
        raise ValueError("Duplicate case identifiers in saved results")
    if {row["case_id"] for row in timing} != set(memory_index):
        raise ValueError("Timing and memory cases do not match")
    metadata = json.loads((results / "environment.json").read_text())
    combined = []
    for row in timing:
        other = memory_index[row["case_id"]]
        for key in ("run_id", "code_version", "algorithm", "version", "n", "queries",
                    "scenario", "duplicate_policy", "hit_rate"):
            if row[key] != other[key]:
                raise ValueError(f"Mismatched {key} for {row['case_id']}")
        if row["run_id"] != metadata["run_id"] or row["code_version"] != metadata["code_version"]:
            raise ValueError("Results and environment metadata belong to different runs")
        combined.append({**row, **{key: value for key, value in other.items()
                                  if key.endswith("_bytes")}})
    write_summary(directory, combined, metadata)
    payload = json.dumps({"rows": combined, "environment": metadata}, separators=(",", ":"))
    # Prevent data from terminating the script element if string fields contain '<'.
    payload = payload.replace("<", "\\u003c")
    template = (directory / "dashboard_template.html").read_text(encoding="utf-8")
    if template.count("__DATA_JSON__") != 1:
        raise ValueError("Dashboard template must contain exactly one data placeholder")
    (directory / "dashboard.html").write_text(template.replace("__DATA_JSON__", payload), encoding="utf-8")


if __name__ == "__main__":
    generate_dashboard(Path(__file__).resolve().parent)
