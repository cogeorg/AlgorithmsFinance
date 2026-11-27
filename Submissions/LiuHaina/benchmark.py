"""Measure saved inputs; run timing and traced-memory experiments separately."""

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time
import tracemalloc

BASE = Path(__file__).resolve().parent
METHODS = ("linear_search", "binary_search", "hash_set_search")
METRICS = ("preparation", "query_batch", "total")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head():
    git = BASE.parents[1] / ".git"
    if not git.is_dir():
        return None
    head = (git / "HEAD").read_text().strip()
    if not head.startswith("ref: "):
        return head
    ref = head[5:]
    if (git / ref).is_file():
        return (git / ref).read_text().strip()
    if (git / "packed-refs").is_file():
        for line in (git / "packed-refs").read_text().splitlines():
            if not line.startswith(("#", "^")) and line.endswith(" " + ref):
                return line.split()[0]
    return None


def timed_group(operation, count):
    result = None
    start = time.perf_counter()
    for _ in range(count):
        result = operation()
    elapsed = time.perf_counter() - start
    return elapsed, result


def calibrate(operation, target, maximum):
    operation()  # Untimed warm-up.
    count = 1
    while True:
        elapsed, result = timed_group(operation, count)
        del result
        if elapsed >= target or count >= maximum:
            return count
        count = min(count * 2, maximum)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def check(result, expected):
    assert isinstance(result, list) and result == expected
    assert all(type(value) is bool for value in result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=BASE / "data/inputs.json")
    parser.add_argument("--output-dir", type=Path, default=BASE / "results")
    parser.add_argument("--min-group-seconds", type=float, default=0.003)
    parser.add_argument("--max-calls", type=int, default=8192)
    args = parser.parse_args()
    if args.min_group_seconds <= 0 or args.max_calls < 1:
        parser.error("Group time and call limit must be positive")
    dataset = json.loads(args.input.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    modules = {v: importlib.import_module(m) for v, m in
               (("original", "search_original"), ("revised", "search"))}
    # Independent expected answers, stage parity, and mutation checks before timing.
    for case in dataset["cases"]:
        array = dataset["arrays"][case["array_id"]]["values"]
        before, before_queries = array.copy(), case["queries"].copy()
        members = set(array)
        assert case["expected"] == [q in members for q in case["queries"]]
        assert len(array) == case["n"] and len(case["queries"]) == case["q"]
        for module in modules.values():
            for method in METHODS:
                check(getattr(module, method)(array, case["queries"]), case["expected"])
                state = getattr(module, "prepare_" + method)(array, case["queries"])
                check(getattr(module, "query_" + method)(state, case["queries"]), case["expected"])
                assert array == before and case["queries"] == before_queries
        del members, state
    configurations = [(c, v, m) for c in dataset["cases"] for v in modules for m in METHODS]
    random.Random(2026).shuffle(configurations)
    raw, summaries, memory = [], [], []
    for index, (case, version, method) in enumerate(configurations, 1):
        array = dataset["arrays"][case["array_id"]]["values"]
        queries = case["queries"]
        module = modules[version]
        prepare = getattr(module, "prepare_" + method)
        query = getattr(module, "query_" + method)
        complete = getattr(module, method)
        identity = dict(run_id=run_id, case_id=case["case_id"], n=case["n"], q=case["q"],
                        scenario=case["scenario"], hit_rate=case["hit_rate"],
                        supplementary=case["supplementary"], version=version, method=method)
        for metric in METRICS:
            state = prepare(array, queries) if metric == "query_batch" else None
            if metric == "preparation":
                operation = lambda: prepare(array, queries)
            elif metric == "query_batch":
                operation = lambda: query(state, queries)
            else:
                operation = lambda: complete(array, queries)
            count = calibrate(operation, args.min_group_seconds, args.max_calls)
            values = []
            for repeat in range(1, 6):
                if metric == "query_batch":
                    state = prepare(array, queries)
                elapsed, result = timed_group(operation, count)
                if metric != "preparation":
                    check(result, case["expected"])
                values.append(elapsed / count)
                raw.append(dict(identity, metric=metric, repeat=repeat, calls_in_group=count,
                                group_elapsed_seconds=elapsed, seconds_per_batch=elapsed / count))
                del result
            summaries.append(dict(identity, metric=metric, unit="seconds_per_batch", repeats=5,
                                  calls_in_group=count, median_seconds=statistics.median(values),
                                  min_seconds=min(values), max_seconds=max(values)))
            del operation, state
        if index % 18 == 0:
            print(f"Timing: {index}/{len(configurations)} configurations", flush=True)
    # Every trace is fresh; input exists before tracing, state/output remain alive.
    for case, version, method in configurations:
        array = dataset["arrays"][case["array_id"]]["values"]
        queries = case["queries"]
        module = modules[version]
        gc.collect()
        tracemalloc.start()
        state = getattr(module, "prepare_" + method)(array, queries)
        output = getattr(module, "query_" + method)(state, queries)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        check(output, case["expected"])
        memory.append(dict(run_id=run_id, case_id=case["case_id"], n=case["n"], q=case["q"],
                           scenario=case["scenario"], hit_rate=case["hit_rate"],
                           supplementary=case["supplementary"], version=version, method=method,
                           current_traced_bytes=current, peak_traced_bytes=peak,
                           input_included=False, prepared_structure_included=True, output_included=True))
        del state, output
    sources = ("search.py", "search_original.py", "benchmark.py", "generate_data.py",
               "validate_data.py", "test_search.py", "run_tests.py",
               "snapshots/search.py", "snapshots/search_original.py")
    metadata = dict(
        run_id=run_id, finished_at_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version, python_implementation=platform.python_implementation(),
        executable=sys.executable, platform=platform.platform(), machine=platform.machine(),
        processor=platform.processor(), logical_cpu_count=os.cpu_count(), git_head=git_head(),
        code_version="Source SHA-256 hashes identify measured files, which may be uncommitted.",
        source_sha256={p: sha256(BASE / p) for p in sources},
        input_file=str(args.input.resolve()), input_sha256=sha256(args.input),
        generator=dataset["generator"], skipped_cases=dataset["skipped_cases"],
        timing=dict(timer="time.perf_counter", clock_info=vars(time.get_clock_info("perf_counter")),
                    unit="seconds per complete query batch, not per query", repeats=5, summary="median",
                    warmup="One untimed call plus calibration for each metric/configuration",
                    min_group_seconds=args.min_group_seconds, max_calls=args.max_calls,
                    order="Configurations shuffled with seed 2026; five consecutive repeats per metric",
                    preparation="prepare_*: includes sorting/set creation and revised early checks",
                    query_batch="query_*: fresh preparation outside each repeat, reused read-only within group",
                    total="Independent public-function calls; fresh preparation for every call",
                    aggregation="Metrics measured independently; medians need not add exactly",
                    overhead="Loop/call overhead and previous-result release included; final result alive after timing",
                    short_calls="Grouped up to max_calls; very short calls remain overhead-sensitive",
                    excluded="Data generation/loading/copying, validation, printing, memory tracing, profiling, dashboard",
                    gc_enabled=gc.isenabled()),
        memory=dict(tool="tracemalloc", unit="bytes", runs_per_configuration=1,
                    scope="Fresh separate trace around preparation/query; state and output alive at reading",
                    input_included=False, prepared_structure_included=True, output_included=True,
                    limits="Python traced allocations, not RSS, all native allocations, or auxiliary space alone"),
        counts=dict(cases=len(dataset["cases"]), configurations=len(configurations),
                    raw_timing_rows=len(raw), summary_rows=len(summaries), memory_rows=len(memory)))
    write_csv(args.output_dir / "timing_raw.csv", raw)
    write_csv(args.output_dir / "timing_summary.csv", summaries)
    write_csv(args.output_dir / "memory.csv", memory)
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Saved {len(raw)} raw timing rows, {len(summaries)} summaries, {len(memory)} memory rows.")


if __name__ == "__main__":
    main()
