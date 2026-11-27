"""Time preparation and query batches on the 18 saved Lab 1 inputs."""

import csv
import json
import platform
import statistics
import subprocess
from pathlib import Path
from time import perf_counter

from search import (
    _binary_queries_v1, _binary_queries_v2, _hash_queries, _linear_queries,
    binary_search_v1, binary_search_v2, hash_search_v1, linear_search_v1,
)


HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"
METHODS = (
    ("linear", "v1", linear_search_v1, lambda ids: ids, _linear_queries),
    ("binary", "v1", binary_search_v1, sorted, _binary_queries_v1),
    ("binary", "v2", binary_search_v2, sorted, _binary_queries_v2),
    ("hash", "v1", hash_search_v1, set, _hash_queries),
)
FIELDS = (
    "row_type", "repeat", "algorithm", "version", "n", "q", "scenario",
    "requested_hit_rate", "actual_hit_rate", "seed", "allow_duplicates",
    "query_batches", "preparation_seconds", "query_seconds", "total_seconds",
    "units", "python_version", "platform", "machine", "processor", "git_commit",
)


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def query_batches(algorithm, q):
    """Repeat short batches so clock overhead is less important."""
    if algorithm == "linear":
        return 100 if q == 1 else 1
    if algorithm == "binary":
        return 1000 if q == 1 else 100
    return 10000 if q == 1 else 1000


def main():
    environment = {
        "units": "seconds",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "git_commit": git_commit(),
    }
    rows = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        ids, queries = data["ids"], data["queries"]
        if len(ids) != data["n"] or len(queries) != data["q"]:
            raise ValueError(f"Wrong input length in {path.name}")
        original_ids, original_queries = ids.copy(), queries.copy()
        expected = linear_search_v1(ids, queries)
        for algorithm, version, public, prepare, search_queries in METHODS:
            # This correctness call also warms up the public implementation.
            if public(ids, queries) != expected:
                raise AssertionError(f"Wrong answers: {algorithm} {version}, {path.name}")
            batches = query_batches(algorithm, data["q"])
            common = {
                "algorithm": algorithm, "version": version,
                "n": data["n"], "q": data["q"], "scenario": data["scenario"],
                "requested_hit_rate": data["requested_hit_rate"],
                "actual_hit_rate": data["actual_hit_rate"],
                "seed": data["seed"],
                "allow_duplicates": data["allow_duplicates"],
                "query_batches": batches,
                **environment,
            }
            repeats = []
            for repeat in range(1, 6):
                # A new sorted list or set is made on every repetition.
                if algorithm == "linear":
                    prepared = ids
                    preparation_seconds = 0.0
                else:
                    start = perf_counter()
                    prepared = prepare(ids)
                    preparation_seconds = perf_counter() - start

                start = perf_counter()
                for _ in range(batches):
                    result = search_queries(prepared, queries)
                query_seconds = (perf_counter() - start) / batches
                total_seconds = preparation_seconds + query_seconds
                if result != expected or min(preparation_seconds, query_seconds, total_seconds) < 0:
                    raise AssertionError(f"Invalid measurement: {path.name}")
                measurement = {
                    "preparation_seconds": preparation_seconds,
                    "query_seconds": query_seconds,
                    "total_seconds": total_seconds,
                }
                repeats.append(measurement)
                rows.append({"row_type": "raw", "repeat": repeat,
                             **common, **measurement})

            medians = {key: statistics.median(row[key] for row in repeats)
                       for key in ("preparation_seconds", "query_seconds",
                                   "total_seconds")}
            rows.append({"row_type": "median", "repeat": "", **common, **medians})
        if ids != original_ids or queries != original_queries:
            raise AssertionError(f"Saved input changed: {path.name}")

    if len(list(DATA_DIR.glob("*.json"))) != 18:
        raise ValueError("Expected exactly 18 fixed datasets")
    RESULTS_DIR.mkdir(exist_ok=True)
    output = RESULTS_DIR / "timings.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    if not output.is_file() or output.stat().st_size == 0:
        raise AssertionError("Timing CSV was not created")
    print(f"Saved {len(rows)} rows from 18 datasets to {output}")


if __name__ == "__main__":
    main()
