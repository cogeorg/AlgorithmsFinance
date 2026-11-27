"""Deterministic measurement arithmetic and fresh-state replay helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from math import ceil
from statistics import median
from time import perf_counter, perf_counter_ns
from typing import TypeVar

from .interface import Event, OrderBook


Number = TypeVar("Number", int, float)
Clock = Callable[[], float]
NanosecondClock = Callable[[], int]
BookFactory = Callable[[], OrderBook]
ThroughputRecord = dict[str, int | float]
LatencyRecord = dict[str, int | str]


def nearest_rank_percentile(
    samples: Sequence[Number], percentile: float
) -> Number:
    """Return a percentile using the documented one-based nearest-rank rule."""

    if not samples:
        raise ValueError("percentile requires at least one sample")
    if isinstance(percentile, bool) or not 0 < percentile <= 100:
        raise ValueError("percentile must be greater than 0 and at most 100")
    ordered = sorted(samples)
    rank = ceil(percentile / 100 * len(ordered))
    return ordered[rank - 1]


def latency_summary_ns(samples: Sequence[int]) -> dict[str, int | float]:
    """Summarize raw processing-latency samples expressed in nanoseconds."""

    if not samples:
        raise ValueError("latency summary requires at least one sample")
    invalid = any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in samples
    )
    if invalid:
        raise ValueError("latency samples must be nonnegative integers")
    return {
        "sample_count": len(samples),
        "median_ns": median(samples),
        "p95_ns": nearest_rank_percentile(samples, 95),
        "p99_ns": nearest_rank_percentile(samples, 99),
    }


def throughput_events_per_second(event_count: int, elapsed_seconds: float) -> float:
    """Calculate processed events per replay second."""

    if isinstance(event_count, bool) or not isinstance(event_count, int) or event_count <= 0:
        raise ValueError("event_count must be a positive integer")
    if isinstance(elapsed_seconds, bool) or elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be positive")
    return event_count / elapsed_seconds


def measure_throughput_repeats(
    book_factory: BookFactory,
    events: Sequence[Event],
    *,
    warmups: int = 1,
    repeats: int = 5,
    clock: Clock = perf_counter,
) -> list[ThroughputRecord]:
    """Replay preloaded events with a fresh book for every warm-up and repeat."""

    if isinstance(warmups, bool) or not isinstance(warmups, int) or warmups < 0:
        raise ValueError("warmups must be a nonnegative integer")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats <= 0:
        raise ValueError("repeats must be a positive integer")
    if not events:
        raise ValueError("events must not be empty")

    for _ in range(warmups):
        book = book_factory()
        for event in events:
            book.process_event(event)

    records: list[ThroughputRecord] = []
    event_count = len(events)
    for repeat in range(1, repeats + 1):
        construction_started = clock()
        book = book_factory()
        construction_seconds = clock() - construction_started

        replay_started = clock()
        for event in events:
            book.process_event(event)
        replay_seconds = clock() - replay_started

        if construction_seconds < 0:
            raise ValueError("clock produced negative construction time")
        throughput = throughput_events_per_second(event_count, replay_seconds)
        records.append(
            {
                "repeat": repeat,
                "event_count": event_count,
                "construction_seconds": construction_seconds,
                "replay_seconds": replay_seconds,
                "total_engine_seconds": construction_seconds + replay_seconds,
                "throughput_events_per_second": throughput,
            }
        )
    return records


def measure_event_latencies(
    book_factory: BookFactory,
    events: Sequence[Event],
    *,
    warmups: int = 1,
    repeats: int = 5,
    clock_ns: NanosecondClock = perf_counter_ns,
) -> list[LatencyRecord]:
    """Warm up separately, then time repeated replays on fresh books."""

    if isinstance(warmups, bool) or not isinstance(warmups, int) or warmups < 0:
        raise ValueError("warmups must be a nonnegative integer")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats <= 0:
        raise ValueError("repeats must be a positive integer")
    if not events:
        raise ValueError("events must not be empty")
    for event in events:
        event_type = event.get("type")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("every measured event must have a nonempty type")

    for _ in range(warmups):
        warmup_book = book_factory()
        for event in events:
            warmup_book.process_event(event)

    records: list[LatencyRecord] = []
    for repeat in range(1, repeats + 1):
        book = book_factory()
        for event_index, event in enumerate(events, start=1):
            event_type = event["type"]
            started = clock_ns()
            book.process_event(event)
            latency_ns = clock_ns() - started
            if latency_ns < 0:
                raise ValueError("clock produced negative event latency")
            records.append(
                {
                    "repeat": repeat,
                    "event_index": event_index,
                    "event_type": event_type,
                    "latency_ns": latency_ns,
                }
            )
    return records


def latency_breakdown_ns(
    records: Sequence[LatencyRecord],
) -> dict[str, object]:
    """Summarize repeated latency records and within-repeat edge windows."""

    if not records:
        raise ValueError("latency breakdown requires at least one record")
    by_repeat: dict[int, list[LatencyRecord]] = {}
    by_event_type: dict[str, list[int]] = {}
    for record in records:
        repeat = record.get("repeat")
        event_index = record.get("event_index")
        event_type = record.get("event_type")
        latency_ns = record.get("latency_ns")
        if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat <= 0:
            raise ValueError("latency record has invalid repeat")
        if (
            isinstance(event_index, bool)
            or not isinstance(event_index, int)
            or event_index <= 0
        ):
            raise ValueError("latency record has invalid event_index")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("latency record has invalid event_type")
        if (
            isinstance(latency_ns, bool)
            or not isinstance(latency_ns, int)
            or latency_ns < 0
        ):
            raise ValueError("latency record has invalid latency_ns")
        by_repeat.setdefault(repeat, []).append(record)
        by_event_type.setdefault(event_type, []).append(latency_ns)

    repeat_numbers = sorted(by_repeat)
    if repeat_numbers != list(range(1, len(repeat_numbers) + 1)):
        raise ValueError("latency repeats must be consecutive from one")

    ordered_repeats: list[list[LatencyRecord]] = []
    event_counts: set[int] = set()
    for repeat in repeat_numbers:
        ordered = sorted(
            by_repeat[repeat], key=lambda record: int(record["event_index"])
        )
        indices = [int(record["event_index"]) for record in ordered]
        if indices != list(range(1, len(ordered) + 1)):
            raise ValueError("event indices must be consecutive within each repeat")
        ordered_repeats.append(ordered)
        event_counts.add(len(ordered))
    if len(event_counts) != 1:
        raise ValueError("latency repeats must contain the same event count")

    event_count = event_counts.pop()
    window_size = max(1, ceil(0.10 * event_count))
    all_samples = [
        int(record["latency_ns"])
        for ordered in ordered_repeats
        for record in ordered
    ]
    early_samples = [
        int(record["latency_ns"])
        for ordered in ordered_repeats
        for record in ordered[:window_size]
    ]
    late_samples = [
        int(record["latency_ns"])
        for ordered in ordered_repeats
        for record in ordered[-window_size:]
    ]
    return {
        "overall": latency_summary_ns(all_samples),
        "by_event_type": {
            event_type: latency_summary_ns(by_event_type[event_type])
            for event_type in sorted(by_event_type)
        },
        "early_10_percent": latency_summary_ns(early_samples),
        "late_10_percent": latency_summary_ns(late_samples),
        "repeat_count": len(ordered_repeats),
        "window_size_per_repeat": window_size,
    }
