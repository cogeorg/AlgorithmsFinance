"""Measure latency by event type and by early/late stream position."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path

from generate_orders import SCENARIOS, events as generate_events
from lob import make_book


FIELDS = [
    "version",
    "scenario",
    "seed",
    "event_count",
    "group",
    "category",
    "sample_count",
    "median_us",
    "p95_us",
    "p99_us",
    "percentile_convention",
]


def nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summary(version, scenario, seed, event_count, group, category, values):
    return {
        "version": version,
        "scenario": scenario,
        "seed": seed,
        "event_count": event_count,
        "group": group,
        "category": category,
        "sample_count": len(values),
        "median_us": f"{statistics.median(values) * 1e6:.3f}",
        "p95_us": f"{nearest_rank(values, 0.95) * 1e6:.3f}",
        "p99_us": f"{nearest_rank(values, 0.99) * 1e6:.3f}",
        "percentile_convention": "nearest rank",
    }


def measure(stream, version, scenario, seed):
    # Warm-up on a separate book so the measured book still begins empty.
    warmup_book = make_book(version)
    for event in stream[: min(1000, len(stream))]:
        warmup_book.process_event(event)

    book = make_book(version)
    by_type = defaultdict(list)
    early: list[float] = []
    late: list[float] = []
    overall: list[float] = []
    edge = max(1, math.ceil(len(stream) * 0.10))

    for index, event in enumerate(stream):
        start = time.perf_counter()
        book.process_event(event)
        elapsed = time.perf_counter() - start
        overall.append(elapsed)
        by_type[event["type"]].append(elapsed)
        if index < edge:
            early.append(elapsed)
        if index >= len(stream) - edge:
            late.append(elapsed)

    rows = [
        summary(book.version, scenario, seed, len(stream), "overall", "all", overall),
        summary(book.version, scenario, seed, len(stream), "position", "early_10pct", early),
        summary(book.version, scenario, seed, len(stream), "position", "late_10pct", late),
    ]
    for event_type in sorted(by_type):
        rows.append(
            summary(
                book.version,
                scenario,
                seed,
                len(stream),
                "event_type",
                event_type,
                by_type[event_type],
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--scenarios", nargs="+", choices=SCENARIOS, default=["mixed", "buildup"]
    )
    parser.add_argument("--versions", nargs="+", choices=("A", "B"), default=["A", "B"])
    parser.add_argument("--levels", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("results/latency_detail.csv"))
    args = parser.parse_args()

    rows = []
    total = len(args.scenarios) * len(args.versions)
    current = 0
    for scenario in args.scenarios:
        stream = list(generate_events(scenario, args.events, args.seed, args.levels))
        for version in args.versions:
            current += 1
            print(f"[{current}/{total}] {version} {scenario}", flush=True)
            rows.extend(measure(stream, version, scenario, args.seed))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)


if __name__ == "__main__":
    main()
