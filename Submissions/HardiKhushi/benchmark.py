"""Measure both manual versions across a reproducible workload matrix."""

import argparse
import csv
import hashlib
import json
import math
import platform
import shutil
import statistics
import subprocess
import sys
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

from data_generator import DUPLICATE_POLICIES, SCENARIOS, generate_workload
from search import VERSIONS

HERE = Path(__file__).resolve().parent
PHASES = ("prepare", "query", "total")
SOURCE_FILES = ("search.py", "search_original.py", "data_generator.py", "benchmark.py")


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def source_identity():
    hashes = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
              for name in SOURCE_FILES}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE,
                              capture_output=True, text=True, check=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE,
                                capture_output=True, text=True, check=True).stdout
        dirty = bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        head, dirty = None, None
    return {"code_version": digest, "source_sha256": hashes,
            "git_head": head, "submission_has_uncommitted_changes": dirty}


def measure_phase(phase, prepare, query, ids, queries, expected, executions):
    """Return untraced nanoseconds for a batch; validate after the clock stops.

    Query-only timing creates fresh prepared state outside its timed batch.
    Preparation and total timing rebuild state on every execution.
    """
    if phase == "prepare":
        start = perf_counter_ns()
        for _ in range(executions):
            state = prepare(ids)
        elapsed = perf_counter_ns() - start
        assert query(state, queries) == expected
    elif phase == "query":
        state = prepare(ids)
        start = perf_counter_ns()
        for _ in range(executions):
            result = query(state, queries)
        elapsed = perf_counter_ns() - start
        assert result == expected
    elif phase == "total":
        start = perf_counter_ns()
        for _ in range(executions):
            state = prepare(ids)
            result = query(state, queries)
        elapsed = perf_counter_ns() - start
        assert result == expected
    else:
        raise ValueError(f"Unknown phase: {phase}")
    return elapsed


def measure_memory(prepare, query, ids, queries, expected):
    """Trace one full preparation/query call, retaining state and output."""
    tracemalloc.start()
    try:
        state = prepare(ids)
        result = query(state, queries)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result == expected
    return current, peak


def archive_previous(results):
    names = ("timing.csv", "memory.csv", "timing_raw.csv", "memory_raw.csv",
             "environment.json", "SUMMARY.md")
    existing = [results / name for name in names if (results / name).exists()]
    if not existing:
        return None
    previous = "legacy"
    metadata = results / "environment.json"
    if metadata.exists():
        previous = json.loads(metadata.read_text())["run_id"]
    destination = results / "history" / previous
    if destination.exists():
        destination = destination.with_name(previous + "-" + datetime.now(timezone.utc).strftime("%H%M%S%f"))
    destination.mkdir(parents=True)
    for path in existing:
        shutil.copy2(path, destination / path.name)
        assert path.read_bytes() == (destination / path.name).read_bytes()
    return str(destination.relative_to(HERE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=positive_int, default=[1000, 10000, 100000])
    parser.add_argument("--queries", nargs="+", type=positive_int, default=[1, 100])
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument("--duplicate-policies", nargs="+", choices=DUPLICATE_POLICIES,
                        default=list(DUPLICATE_POLICIES))
    parser.add_argument("--repeats", type=positive_int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-ms", type=positive_float, default=5.0)
    args = parser.parse_args()
    identity = source_identity()
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    timing, memory, raw_timing, raw_memory = [], [], [], []
    sizes, counts = sorted(set(args.sizes)), sorted(set(args.queries))
    scenarios = list(dict.fromkeys(args.scenarios))
    policies = list(dict.fromkeys(args.duplicate_policies))
    workload_count = len(sizes) * len(counts) * len(scenarios) * len(policies)
    completed = 0
    for n in sizes:
        for count in counts:
            for scenario in scenarios:
                for policy in policies:
                    workload = generate_workload(n, count, seed=args.seed,
                                                 scenario=scenario, duplicate_policy=policy)
                    ids, queries, expected = workload.ids, workload.queries, workload.expected
                    original_ids, original_queries = ids.copy(), queries.copy()
                    for version, methods in VERSIONS.items():
                        for name in ("linear", "binary", "set"):
                            prepare, query = methods["prepare"][name], methods["query"][name]
                            assert methods["batch"][name](ids, queries) == expected
                            case_id = f"n{n}-q{count}-{scenario}-{policy}-{name}-{version}"
                            common = {"run_id": run_id, "case_id": case_id,
                                      "algorithm": name, "version": version, **workload.settings,
                                      "repeats": args.repeats, "code_version": identity["code_version"]}
                            summary = dict(common)
                            for phase in PHASES:
                                # Untimed calibration determines batching for very short calls.
                                pilot = measure_phase(phase, prepare, query, ids, queries, expected, 1)
                                executions = min(65536, max(1, math.ceil(args.target_ms * 1e6 / max(pilot, 1))))
                                samples = []
                                for repeat in range(1, args.repeats + 1):
                                    elapsed_ns = measure_phase(phase, prepare, query, ids, queries,
                                                               expected, executions)
                                    elapsed_ms = elapsed_ns / 1e6
                                    per_execution = elapsed_ms / executions
                                    samples.append(per_execution)
                                    raw_timing.append({"run_id": run_id, "case_id": case_id,
                                                       "phase": phase, "repeat": repeat,
                                                       "executions": executions,
                                                       "elapsed_batch_ms": elapsed_ms,
                                                       "per_execution_ms": per_execution})
                                for label, function in (("median", statistics.median),
                                                        ("min", min), ("max", max)):
                                    summary[f"{label}_{phase}_ms"] = function(samples)
                            timing.append(summary)
                            currents, peaks = [], []
                            for repeat in range(1, args.repeats + 1):
                                current, peak = measure_memory(prepare, query, ids, queries, expected)
                                currents.append(current)
                                peaks.append(peak)
                                raw_memory.append({"run_id": run_id, "case_id": case_id,
                                                   "repeat": repeat, "current_bytes": current,
                                                   "peak_bytes": peak})
                            mem_summary = dict(common)
                            for metric, samples in (("current", currents), ("peak", peaks)):
                                for label, function in (("median", statistics.median), ("min", min), ("max", max)):
                                    mem_summary[f"{label}_{metric}_bytes"] = function(samples)
                            memory.append(mem_summary)
                    assert ids == original_ids and queries == original_queries
                    completed += 1
                    print(f"[{completed}/{workload_count}] n={n}, q={count}, {scenario}, {policy}: all six variants correct", flush=True)
    # Source changes during a long run invalidate attribution.
    assert source_identity()["source_sha256"] == identity["source_sha256"]
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    archived = archive_previous(results)
    metadata = {
        "run_id": run_id, "started_utc": now.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(), **identity,
        "python": sys.version, "platform": platform.platform(),
        "machine": platform.machine(), "processor": platform.processor(),
        "workload_count": workload_count, "configuration_count": len(timing),
        "settings": {"sizes": sizes, "query_counts": counts, "scenarios": scenarios,
                     "duplicate_policies": policies, "repeats": args.repeats,
                     "seed": args.seed, "target_batch_ms": args.target_ms},
        "protocol": {
            "time_unit": "milliseconds per complete preparation/query-batch/total execution",
            "timing": "perf_counter_ns; preflight warm-up plus per-phase calibration; five repeats by default; adaptive batching capped at 65536 executions; raw elapsed batches and divisors saved",
            "prepare": "fresh state each execution; includes constructor and prior-state release within a timed batch",
            "query": "fresh prepared state outside each repeat; same prepared state reused within that repeat's timed query batch",
            "total": "fresh preparation plus all queries each execution; measured independently, not a sum of phase medians",
            "excluded": "input generation, correctness checks, printing, memory tracing, profiling, dashboard rendering",
            "memory": "separate fresh tracemalloc runs; current and peak bytes with prepared state and output alive; existing inputs excluded; not RSS or every native allocation",
            "scope": "single machine and seed; original/revised measured sequentially; scheduling, warm caches and allocator state can affect results; no confidence intervals",
        },
        "archived_previous_results": archived,
    }
    write_csv(results / "timing.csv", timing)
    write_csv(results / "memory.csv", memory)
    write_csv(results / "timing_raw.csv", raw_timing)
    write_csv(results / "memory_raw.csv", raw_memory)
    (results / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(timing)} configurations, {len(raw_timing)} raw timing rows, {len(raw_memory)} raw memory rows.", flush=True)
    # Dashboard generation is deliberately outside all measurement regions.
    from dashboard import generate_dashboard
    generate_dashboard(HERE)
    print(f"Dashboard: {HERE / 'dashboard.html'}", flush=True)


if __name__ == "__main__":
    main()
