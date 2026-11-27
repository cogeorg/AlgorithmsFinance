"""Separate tracemalloc replay with explicit memory inclusion boundaries."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tracemalloc
from typing import Any

from .benchmarking import (
    book_factory,
    environment_metadata,
    load_event_batch,
    write_json_exclusive,
)
from .interface import Event, OrderBook


BookFactory = Callable[[], OrderBook]
TraceStart = Callable[[], None]
TraceGet = Callable[[], tuple[int, int]]
TraceStop = Callable[[], None]


def measurement_checkpoint_indices(
    event_count: int, *, checkpoint_count: int = 10
) -> tuple[int, ...]:
    """Return deterministic replay positions for memory-growth samples."""

    if isinstance(event_count, bool) or not isinstance(event_count, int) or event_count <= 0:
        raise ValueError("event_count must be a positive integer")
    if (
        isinstance(checkpoint_count, bool)
        or not isinstance(checkpoint_count, int)
        or checkpoint_count <= 0
    ):
        raise ValueError("checkpoint_count must be a positive integer")
    if event_count == 1 or checkpoint_count == 1:
        return (event_count,)
    if checkpoint_count >= event_count:
        return tuple(range(1, event_count + 1))

    positions = {
        1 + round(index * (event_count - 1) / (checkpoint_count - 1))
        for index in range(checkpoint_count)
    }
    return tuple(sorted(positions))


def measure_memory_replay(
    book_factory: BookFactory,
    events: Sequence[Event],
    *,
    mode: str,
    checkpoint_count: int = 10,
    trace_start: TraceStart | None = None,
    trace_get: TraceGet | None = None,
    trace_stop: TraceStop | None = None,
) -> dict[str, Any]:
    """Measure one replay under an explicit memory inclusion mode."""

    if not events:
        raise ValueError("events must not be empty")
    if mode not in {"memory_state", "memory_retained_output"}:
        raise ValueError("unknown memory mode")
    checkpoints = measurement_checkpoint_indices(
        len(events), checkpoint_count=checkpoint_count
    )
    supplied_trace_functions = (trace_start, trace_get, trace_stop)
    if any(function is not None for function in supplied_trace_functions) and not all(
        function is not None for function in supplied_trace_functions
    ):
        raise ValueError("provide all trace functions or none")

    start = trace_start or tracemalloc.start
    get_memory = trace_get or tracemalloc.get_traced_memory
    stop = trace_stop or tracemalloc.stop
    checkpoint_set = set(checkpoints)
    samples: list[dict[str, int]] = []
    retained_results: list[dict[str, object]] | None = None
    current_result: dict[str, object] | None = None
    book: OrderBook | None = None

    start()
    try:
        book = book_factory()
        if mode == "memory_retained_output":
            retained_results = []
        for event_index, event in enumerate(events, start=1):
            current_result = book.process_event(event)
            if retained_results is not None:
                retained_results.append(current_result)
            if event_index in checkpoint_set:
                current_bytes, peak_bytes = get_memory()
                if current_bytes < 0 or peak_bytes < current_bytes:
                    raise ValueError("tracer returned invalid memory values")
                samples.append(
                    {
                        "event_index": event_index,
                        "current_bytes": current_bytes,
                        "peak_bytes": peak_bytes,
                    }
                )
    finally:
        stop()

    assert book is not None
    assert current_result is not None
    final_sample = samples[-1]
    snapshot = book.inspect_book()
    occupied_levels = {
        (order["side"], order["price_ticks"])
        for order in snapshot
    }
    return {
        "mode": mode,
        "event_count": len(events),
        "checkpoints": samples,
        "final": {
            "current_bytes": final_sample["current_bytes"],
            "peak_bytes": final_sample["peak_bytes"],
            "active_orders": len(snapshot),
            "occupied_price_levels": len(occupied_levels),
            "retained_output_count": (
                len(retained_results) if retained_results is not None else 0
            ),
        },
        "inclusions": {
            "preloaded_input": False,
            "book_construction": True,
            "live_book_state": True,
            "temporary_matching_allocations": True,
            "current_event_result": True,
            "complete_result_history": mode == "memory_retained_output",
            "checkpoint_bookkeeping": True,
            "final_book_inspection": False,
            "python_tracemalloc_only": True,
        },
    }


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("baseline", "revised"), required=True)
    parser.add_argument(
        "--mode",
        choices=("memory_state", "memory_retained_output"),
        required=True,
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--max-events", type=_positive_integer)
    parser.add_argument("--checkpoints", type=_positive_integer, default=10)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    try:
        events, input_metadata = load_event_batch(
            args.input,
            max_events=args.max_events,
        )
        measurement = measure_memory_replay(
            book_factory(args.version),
            events,
            mode=args.mode,
            checkpoint_count=args.checkpoints,
        )
        document: dict[str, object] = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "phase": args.mode,
            "version": args.version,
            "command": [sys.executable, *sys.argv],
            "environment": environment_metadata(),
            "input": input_metadata,
            "settings": {"checkpoint_count": args.checkpoints},
            "measurement": measurement,
        }
        write_json_exclusive(args.out, document)
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "output": str(args.out),
                "final": document["measurement"]["final"],
            }
        )
    )
    return 0
