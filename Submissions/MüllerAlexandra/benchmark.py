"""Reproducible timing and traced-memory measurements for all lab methods."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import gc
import json
import math
import os
from pathlib import Path
import platform
import statistics
import time
import tracemalloc
from typing import Any, Callable

from algorithms import (
    prepare_binary,
    prepare_hash_set,
    prepare_linear,
    query_binary_iterative,
    query_binary_recursive,
    query_hash_set,
    query_linear,
)
from synthetic_data import DuplicatePolicy, generate_synthetic_data


PrepareFunction = Callable[[list[int]], Any]
QueryFunction = Callable[[Any, list[int]], list[bool]]


@dataclass(frozen=True)
class MethodSpec:
    name: str
    version: str
    prepare: PrepareFunction
    query: QueryFunction

    @property
    def label(self) -> str:
        return f"{self.name} ({self.version})"


METHODS = (
    MethodSpec("linear_search", "original", prepare_linear, query_linear),
    MethodSpec(
        "binary_search", "original_recursive", prepare_binary, query_binary_recursive
    ),
    MethodSpec(
        "binary_search", "revised_iterative", prepare_binary, query_binary_iterative
    ),
    MethodSpec("hash_set", "standard_library", prepare_hash_set, query_hash_set),
)

SCENARIOS = (
    ("all_absent", 0.0),
    ("mixed", 0.5),
    ("all_present", 1.0),
)


def benchmark_cases(
    sizes: list[int], query_counts: list[int]
) -> list[tuple[int, int, str, float]]:
    """Return the required matrix; a one-query batch cannot be genuinely mixed."""
    cases: list[tuple[int, int, str, float]] = []
    for n in sizes:
        for q in query_counts:
            for scenario, hit_rate in SCENARIOS:
                if scenario == "mixed" and q < 2:
                    continue
                cases.append((n, q, scenario, hit_rate))
    return cases


def _time_average(operation: Callable[[], Any], loops: int) -> tuple[float, Any]:
    result: Any = None
    start = time.perf_counter()
    for _ in range(loops):
        result = operation()
    elapsed = time.perf_counter() - start
    return elapsed / loops, result


def _calibrate_loops(
    operation: Callable[[], Any], target_seconds: float, maximum: int = 1_000
) -> int:
    """Choose batching loops using an untimed-for-reporting calibration call."""
    elapsed, _ = _time_average(operation, 1)
    if elapsed <= 0.0:
        return maximum
    return max(1, min(maximum, math.ceil(target_seconds / elapsed)))


def measure_timing(
    method: MethodSpec,
    ids: list[int],
    queries: list[int],
    expected: list[bool],
    repeats: int,
    target_seconds: float,
) -> dict[str, Any]:
    """Warm up, then time preparation, query batch, and combined operation."""
    warm_prepared = method.prepare(ids)
    warm_output = method.query(warm_prepared, queries)
    if warm_output != expected:
        raise AssertionError(f"incorrect warm-up output from {method.label}")

    preparation_loops = _calibrate_loops(
        lambda: method.prepare(ids), target_seconds
    )
    query_loops = _calibrate_loops(
        lambda: method.query(warm_prepared, queries), target_seconds
    )

    def prepare_and_query() -> list[bool]:
        return method.query(method.prepare(ids), queries)

    total_loops = _calibrate_loops(prepare_and_query, target_seconds)
    raw_preparation: list[float] = []
    raw_query_batch: list[float] = []
    raw_total: list[float] = []

    for _ in range(repeats):
        preparation_seconds, prepared = _time_average(
            lambda: method.prepare(ids), preparation_loops
        )
        query_seconds, output = _time_average(
            lambda: method.query(prepared, queries), query_loops
        )
        total_seconds, combined_output = _time_average(
            prepare_and_query, total_loops
        )
        if output != expected or combined_output != expected:
            raise AssertionError(f"incorrect measured output from {method.label}")
        raw_preparation.append(preparation_seconds)
        raw_query_batch.append(query_seconds)
        raw_total.append(total_seconds)

    return {
        "raw_seconds": {
            "preparation": raw_preparation,
            "query_batch": raw_query_batch,
            "total": raw_total,
        },
        "median_seconds": {
            "preparation": statistics.median(raw_preparation),
            "query_batch": statistics.median(raw_query_batch),
            "total": statistics.median(raw_total),
        },
        "batching_loops": {
            "preparation": preparation_loops,
            "query_batch": query_loops,
            "total": total_loops,
        },
    }


def measure_traced_memory(
    method: MethodSpec,
    ids: list[int],
    queries: list[int],
    expected: list[bool],
) -> dict[str, int]:
    """Measure a fresh preparation and query run after the input already exists."""
    gc.collect()
    tracemalloc.start()
    try:
        prepared = method.prepare(ids)
        output = method.query(prepared, queries)
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        if output != expected:
            raise AssertionError(f"incorrect memory-run output from {method.label}")
        # Both prepared and output deliberately remain alive at the reading above.
        return {"current_bytes": current_bytes, "peak_bytes": peak_bytes}
    finally:
        tracemalloc.stop()


def environment_details(code_version: str) -> dict[str, Any]:
    uname = platform.uname()
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_version": code_version,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "system": uname.system,
        "release": uname.release,
        "machine": uname.machine,
        "processor": uname.processor,
        "logical_cpu_count": os.cpu_count(),
        "timer": "time.perf_counter",
    }


def run_benchmarks(
    *,
    code_version: str,
    output_dir: Path,
    sizes: list[int],
    query_counts: list[int],
    duplicate_policy: DuplicatePolicy,
    base_seed: int,
    repeats: int,
    target_seconds: float,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    cases = benchmark_cases(sizes, query_counts)

    for case_index, (n, q, scenario, requested_hit_rate) in enumerate(cases):
        seed = base_seed + case_index
        dataset = generate_synthetic_data(
            n=n,
            q=q,
            hit_rate=requested_hit_rate,
            duplicate_policy=duplicate_policy,
            seed=seed,
        )
        expected = [query in set(dataset.ids) for query in dataset.queries]
        original_ids = dataset.ids.copy()

        for method in METHODS:
            timing = measure_timing(
                method,
                dataset.ids,
                dataset.queries,
                expected,
                repeats,
                target_seconds,
            )
            memory = measure_traced_memory(
                method, dataset.ids, dataset.queries, expected
            )
            if dataset.ids != original_ids:
                raise AssertionError(f"{method.label} changed the input array")
            records.append(
                {
                    "method": method.name,
                    "version": method.version,
                    "label": method.label,
                    "n": n,
                    "q": q,
                    "scenario": scenario,
                    "requested_hit_rate": requested_hit_rate,
                    "actual_hit_rate": dataset.actual_hit_rate,
                    "duplicate_policy": duplicate_policy,
                    "seed": seed,
                    **timing,
                    "tracemalloc": memory,
                }
            )

    payload = {
        "schema_version": 1,
        "environment": environment_details(code_version),
        "settings": {
            "sizes": sizes,
            "query_counts": query_counts,
            "scenarios": [
                {"name": name, "requested_hit_rate": rate}
                for name, rate in SCENARIOS
            ],
            "duplicate_policy": duplicate_policy,
            "base_seed": base_seed,
            "repeats": repeats,
            "warm_up_runs": 1,
            "short_call_target_seconds": target_seconds,
            "mixed_q1_omitted": True,
        },
        "definitions": {
            "preparation": "seconds per preparation; sorting/set construction included",
            "query_batch": "seconds per complete ordered query batch",
            "total": "seconds per fresh preparation plus one complete query batch",
            "timing_excludes": [
                "data generation",
                "tests",
                "printing",
                "AI calls",
                "dashboard rendering",
                "memory tracing",
            ],
            "tracemalloc": (
                "fresh run separate from timing; input allocated before tracing and excluded; "
                "prepared structure and returned output alive and included at reading; peak "
                "covers traced Python allocations during preparation and query"
            ),
        },
        "records": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "raw_benchmark.json", payload)
    _write_csv(output_dir / "benchmark_summary.csv", records)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "method",
        "version",
        "label",
        "n",
        "q",
        "scenario",
        "requested_hit_rate",
        "actual_hit_rate",
        "duplicate_policy",
        "seed",
        "preparation_median_seconds",
        "query_batch_median_seconds",
        "total_median_seconds",
        "tracemalloc_current_bytes",
        "tracemalloc_peak_bytes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "method": record["method"],
                    "version": record["version"],
                    "label": record["label"],
                    "n": record["n"],
                    "q": record["q"],
                    "scenario": record["scenario"],
                    "requested_hit_rate": record["requested_hit_rate"],
                    "actual_hit_rate": record["actual_hit_rate"],
                    "duplicate_policy": record["duplicate_policy"],
                    "seed": record["seed"],
                    "preparation_median_seconds": record["median_seconds"][
                        "preparation"
                    ],
                    "query_batch_median_seconds": record["median_seconds"][
                        "query_batch"
                    ],
                    "total_median_seconds": record["median_seconds"]["total"],
                    "tracemalloc_current_bytes": record["tracemalloc"][
                        "current_bytes"
                    ],
                    "tracemalloc_peak_bytes": record["tracemalloc"]["peak_bytes"],
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--code-version",
        required=True,
        help="Commit hash or other immutable identifier for the measured code",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--sizes", type=int, nargs="+", default=[1_000, 10_000, 100_000])
    parser.add_argument("--query-counts", type=int, nargs="+", default=[1, 100])
    parser.add_argument("--duplicate-policy", choices=["allow", "unique"], default="allow")
    parser.add_argument("--base-seed", type=int, default=20261120)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--target-seconds", type=float, default=0.005)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_benchmarks(
        code_version=args.code_version,
        output_dir=args.output_dir,
        sizes=args.sizes,
        query_counts=args.query_counts,
        duplicate_policy=args.duplicate_policy,
        base_seed=args.base_seed,
        repeats=args.repeats,
        target_seconds=args.target_seconds,
    )
    print(f"Saved {len(payload['records'])} records to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
