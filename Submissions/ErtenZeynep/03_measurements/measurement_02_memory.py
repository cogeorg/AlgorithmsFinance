"""Separate tracemalloc measurements for mandatory search configurations."""

from __future__ import annotations

import argparse
import csv
import gc
from pathlib import Path
import platform
import sys
import tracemalloc
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "01_source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from algorithms_finance.data_01_generation import (  # noqa: E402
    generate_case,
    mandatory_configurations,
)
from measurement_01_benchmarks import (  # noqa: E402
    BENCHMARK_VERSION,
    _code_version,
    algorithm_specs,
)


MEMORY_MEASUREMENT_VERSION = "1.0.0"


def run_memory_measurements() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    code_version = _code_version()

    for config in mandatory_configurations():
        case = generate_case(config)
        expected = [query in set(case.array) for query in case.queries]
        original_array = case.array.copy()

        for spec in algorithm_specs():
            gc.collect()
            tracemalloc.start()
            try:
                prepared = spec.prepare(case.array)
                output = spec.query(prepared, case.queries)
                current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

            if output != expected:
                raise AssertionError(
                    f"incorrect output during memory measurement: {spec.method}"
                )
            if case.array != original_array:
                raise AssertionError(
                    f"input mutation during memory measurement: {spec.method}"
                )

            metadata = case.metadata
            rows.append(
                {
                    "case_id": metadata["case_id"],
                    "dataset_class": metadata["dataset_class"],
                    "method": spec.method,
                    "algorithm_version": spec.version,
                    "array_size": metadata["array_size"],
                    "query_count": metadata["query_count"],
                    "scenario": metadata["scenario"],
                    "actual_hit_rate": metadata["actual_hit_rate"],
                    "duplicate_policy": metadata["duplicate_policy"],
                    "array_seed": metadata["array_seed"],
                    "query_seed": metadata["query_seed"],
                    "current_traced_bytes": current_bytes,
                    "peak_traced_bytes": peak_bytes,
                    "returned_output_length": len(output),
                    "input_allocated_before_tracing": True,
                    "preparation_included": True,
                    "prepared_structure_alive_at_read": True,
                    "output_alive_at_read": True,
                    "measurement_unit": "bytes",
                    "python_version": platform.python_version(),
                    "platform": platform.platform(),
                    "code_version": code_version,
                    "benchmark_version": BENCHMARK_VERSION,
                    "memory_measurement_version": MEMORY_MEASUREMENT_VERSION,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            PROJECT_ROOT
            / "04_results"
            / "memory"
            / "result_01_memory_measurements.csv"
        ),
    )
    args = parser.parse_args()

    rows = run_memory_measurements()
    write_csv(args.output, rows)
    print(f"Saved {len(rows)} memory rows to {args.output}")


if __name__ == "__main__":
    main()
