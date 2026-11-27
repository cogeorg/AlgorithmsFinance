"""Reproducible runtime benchmarks for all mandatory search configurations."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "01_source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from algorithms_finance.algorithms.algorithm_01_linear_search import (  # noqa: E402
    prepare_linear_search,
    query_linear_search,
)
from algorithms_finance.algorithms.algorithm_02_binary_search_recursive import (  # noqa: E402
    prepare_binary_search as prepare_binary_search_recursive,
    query_binary_search_recursive,
)
from algorithms_finance.algorithms.algorithm_03_binary_search_iterative import (  # noqa: E402
    prepare_binary_search as prepare_binary_search_iterative,
    query_binary_search_iterative,
)
from algorithms_finance.algorithms.algorithm_04_hash_set_membership import (  # noqa: E402
    prepare_hash_set,
    query_hash_set_membership,
)
from algorithms_finance.data_01_generation import (  # noqa: E402
    SyntheticCase,
    generate_case,
    mandatory_configurations,
)


BENCHMARK_VERSION = "1.0.0"
WARMUP_RUNS = 1
MEASUREMENT_REPETITIONS = 5

PrepareFunction = Callable[[Sequence[int]], Any]
QueryFunction = Callable[[Any, Sequence[int]], list[bool]]


@dataclass(frozen=True)
class AlgorithmSpec:
    method: str
    version: str
    prepare: PrepareFunction
    query: QueryFunction


def algorithm_specs() -> tuple[AlgorithmSpec, ...]:
    return (
        AlgorithmSpec(
            "linear_search",
            "original",
            prepare_linear_search,
            query_linear_search,
        ),
        AlgorithmSpec(
            "binary_search_recursive",
            "original",
            prepare_binary_search_recursive,
            query_binary_search_recursive,
        ),
        AlgorithmSpec(
            "binary_search_iterative",
            "revised",
            prepare_binary_search_iterative,
            query_binary_search_iterative,
        ),
        AlgorithmSpec(
            "hash_set_membership",
            "original",
            prepare_hash_set,
            query_hash_set_membership,
        ),
    )


def _preparation_iterations(spec: AlgorithmSpec) -> int:
    return 5_000 if spec.method == "linear_search" else 1


def _query_iterations(
    spec: AlgorithmSpec,
    array_size: int,
    query_count: int,
) -> int:
    if spec.method == "linear_search":
        estimated_comparisons = max(1, array_size * query_count)
        return max(1, min(1_000, 5_000 // estimated_comparisons))
    return max(1, min(10_000, 5_000 // query_count))


def _measure_preparation(
    spec: AlgorithmSpec,
    array: Sequence[int],
) -> tuple[float, Any, int]:
    iterations = _preparation_iterations(spec)
    prepared = None
    start = time.perf_counter()
    for _ in range(iterations):
        prepared = spec.prepare(array)
    elapsed = time.perf_counter() - start
    return elapsed / iterations, prepared, iterations


def _measure_query_batch(
    spec: AlgorithmSpec,
    prepared: Any,
    queries: Sequence[int],
    array_size: int,
) -> tuple[float, list[bool], int]:
    iterations = _query_iterations(spec, array_size, len(queries))
    output: list[bool] = []
    start = time.perf_counter()
    for _ in range(iterations):
        output = spec.query(prepared, queries)
    elapsed = time.perf_counter() - start
    return elapsed / iterations, output, iterations


def _warm_up(spec: AlgorithmSpec, case: SyntheticCase) -> None:
    for _ in range(WARMUP_RUNS):
        prepared = spec.prepare(case.array)
        output = spec.query(prepared, case.queries)
        if len(output) != len(case.queries):
            raise AssertionError("warm-up output length does not match query count")


def _expected_output(case: SyntheticCase) -> list[bool]:
    values = set(case.array)
    return [query in values for query in case.queries]


def _code_version() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "Submissions/ErtenZeynep"],
            cwd=PROJECT_ROOT.parents[1],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return f"{commit}-dirty" if dirty else commit
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted-working-tree"


def _base_row(
    case: SyntheticCase,
    spec: AlgorithmSpec,
    code_version: str,
) -> dict[str, Any]:
    metadata = case.metadata
    return {
        "case_id": metadata["case_id"],
        "dataset_class": metadata["dataset_class"],
        "method": spec.method,
        "algorithm_version": spec.version,
        "array_size": metadata["array_size"],
        "query_count": metadata["query_count"],
        "scenario": metadata["scenario"],
        "target_hit_rate": metadata["target_hit_rate"],
        "actual_hit_rate": metadata["actual_hit_rate"],
        "duplicate_policy": metadata["duplicate_policy"],
        "duplicate_rate": metadata["duplicate_rate"],
        "absent_policy": metadata["absent_policy"],
        "array_seed": metadata["array_seed"],
        "query_seed": metadata["query_seed"],
        "array_fingerprint_sha256": metadata["array_fingerprint_sha256"],
        "query_fingerprint_sha256": metadata["query_fingerprint_sha256"],
        "measurement_unit": "seconds_per_complete_query_batch",
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "code_version": code_version,
        "benchmark_version": BENCHMARK_VERSION,
    }


def run_benchmarks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    specs = algorithm_specs()
    code_version = _code_version()

    for case_index, config in enumerate(mandatory_configurations()):
        case = generate_case(config)
        expected = _expected_output(case)
        original_array = case.array.copy()
        original_queries = case.queries.copy()

        for spec in specs:
            _warm_up(spec, case)

        for repetition in range(1, MEASUREMENT_REPETITIONS + 1):
            shift = (case_index + repetition - 1) % len(specs)
            ordered_specs = specs[shift:] + specs[:shift]

            for order_index, spec in enumerate(ordered_specs, start=1):
                preparation_seconds, prepared, preparation_iterations = (
                    _measure_preparation(spec, case.array)
                )
                query_seconds, output, query_iterations = _measure_query_batch(
                    spec,
                    prepared,
                    case.queries,
                    config.array_size,
                )

                if output != expected:
                    raise AssertionError(
                        f"incorrect output during benchmark: {spec.method}"
                    )
                if case.array != original_array or case.queries != original_queries:
                    raise AssertionError(
                        f"input mutation during benchmark: {spec.method}"
                    )

                row = _base_row(case, spec, code_version)
                row.update(
                    {
                        "repetition": repetition,
                        "execution_order": order_index,
                        "preparation_inner_iterations": preparation_iterations,
                        "query_inner_iterations": query_iterations,
                        "preparation_seconds": preparation_seconds,
                        "query_batch_seconds": query_seconds,
                        "query_seconds_per_query": (
                            query_seconds / config.query_count
                        ),
                        "total_seconds": preparation_seconds + query_seconds,
                    }
                )
                rows.append(row)
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["case_id"]), str(row["method"]))
        groups.setdefault(key, []).append(row)

    summaries = []
    for grouped_rows in groups.values():
        first = grouped_rows[0]
        summary = {
            key: value
            for key, value in first.items()
            if key
            not in {
                "repetition",
                "execution_order",
                "preparation_inner_iterations",
                "query_inner_iterations",
                "preparation_seconds",
                "query_batch_seconds",
                "query_seconds_per_query",
                "total_seconds",
            }
        }
        summary.update(
            {
                "repetition_count": len(grouped_rows),
                "median_preparation_seconds": statistics.median(
                    float(row["preparation_seconds"]) for row in grouped_rows
                ),
                "median_query_batch_seconds": statistics.median(
                    float(row["query_batch_seconds"]) for row in grouped_rows
                ),
                "median_query_seconds_per_query": statistics.median(
                    float(row["query_seconds_per_query"])
                    for row in grouped_rows
                ),
                "median_total_seconds": statistics.median(
                    float(row["total_seconds"]) for row in grouped_rows
                ),
            }
        )
        summaries.append(summary)
    return summaries


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_environment(path: Path, code_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "benchmark_version": BENCHMARK_VERSION,
        "python_version": platform.python_version(),
        "python_full_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "code_version": code_version,
        "warmup_runs": WARMUP_RUNS,
        "measurement_repetitions": MEASUREMENT_REPETITIONS,
        "timer": "time.perf_counter",
        "time_unit": "seconds",
        "query_measurement": "per complete ordered query batch",
        "total_definition": "preparation_seconds + query_batch_seconds",
        "data_generation_timed": False,
        "tests_timed": False,
        "printing_timed": False,
        "memory_tracing_enabled": False,
    }
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "04_results" / "benchmarks",
    )
    args = parser.parse_args()

    rows = run_benchmarks()
    summaries = summarize(rows)
    _write_csv(args.output_dir / "result_01_raw_repetitions.csv", rows)
    _write_csv(args.output_dir / "result_02_median_summary.csv", summaries)
    _write_environment(
        PROJECT_ROOT / "04_results" / "metadata" / "result_01_environment.json",
        str(rows[0]["code_version"]),
    )
    print(
        f"Saved {len(rows)} raw rows and {len(summaries)} summaries "
        f"to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
