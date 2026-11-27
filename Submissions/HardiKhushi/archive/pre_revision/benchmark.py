"""Measure complete query batches and save CSVs in this folder's results/."""

import argparse
import csv
import platform
import statistics
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

from dashboard import generate_dashboard
from data_generator import DUPLICATE_POLICIES, SCENARIOS, generate_workload
from search import SEARCH_METHODS


HERE = Path(__file__).resolve().parent


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=positive_int,
                        default=[1000, 5000, 10000])
    parser.add_argument("--queries", type=positive_int, default=200)
    parser.add_argument("--repeats", type=positive_int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", choices=SCENARIOS, default="mixed")
    parser.add_argument("--duplicate-policy", choices=DUPLICATE_POLICIES, default="unique")
    args = parser.parse_args()
    timing_rows, memory_rows = [], []
    measured_utc = datetime.now(timezone.utc).isoformat()
    for n in sorted(set(args.sizes)):
        workload = generate_workload(n, args.queries, seed=args.seed,
                                     scenario=args.scenario,
                                     duplicate_policy=args.duplicate_policy)
        ids, queries, expected = workload.ids, workload.queries, workload.expected
        for name, method in SEARCH_METHODS.items():
            assert method(ids, queries) == expected  # Untimed check and warm-up.
            times = []
            for _ in range(args.repeats):
                start = perf_counter_ns()
                result = method(ids, queries)
                elapsed_ms = (perf_counter_ns() - start) / 1_000_000
                assert result == expected
                del result
                times.append(elapsed_ms)
            peaks = []
            # Allocation tracing runs separately so it does not distort timing.
            for _ in range(args.repeats):
                tracemalloc.start()
                try:
                    result = method(ids, queries)
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                assert result == expected
                del result
                peaks.append(peak)
            common = {
                "algorithm": name, **workload.settings, "repeats": args.repeats,
                "measured_utc": measured_utc, "python": platform.python_version(),
                "platform": platform.platform(),
            }
            timing_rows.append({**common, "median_ms": statistics.median(times),
                                "min_ms": min(times), "max_ms": max(times)})
            memory_rows.append({**common,
                                "median_peak_bytes": statistics.median(peaks),
                                "min_peak_bytes": min(peaks),
                                "max_peak_bytes": max(peaks)})
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    write_csv(results / "timing.csv", timing_rows)
    write_csv(results / "memory.csv", memory_rows)
    generate_dashboard(HERE)
    print(f"Saved {len(timing_rows)} measurements per CSV in {results}; dashboard.html in {HERE}")


if __name__ == "__main__":
    main()
