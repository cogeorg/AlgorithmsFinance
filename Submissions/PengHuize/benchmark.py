"""Reproducible timing and memory measurements for membership algorithms."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable, Dict, List, Sequence

from algorithms import (
    prepare_binary,
    prepare_hash,
    prepare_linear,
    query_binary_iterative,
    query_binary_recursive,
    query_hash,
    query_linear,
)
from synthetic_data import generate_synthetic_data


ARRAY_SIZES = (1_000, 10_000, 100_000)
QUERY_COUNTS = (1, 100)
SCENARIOS = {
    "all_present": 1.0,
    "all_absent": 0.0,
    "mixed": 0.5,
}
BASE_SEED = 20_261_120
ALLOW_DUPLICATES = True
DEFAULT_REPEATS = 5
UNIT = "seconds_per_complete_query_batch"


@dataclass(frozen=True)
class MethodSpec:
    """Preparation and query functions for one measured method/version."""

    method: str
    version: str
    prepare: Callable[[Sequence[int]], Any]
    query: Callable[[Any, Sequence[int]], List[bool]]


METHODS = (
    MethodSpec("linear", "current", prepare_linear, query_linear),
    MethodSpec("binary", "original_recursive", prepare_binary, query_binary_recursive),
    MethodSpec("binary", "revised_iterative", prepare_binary, query_binary_iterative),
    MethodSpec("hash_set", "current", prepare_hash, query_hash),
)


def _calibrate(operation: Callable[[], Any], target_seconds: float = 0.01) -> int:
    """Choose repetitions for short calls and return a capped loop count."""
    start = time.perf_counter()
    operation()
    elapsed = time.perf_counter() - start
    if elapsed <= 0.0:
        return 1_000
    return max(1, min(1_000, int(target_seconds / elapsed)))


def _time_repeated(operation: Callable[[], Any], loops: int) -> float:
    """Return elapsed seconds per complete operation batch."""
    result = None
    start = time.perf_counter()
    for _ in range(loops):
        result = operation()
    elapsed = time.perf_counter() - start
    if result is None:
        raise RuntimeError("timed operation unexpectedly returned None")
    return elapsed / loops


def measure_timings(
    spec: MethodSpec,
    ids: Sequence[int],
    queries: Sequence[int],
    repeats: int,
) -> Dict[str, Any]:
    """Warm up, then measure fresh preparation, queries, and total time."""
    warm_prepared = spec.prepare(ids)
    warm_output = spec.query(warm_prepared, queries)
    if len(warm_output) != len(queries):
        raise AssertionError("warm-up returned the wrong result length")

    prep_loops = _calibrate(lambda: spec.prepare(ids))
    query_prepared = spec.prepare(ids)
    query_loops = _calibrate(lambda: spec.query(query_prepared, queries))
    total_loops = _calibrate(lambda: spec.query(spec.prepare(ids), queries))

    prep_repeats = []
    query_repeats = []
    total_repeats = []

    for _ in range(repeats):
        prep_repeats.append(
            _time_repeated(lambda: spec.prepare(ids), prep_loops)
        )

        # Fresh preparation state is created for every recorded query repeat.
        prepared = spec.prepare(ids)
        query_repeats.append(
            _time_repeated(lambda: spec.query(prepared, queries), query_loops)
        )

        # Each inner total-time call creates its own fresh preparation state.
        total_repeats.append(
            _time_repeated(
                lambda: spec.query(spec.prepare(ids), queries), total_loops
            )
        )

    return {
        "preparation": prep_repeats,
        "query_batch": query_repeats,
        "total": total_repeats,
        "loops": {
            "preparation": prep_loops,
            "query_batch": query_loops,
            "total": total_loops,
        },
    }


def measure_memory(
    spec: MethodSpec, ids: Sequence[int], queries: Sequence[int]
) -> Dict[str, int]:
    """Measure Python allocations for preparation plus the returned output."""
    tracemalloc.start()
    try:
        prepared = spec.prepare(ids)
        output = spec.query(prepared, queries)
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        if len(output) != len(queries):
            raise AssertionError("memory run returned the wrong result length")
    finally:
        tracemalloc.stop()
    return {"current_bytes": current_bytes, "peak_bytes": peak_bytes}


def _git_value(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _source_hash(project_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in ("algorithms.py", "synthetic_data.py", "benchmark.py"):
        digest.update(name.encode("utf-8"))
        digest.update((project_dir / name).read_bytes())
    return digest.hexdigest()


def collect_environment(project_dir: Path, run_id: str) -> Dict[str, Any]:
    repo_root = project_dir.parents[1]
    dirty_output = _git_value(
        repo_root, "status", "--porcelain", "--", "Submissions/PengHuize"
    )
    return {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unavailable",
        "git_commit": _git_value(repo_root, "rev-parse", "HEAD"),
        "git_dirty_for_submission": bool(dirty_output),
        "source_sha256": _source_hash(project_dir),
        "timing_unit": UNIT,
        "timing_clock": "time.perf_counter",
        "warm_up": True,
        "repeat_count": DEFAULT_REPEATS,
        "memory_tool": "tracemalloc",
        "memory_scope": (
            "Input and queries are built before tracing. Preparation structures "
            "and returned output remain alive when current and peak bytes are read."
        ),
    }


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty result table")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_benchmarks(output_dir: Path, repeats: int, quick: bool) -> None:
    """Run fixed-input experiments and save raw, summary, and environment data."""
    project_dir = Path(__file__).resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    array_sizes = (1_000,) if quick else ARRAY_SIZES

    raw_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for n_index, n in enumerate(array_sizes):
        for q_index, q in enumerate(QUERY_COUNTS):
            for scenario_index, (scenario, hit_rate) in enumerate(SCENARIOS.items()):
                seed = BASE_SEED + n_index * 100 + q_index * 10 + scenario_index
                ids, queries = generate_synthetic_data(
                    num_ids=n,
                    num_queries=q,
                    hit_rate=hit_rate,
                    seed=seed,
                    allow_duplicates=ALLOW_DUPLICATES,
                )
                expected = [query in set(ids) for query in queries]

                for spec in METHODS:
                    prepared = spec.prepare(ids)
                    actual = spec.query(prepared, queries)
                    if actual != expected:
                        raise AssertionError(
                            f"incorrect results for {spec.method}/{spec.version}"
                        )

                    timings = measure_timings(spec, ids, queries, repeats)
                    memory = measure_memory(spec, ids, queries)

                    common = {
                        "run_id": run_id,
                        "method": spec.method,
                        "version": spec.version,
                        "n": n,
                        "q": q,
                        "scenario": scenario,
                        "seed": seed,
                        "hit_rate": hit_rate,
                        "allow_duplicates": ALLOW_DUPLICATES,
                    }

                    for metric in ("preparation", "query_batch", "total"):
                        for repeat_index, seconds in enumerate(timings[metric], start=1):
                            raw_rows.append(
                                {
                                    **common,
                                    "metric": metric,
                                    "repeat": repeat_index,
                                    "seconds": seconds,
                                    "inner_loops": timings["loops"][metric],
                                    "unit": UNIT,
                                }
                            )

                    summary_rows.append(
                        {
                            **common,
                            "preparation_median_seconds": median(
                                timings["preparation"]
                            ),
                            "query_batch_median_seconds": median(
                                timings["query_batch"]
                            ),
                            "total_median_seconds": median(timings["total"]),
                            "memory_current_bytes": memory["current_bytes"],
                            "memory_peak_bytes": memory["peak_bytes"],
                            "repeat_count": repeats,
                            "timing_unit": UNIT,
                        }
                    )
                    print(
                        f"measured n={n} q={q} {scenario} "
                        f"{spec.method}/{spec.version}"
                    )

    _write_csv(output_dir / "raw_timings.csv", raw_rows)
    _write_csv(output_dir / "summary.csv", summary_rows)
    environment = collect_environment(project_dir, run_id)
    environment["repeat_count"] = repeats
    environment["quick_run"] = quick
    environment["array_sizes"] = list(array_sizes)
    environment["query_counts"] = list(QUERY_COUNTS)
    environment["scenarios"] = SCENARIOS
    environment["base_seed"] = BASE_SEED
    environment["allow_duplicates"] = ALLOW_DUPLICATES
    (output_dir / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"saved results to {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use n=1,000 only for a fast smoke run.",
    )
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    run_benchmarks(arguments.output_dir, arguments.repeats, arguments.quick)
