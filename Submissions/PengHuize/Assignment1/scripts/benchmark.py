"""Reproducible runtime, latency, operation-count, and memory experiments."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from generate_orders import SCENARIOS, events as generate_events
from lob import make_book


FIELDS = [
    "version",
    "scenario",
    "seed",
    "event_count",
    "phase",
    "repeat",
    "status",
    "completed_events",
    "elapsed_seconds",
    "throughput_events_per_second",
    "latency_median_us",
    "latency_p95_us",
    "latency_p99_us",
    "active_order_peak",
    "price_level_peak",
    "final_active_orders",
    "final_price_levels",
    "fill_count",
    "makers_touched",
    "price_levels_visited",
    "maker_scans",
    "traced_peak_bytes",
    "notes",
]


def blank_row(**values: Any) -> dict[str, Any]:
    row = {field: "" for field in FIELDS}
    row.update(values)
    return row


def replay_once(stream, version, time_limit=None, *, instrument=False, latency=False):
    book = make_book(version, instrument=instrument)
    start = time.perf_counter()
    per_event: list[float] = []
    completed = 0
    status = "completed"
    for index, event in enumerate(stream, start=1):
        event_start = time.perf_counter() if latency else 0.0
        book.process_event(event)
        if latency:
            per_event.append(time.perf_counter() - event_start)
        completed = index
        if time_limit and index < len(stream) and index % 1000 == 0:
            if time.perf_counter() - start > time_limit:
                status = "stopped_time_limit"
                break
    elapsed = time.perf_counter() - start
    return book, elapsed, completed, status, per_event


def nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def memory_once(stream, version, time_limit=None):
    tracemalloc.start()
    book = make_book(version)
    last_result = None
    completed = 0
    status = "completed"
    start = time.perf_counter()
    for index, event in enumerate(stream, start=1):
        last_result = book.process_event(event)
        completed = index
        if time_limit and index < len(stream) and index % 1000 == 0:
            if time.perf_counter() - start > time_limit:
                status = "stopped_time_limit"
                break
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if last_result is None:
        raise AssertionError("empty benchmark stream")
    return book, current, peak, completed, status


def run_config(args, scenario, count, seed, version):
    stream = list(generate_events(scenario, count, seed, args.levels))
    rows: list[dict[str, Any]] = []

    warmup = stream[: min(1000, len(stream))]
    replay_once(warmup, version)

    elapsed_completed: list[float] = []
    for repeat in range(1, args.repeats + 1):
        book, elapsed, completed, status, _ = replay_once(
            stream, version, args.time_limit
        )
        if status == "completed":
            elapsed_completed.append(elapsed)
        rows.append(
            blank_row(
                version=book.version,
                scenario=scenario,
                seed=seed,
                event_count=count,
                phase="replay",
                repeat=repeat,
                status=status,
                completed_events=completed,
                elapsed_seconds=f"{elapsed:.9f}",
                throughput_events_per_second=(
                    f"{completed / elapsed:.3f}" if elapsed else ""
                ),
                final_active_orders=book.active_order_count(),
                final_price_levels=book.price_level_count(),
                notes=f"time limit {args.time_limit}s" if status != "completed" else "",
            )
        )
        if status != "completed":
            break

    if elapsed_completed:
        median_elapsed = statistics.median(elapsed_completed)
        rows.append(
            blank_row(
                version=make_book(version).version,
                scenario=scenario,
                seed=seed,
                event_count=count,
                phase="replay_median",
                repeat="median",
                status="completed",
                completed_events=count,
                elapsed_seconds=f"{median_elapsed:.9f}",
                throughput_events_per_second=f"{count / median_elapsed:.3f}",
            )
        )

    if not args.skip_latency:
        book, elapsed, completed, status, per_event = replay_once(
            stream,
            version,
            args.time_limit,
            instrument=True,
            latency=True,
        )
        metrics = book.metrics()
        observed = per_event[:completed]
        rows.append(
            blank_row(
                version=book.version,
                scenario=scenario,
                seed=seed,
                event_count=count,
                phase="latency_instrumented",
                repeat=1,
                status=status,
                completed_events=completed,
                elapsed_seconds=f"{elapsed:.9f}",
                latency_median_us=f"{statistics.median(observed) * 1e6:.3f}",
                latency_p95_us=f"{nearest_rank(observed, 0.95) * 1e6:.3f}",
                latency_p99_us=f"{nearest_rank(observed, 0.99) * 1e6:.3f}",
                active_order_peak=metrics["active_order_peak"],
                price_level_peak=metrics["price_level_peak"],
                final_active_orders=metrics["active_orders"],
                final_price_levels=metrics["price_levels"],
                fill_count=metrics["fills"],
                makers_touched=metrics["maker_orders_touched"],
                price_levels_visited=metrics["price_level_visits"],
                maker_scans=metrics["maker_scans"],
                notes="nearest-rank percentiles; instrumentation excluded from primary timing",
            )
        )

    if not args.skip_memory:
        book, current, peak, completed, status = memory_once(
            stream, version, args.time_limit
        )
        rows.append(
            blank_row(
                version=book.version,
                scenario=scenario,
                seed=seed,
                event_count=count,
                phase="memory",
                repeat=1,
                status=status,
                completed_events=completed,
                final_active_orders=book.active_order_count(),
                final_price_levels=book.price_level_count(),
                traced_peak_bytes=peak,
                notes=(
                    "tracemalloc; pre-generated input excluded; live book and current "
                    f"event result included; ending traced bytes={current}"
                ),
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-counts", nargs="+", type=int, default=[1000, 10000, 100000])
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument("--versions", nargs="+", choices=("A", "B"), default=["A", "B"])
    parser.add_argument("--levels", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--skip-latency", action="store_true")
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/raw_results.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("results/environment.json"))
    args = parser.parse_args()

    if any(count < 1 for count in args.event_counts) or args.repeats < 1:
        parser.error("event counts and repeats must be positive")

    all_rows: list[dict[str, Any]] = []
    total = len(args.scenarios) * len(args.event_counts) * len(args.seeds) * len(args.versions)
    current = 0
    for scenario in args.scenarios:
        for count in args.event_counts:
            for seed in args.seeds:
                for version in args.versions:
                    current += 1
                    print(f"[{current}/{total}] {version} {scenario} M={count} seed={seed}", flush=True)
                    all_rows.extend(run_config(args, scenario, count, seed, version))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    generator_path = Path("generate_orders.py")
    metadata = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "standard_library_only": True,
        "generator_sha256": hashlib.sha256(generator_path.read_bytes()).hexdigest(),
        "settings": {
            "scenarios": args.scenarios,
            "event_counts": args.event_counts,
            "seeds": args.seeds,
            "versions": args.versions,
            "levels": args.levels,
            "repeats": args.repeats,
            "time_limit_seconds": args.time_limit,
            "input_generation_inside_timing": False,
            "percentile_convention": "nearest rank",
        },
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
