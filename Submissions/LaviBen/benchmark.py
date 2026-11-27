"""Fixed-input runtime measurements for every search method and version."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter_ns
from typing import Any

from search_algorithms import (
    binary_iterative_query_batch,
    binary_recursive_query_batch,
    hash_set_query_batch,
    linear_query_batch,
    prepare_binary,
    prepare_hash_set,
    prepare_linear,
)
from synthetic_data import (
    DUPLICATE_POLICY,
    GENERATOR_VERSION,
    generate_search_case,
)


DEFAULT_SIZES = (1_000, 10_000, 100_000)
DEFAULT_QUERY_COUNTS = (1, 100)
SCENARIOS = ("all_present", "all_absent", "mixed")
SCENARIO_HIT_RATES = {
    "all_present": 1.0,
    "all_absent": 0.0,
    "mixed": 0.5,
}
DEFAULT_REPEATS = 5
DEFAULT_BASE_SEED = 2026

PrepareMethod = Callable[[Sequence[int]], Any]
QueryBatchMethod = Callable[[Any, Sequence[int]], list[bool]]


@dataclass(frozen=True)
class AlgorithmSpec:
    name: str
    version: str
    prepare: PrepareMethod
    query_batch: QueryBatchMethod


ALGORITHMS: tuple[AlgorithmSpec, ...] = (
    AlgorithmSpec("Linear search", "v1", prepare_linear, linear_query_batch),
    AlgorithmSpec(
        "Binary search recursive v1",
        "v1",
        prepare_binary,
        binary_recursive_query_batch,
    ),
    AlgorithmSpec(
        "Binary search iterative v2",
        "v2",
        prepare_binary,
        binary_iterative_query_batch,
    ),
    AlgorithmSpec(
        "Hash set membership",
        "stdlib-set",
        prepare_hash_set,
        hash_set_query_batch,
    ),
)


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    array_size: int
    query_count: int
    scenario: str
    requested_hit_rate: float
    realized_hit_rate: float
    realized_hit_count: int
    seed: int
    generator_version: int
    duplicate_policy: str
    value_pool_size: int
    input_sha256: str


@dataclass(frozen=True)
class RawTiming:
    case_id: str
    algorithm: str
    version: str
    repeat: int
    order_position: int
    input_sha256: str
    preparation_ns: int
    query_batch_ns: int
    combined_ns: int


@dataclass(frozen=True)
class SummaryResult:
    case_id: str
    array_size: int
    query_count: int
    scenario: str
    algorithm: str
    version: str
    repeats: int
    preparation_median_ms: float
    query_batch_median_ms: float
    combined_median_ms: float


@dataclass(frozen=True)
class BenchmarkRun:
    metadata: dict[str, Any]
    cases: list[BenchmarkCase]
    raw_results: list[RawTiming]
    summary: list[SummaryResult]


@dataclass(frozen=True)
class _FixedInput:
    case: BenchmarkCase
    ids: tuple[int, ...]
    queries: tuple[int, ...]


def _input_digest(ids: Sequence[int], queries: Sequence[int]) -> str:
    encoded = json.dumps(
        {"ids": ids, "queries": queries},
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_digest() -> str:
    source_directory = Path(__file__).resolve().parent
    source_files = (
        "benchmark.py",
        "dashboard.py",
        "search_algorithms.py",
        "synthetic_data.py",
    )
    digest = hashlib.sha256()
    for filename in source_files:
        path = source_directory / filename
        digest.update(filename.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_output(*arguments: str) -> str:
    repository_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _metadata(
    *,
    sizes: Sequence[int],
    query_counts: Sequence[int],
    scenarios: Sequence[str],
    repeats: int,
    base_seed: int,
) -> dict[str, Any]:
    submission_status = _git_output(
        "status",
        "--porcelain",
        "--",
        "Submissions/LaviBen",
    )
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "units": {
            "raw_timings": "nanoseconds",
            "summary_timings": "milliseconds",
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "python_full_version": sys.version,
            "system": platform.system(),
            "system_release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
            "logical_cpu_count": os.cpu_count(),
        },
        "code_version": {
            "git_commit": _git_output("rev-parse", "HEAD"),
            "submission_tree_dirty": bool(submission_status),
            "source_sha256": _source_digest(),
        },
        "benchmark_settings": {
            "sizes": list(sizes),
            "query_counts": list(query_counts),
            "scenarios": list(scenarios),
            "repeats": repeats,
            "base_seed": base_seed,
            "clock": "time.perf_counter_ns",
            "summary_statistic": "median",
            "data_generation_timed": False,
            "garbage_collection_disabled_during_timing": True,
            "algorithm_order": "deterministic rotation by repeat",
        },
        "generator_settings": {
            "generator_version": GENERATOR_VERSION,
            "duplicate_policy": DUPLICATE_POLICY,
            "value_pool_size": "max(1, array_size // 3)",
            "sampling": "with replacement",
            "query_order": "seeded shuffle",
            "mixed_requested_hit_rate": 0.5,
            "hit_count_rounding": "nearest integer, halves rounded up",
        },
    }


def _build_fixed_inputs(
    sizes: Sequence[int],
    query_counts: Sequence[int],
    scenarios: Sequence[str],
    *,
    base_seed: int,
) -> list[_FixedInput]:
    fixed_inputs: list[_FixedInput] = []
    case_index = 0

    for array_size in sizes:
        if array_size < 0:
            raise ValueError("array sizes must be non-negative")
        for query_count in query_counts:
            if query_count < 0:
                raise ValueError("query counts must be non-negative")
            for scenario in scenarios:
                if scenario not in SCENARIO_HIT_RATES:
                    raise ValueError(f"unknown scenario: {scenario}")

                seed = base_seed + case_index
                requested_hit_rate = SCENARIO_HIT_RATES[scenario]
                generated_ids, generated_queries = generate_search_case(
                    array_size,
                    query_count,
                    seed=seed,
                    hit_rate=requested_hit_rate,
                )
                ids = tuple(generated_ids)
                queries = tuple(generated_queries)
                lookup = set(ids)
                realized_hits = sum(query in lookup for query in queries)
                realized_hit_rate = (
                    realized_hits / query_count if query_count else 0.0
                )
                case_id = f"n{array_size}_q{query_count}_{scenario}"
                case = BenchmarkCase(
                    case_id=case_id,
                    array_size=array_size,
                    query_count=query_count,
                    scenario=scenario,
                    requested_hit_rate=requested_hit_rate,
                    realized_hit_rate=realized_hit_rate,
                    realized_hit_count=realized_hits,
                    seed=seed,
                    generator_version=GENERATOR_VERSION,
                    duplicate_policy=DUPLICATE_POLICY,
                    value_pool_size=max(1, array_size // 3),
                    input_sha256=_input_digest(ids, queries),
                )
                fixed_inputs.append(_FixedInput(case, ids, queries))
                case_index += 1

    return fixed_inputs


def _measure_fixed_inputs(
    fixed_inputs: Sequence[_FixedInput],
    *,
    repeats: int,
) -> list[RawTiming]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")

    raw_results: list[RawTiming] = []
    for fixed_input in fixed_inputs:
        lookup = set(fixed_input.ids)
        expected = [query in lookup for query in fixed_input.queries]

        for algorithm in ALGORITHMS:
            prepared = algorithm.prepare(fixed_input.ids)
            if algorithm.query_batch(prepared, fixed_input.queries) != expected:
                raise AssertionError(f"{algorithm.name} failed warm-up correctness")

        for repeat_index in range(repeats):
            rotation = repeat_index % len(ALGORITHMS)
            ordered_algorithms = ALGORITHMS[rotation:] + ALGORITHMS[:rotation]
            for order_position, algorithm in enumerate(ordered_algorithms):
                garbage_collection_was_enabled = gc.isenabled()
                if garbage_collection_was_enabled:
                    gc.disable()
                try:
                    combined_started = perf_counter_ns()
                    preparation_started = perf_counter_ns()
                    prepared = algorithm.prepare(fixed_input.ids)
                    preparation_finished = perf_counter_ns()
                    query_started = perf_counter_ns()
                    result = algorithm.query_batch(prepared, fixed_input.queries)
                    query_finished = perf_counter_ns()
                finally:
                    if garbage_collection_was_enabled:
                        gc.enable()

                if result != expected:
                    raise AssertionError(f"{algorithm.name} returned incorrect results")

                raw_results.append(
                    RawTiming(
                        case_id=fixed_input.case.case_id,
                        algorithm=algorithm.name,
                        version=algorithm.version,
                        repeat=repeat_index + 1,
                        order_position=order_position + 1,
                        input_sha256=fixed_input.case.input_sha256,
                        preparation_ns=preparation_finished - preparation_started,
                        query_batch_ns=query_finished - query_started,
                        combined_ns=query_finished - combined_started,
                    )
                )

    return raw_results


def _summarize(
    cases: Sequence[BenchmarkCase],
    raw_results: Sequence[RawTiming],
    *,
    repeats: int,
) -> list[SummaryResult]:
    summary: list[SummaryResult] = []
    for case in cases:
        for algorithm in ALGORITHMS:
            rows = [
                row
                for row in raw_results
                if row.case_id == case.case_id and row.algorithm == algorithm.name
            ]
            summary.append(
                SummaryResult(
                    case_id=case.case_id,
                    array_size=case.array_size,
                    query_count=case.query_count,
                    scenario=case.scenario,
                    algorithm=algorithm.name,
                    version=algorithm.version,
                    repeats=repeats,
                    preparation_median_ms=round(
                        median(row.preparation_ns for row in rows) / 1_000_000,
                        6,
                    ),
                    query_batch_median_ms=round(
                        median(row.query_batch_ns for row in rows) / 1_000_000,
                        6,
                    ),
                    combined_median_ms=round(
                        median(row.combined_ns for row in rows) / 1_000_000,
                        6,
                    ),
                )
            )
    return summary


def run_benchmarks(
    sizes: Sequence[int] = DEFAULT_SIZES,
    query_counts: Sequence[int] = DEFAULT_QUERY_COUNTS,
    *,
    scenarios: Sequence[str] = SCENARIOS,
    repeats: int = DEFAULT_REPEATS,
    base_seed: int = DEFAULT_BASE_SEED,
) -> BenchmarkRun:
    """Generate each case once, then measure all algorithms on that input."""

    fixed_inputs = _build_fixed_inputs(
        sizes,
        query_counts,
        scenarios,
        base_seed=base_seed,
    )
    raw_results = _measure_fixed_inputs(fixed_inputs, repeats=repeats)
    cases = [fixed_input.case for fixed_input in fixed_inputs]
    summary = _summarize(cases, raw_results, repeats=repeats)
    return BenchmarkRun(
        metadata=_metadata(
            sizes=sizes,
            query_counts=query_counts,
            scenarios=scenarios,
            repeats=repeats,
            base_seed=base_seed,
        ),
        cases=cases,
        raw_results=raw_results,
        summary=summary,
    )


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_results(run: BenchmarkRun, output_directory: Path) -> dict[str, Path]:
    """Save full raw timings, summaries, metadata, and the input manifest."""

    output_directory.mkdir(parents=True, exist_ok=True)
    results_json = output_directory / "benchmark_results.json"
    summary_csv = output_directory / "benchmark_results.csv"
    raw_csv = output_directory / "raw_timings.csv"
    input_manifest_json = output_directory / "input_manifest.json"

    case_rows = [asdict(case) for case in run.cases]
    raw_rows = [asdict(result) for result in run.raw_results]
    summary_rows = [asdict(result) for result in run.summary]
    results_json.write_text(
        json.dumps(
            {
                "metadata": run.metadata,
                "cases": case_rows,
                "raw_results": raw_rows,
                "summary": summary_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    input_manifest_json.write_text(
        json.dumps(
            {
                "generator_settings": run.metadata["generator_settings"],
                "cases": case_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        summary_csv,
        summary_rows,
        list(SummaryResult.__dataclass_fields__),
    )
    _write_csv(raw_csv, raw_rows, list(RawTiming.__dataclass_fields__))
    return {
        "results_json": results_json,
        "summary_csv": summary_csv,
        "raw_csv": raw_csv,
        "input_manifest_json": input_manifest_json,
    }


def _parse_integers(raw_values: str) -> list[int]:
    values = [int(value.strip()) for value in raw_values.split(",") if value.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one integer is required")
    if any(value < 0 for value in values):
        raise argparse.ArgumentTypeError("values must be non-negative")
    return values


def _parse_scenarios(raw_scenarios: str) -> list[str]:
    scenarios = [
        value.strip() for value in raw_scenarios.split(",") if value.strip()
    ]
    unknown = set(scenarios) - set(SCENARIOS)
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown scenarios: {sorted(unknown)}")
    return scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        type=_parse_integers,
        default=list(DEFAULT_SIZES),
        help="comma-separated array sizes",
    )
    parser.add_argument(
        "--query-counts",
        type=_parse_integers,
        default=list(DEFAULT_QUERY_COUNTS),
        help="comma-separated query counts",
    )
    parser.add_argument(
        "--scenarios",
        type=_parse_scenarios,
        default=list(SCENARIOS),
        help="comma-separated scenario names",
    )
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED)
    parser.add_argument("--output", type=Path, default=Path("results"))
    arguments = parser.parse_args()

    run = run_benchmarks(
        arguments.sizes,
        arguments.query_counts,
        scenarios=arguments.scenarios,
        repeats=arguments.repeats,
        base_seed=arguments.base_seed,
    )
    artifacts = write_results(run, arguments.output)
    print("Wrote " + ", ".join(str(path) for path in artifacts.values()))


if __name__ == "__main__":
    main()
