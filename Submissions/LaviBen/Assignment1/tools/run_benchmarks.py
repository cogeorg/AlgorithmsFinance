#!/usr/bin/env python3
"""Run reproducible timing, latency, diagnostics, and memory experiments."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import gc
from pathlib import Path
import statistics
import sys
from time import perf_counter
import tracemalloc
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from measurement.datasets import (  # noqa: E402
    liquidation_request,
    load_dataset,
    read_events,
)
from measurement.metrics import (  # noqa: E402
    MeasurementTimeout,
    environment_metadata,
    latency_replay,
    replay_diagnostics,
    time_limit,
    timed_replay,
    traced_memory_replay,
    validate_report,
    write_report,
)
from orderbook.baseline import BaselineOrderBook  # noqa: E402
from orderbook.revised import RevisedOrderBook  # noqa: E402


IMPLEMENTATIONS = {
    "baseline": BaselineOrderBook,
    "revised": RevisedOrderBook,
}
MEASUREMENT_INTEGRITY_REVISION = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "canonical"), default="smoke")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "generated" / "benchmark",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "tmp" / "benchmark_smoke.json.gz",
    )
    parser.add_argument("--versions", nargs="+", choices=tuple(IMPLEMENTATIONS))
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--parse-repeats", type=int)
    parser.add_argument("--warmup-events", type=int)
    parser.add_argument("--diagnostic-events", type=int, default=1_000)
    parser.add_argument("--latency-events", type=int)
    parser.add_argument("--time-limit-seconds", type=float, default=120.0)
    parser.add_argument("--skip-memory", action="store_true")
    return parser.parse_args()


def common_fields(metadata: Mapping[str, object]) -> dict[str, object]:
    return {
        "dataset_id": metadata["dataset_id"],
        "experiment": metadata["experiment"],
        "scenario": metadata["scenario"],
        "seed": metadata["seed"],
        "event_count": metadata["event_count"],
        "levels": metadata["levels"],
        "event_sha256": metadata["event_sha256"],
    }


def append_timing_summary(
    records: list[dict[str, object]],
    raw_records: Sequence[Mapping[str, object]],
    base: Mapping[str, object],
    phase: str,
    version: str,
    expected_repeat_count: int | None = None,
) -> None:
    if expected_repeat_count is None:
        expected_repeat_count = len(raw_records)
    if expected_repeat_count < len(raw_records):
        raise ValueError("expected repeat count cannot be smaller than raw records")
    completed = [
        float(record["elapsed_seconds"])
        for record in raw_records
        if not record["stopped"]
    ]
    stopped_count = len(raw_records) - len(completed)
    missing_count = expected_repeat_count - len(raw_records)
    if completed:
        median_elapsed = statistics.median(completed)
        completed_throughputs = [
            float(record["throughput_events_per_second"])
            for record in raw_records
            if not record["stopped"] and "throughput_events_per_second" in record
        ]
        summary: dict[str, object] = {
            **base,
            "measurement_kind": "timing_summary",
            "phase": phase,
            "version": version,
            "repeat": None,
            "elapsed_seconds_median": median_elapsed,
            "time_unit": "seconds",
            "expected_repeat_count": expected_repeat_count,
            "completed_repeat_count": len(completed),
            "stopped_repeat_count": stopped_count,
            "missing_repeat_count": missing_count,
            "completion_status": (
                "partial" if stopped_count or missing_count else "complete"
            ),
            "stopped": False,
        }
        if completed_throughputs:
            summary["throughput_events_per_second_median"] = statistics.median(
                completed_throughputs
            )
        records.append(
            summary
        )
    else:
        records.append(
            {
                **base,
                "measurement_kind": "timing_summary",
                "phase": phase,
                "version": version,
                "repeat": None,
                "expected_repeat_count": expected_repeat_count,
                "completed_repeat_count": 0,
                "stopped_repeat_count": stopped_count,
                "missing_repeat_count": missing_count,
                "completion_status": (
                    "partial"
                    if stopped_count and missing_count
                    else "stopped"
                    if stopped_count
                    else "missing"
                ),
                "stopped": not missing_count,
                "time_unit": "seconds",
                **(
                    {"stop_reason": "all raw repeats stopped at the declared limit"}
                    if not missing_count
                    else {}
                ),
            }
        )


def compare_versions(
    events: Sequence[Mapping[str, object]],
    time_limit_seconds: float | None = None,
) -> dict[str, object]:
    books = {name: cls() for name, cls in IMPLEMENTATIONS.items()}
    compared = 0
    try:
        with time_limit(time_limit_seconds):
            for index, event in enumerate(events, 1):
                before = deepcopy(event)
                results = {name: book.ProcessEvent(event) for name, book in books.items()}
                if event != before:
                    raise AssertionError(f"input mutation at diagnostic event {index}")
                if results["baseline"] != results["revised"]:
                    raise AssertionError(f"result disagreement at diagnostic event {index}")
                states = {name: book.InspectBook() for name, book in books.items()}
                if states["baseline"] != states["revised"]:
                    raise AssertionError(
                        f"canonical-book disagreement at diagnostic event {index}"
                    )
                compared = index
    except MeasurementTimeout as error:
        return {
            "events_requested": len(events),
            "events_compared": compared,
            "stopped": True,
            "stop_reason": str(error),
        }
    return {
        "events_requested": len(events),
        "events_compared": compared,
        "ordered_results_equal": True,
        "final_books_equal": True,
        "input_unchanged": True,
        "stopped": False,
    }


def warm_up(book_class: type[Any], events: Sequence[Mapping[str, object]]) -> None:
    book = book_class()
    for event in events:
        book.ProcessEvent(event)


def parse_measurements(
    path: Path,
    metadata: Mapping[str, object],
    repeats: int,
) -> list[dict[str, object]]:
    base = common_fields(metadata)
    records: list[dict[str, object]] = []
    raw: list[dict[str, object]] = []
    for repeat in range(repeats):
        started = perf_counter()
        parsed = read_events(path)
        elapsed = perf_counter() - started
        if len(parsed) != metadata["event_count"]:
            raise AssertionError("parse repeat changed event count")
        record = {
            **base,
            "measurement_kind": "timing",
            "phase": "input_read_parse",
            "version": "shared",
            "repeat": repeat,
            "elapsed_seconds": elapsed,
            "time_unit": "seconds",
            "events_processed": len(parsed),
            "throughput_events_per_second": len(parsed) / elapsed,
            "attempted": True,
            "stopped": False,
        }
        raw.append(record)
        records.append(record)
        # Release this repeat's parsed objects after the clock read and before
        # the next clock starts. Otherwise reassignment charges prior cleanup
        # to the following parse repeat.
        del parsed
        gc.collect()
    append_timing_summary(
        records,
        raw,
        base,
        "input_read_parse",
        "shared",
        expected_repeat_count=repeats,
    )
    return records


def append_application_totals(records: list[dict[str, object]]) -> None:
    """Add raw and median parsing-plus-engine totals from paired repeats."""

    parse_by_repeat = {
        (record["dataset_id"], record["repeat"]): record
        for record in records
        if record["measurement_kind"] == "timing"
        and record["phase"] == "input_read_parse"
    }
    sources = [
        record
        for record in records
        if record["measurement_kind"] == "timing"
        and record["phase"] in {"engine_replay", "build_plus_sale"}
    ]
    totals: list[dict[str, object]] = []
    for source in sources:
        parse_record = parse_by_repeat.get((source["dataset_id"], source["repeat"]))
        if parse_record is None:
            raise ValueError(
                "unpaired timing repeats: no input_read_parse row for "
                f"dataset={source['dataset_id']!r}, repeat={source['repeat']!r}"
            )
        parse_elapsed = float(parse_record["elapsed_seconds"])
        source_elapsed = source["elapsed_seconds"]
        operation_attempted = source.get("attempted", True)
        if source_elapsed is None:
            if operation_attempted is not False:
                raise ValueError(
                    "null source timing must be explicitly unattempted"
                )
            # The paired parse did run, so the derived application phase has a
            # known partial duration even though its operation never started.
            total_elapsed = parse_elapsed
        else:
            total_elapsed = parse_elapsed + float(source_elapsed)
        total: dict[str, object] = {
            key: source[key]
            for key in (
                "dataset_id",
                "experiment",
                "scenario",
                "seed",
                "event_count",
                "levels",
                "event_sha256",
                "version",
                "repeat",
            )
        }
        for optional in ("liquidation_percent", "requested_qty_units"):
            if optional in source:
                total[optional] = source[optional]
        total.update(
            {
                "measurement_kind": "timing",
                "phase": "application_total",
                "elapsed_seconds": total_elapsed,
                "time_unit": "seconds",
                "input_read_parse_seconds": parse_record["elapsed_seconds"],
                "engine_seconds": source["elapsed_seconds"],
                "events_processed": source.get("events_processed"),
                "operation_attempted": operation_attempted,
                "attempted": True,
                "stopped": source["stopped"],
            }
        )
        if source["stopped"]:
            total["stop_reason"] = source["stop_reason"]
        elif source.get("events_processed") and total_elapsed > 0:
            total["throughput_events_per_second"] = (
                int(source["events_processed"]) / total_elapsed
            )
        totals.append(total)
    records.extend(totals)

    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for total in totals:
        key = (
            total["dataset_id"],
            total["version"],
            total.get("liquidation_percent"),
        )
        grouped.setdefault(key, []).append(total)
    for values in grouped.values():
        first = values[0]
        base = {
            key: first[key]
            for key in (
                "dataset_id",
                "experiment",
                "scenario",
                "seed",
                "event_count",
                "levels",
                "event_sha256",
            )
        }
        for optional in ("liquidation_percent", "requested_qty_units"):
            if optional in first:
                base[optional] = first[optional]
        append_timing_summary(
            records,
            values,
            base,
            "application_total",
            str(first["version"]),
            expected_repeat_count=sum(
                1
                for dataset_id, _repeat in parse_by_repeat
                if dataset_id == first["dataset_id"]
            ),
        )


def stream_measurements(
    events: Sequence[Mapping[str, object]],
    metadata: Mapping[str, object],
    versions: Sequence[str],
    repeats: int,
    warmup_events: int,
    diagnostic_events: int,
    latency_events: int | None,
    time_limit_seconds: float | None,
    include_memory: bool,
) -> list[dict[str, object]]:
    base = common_fields(metadata)
    records: list[dict[str, object]] = []
    diagnostic_input = events[: min(len(events), diagnostic_events)]
    correctness = compare_versions(diagnostic_input, time_limit_seconds)
    records.append(
        {
            **base,
            "measurement_kind": "correctness",
            "phase": "diagnostic_prefix",
            "version": "shared",
            **correctness,
        }
    )

    # Operation counts explain a small representative prefix and remain
    # separate from primary timing. They are bounded like every other
    # potentially long operation.
    diagnostics = replay_diagnostics(
        RevisedOrderBook,
        diagnostic_input,
        time_limit_seconds,
    )
    records.append(
        {
            **base,
            "measurement_kind": "operation_counts",
            "phase": "diagnostic_prefix_instrumented",
            "version": "revised",
            **diagnostics,
        }
    )

    for version in versions:
        book_class = IMPLEMENTATIONS[version]
        warm_up(book_class, events[: min(len(events), warmup_events)])
        raw: list[dict[str, object]] = []
        for repeat in range(repeats):
            outcome = timed_replay(book_class, events, time_limit_seconds)
            elapsed = float(outcome["elapsed_seconds"])
            record = {
                **base,
                "measurement_kind": "timing",
                "phase": "engine_replay",
                "version": version,
                "repeat": repeat,
                "time_unit": "seconds",
                **outcome,
            }
            if not record["stopped"] and elapsed > 0:
                record["throughput_events_per_second"] = len(events) / elapsed
            raw.append(record)
            records.append(record)
        append_timing_summary(
            records,
            raw,
            base,
            "engine_replay",
            version,
            expected_repeat_count=repeats,
        )

        latency_input = events if latency_events is None else events[:latency_events]
        latency = latency_replay(book_class, latency_input, time_limit_seconds)
        records.append(
            {
                **base,
                "measurement_kind": "latency",
                "phase": "per_event_instrumented",
                "version": version,
                "percentile_convention": "nearest-rank: ceil(p/100*n), minimum rank 1",
                "latency_unit": "nanoseconds",
                **latency,
            }
        )

        if include_memory:
            memory = traced_memory_replay(book_class, events, time_limit_seconds)
            records.append(
                {
                    **base,
                    "measurement_kind": "memory",
                    "phase": "engine_replay",
                    "version": version,
                    "memory_unit": "traced_bytes",
                    **memory,
                }
            )
    return records


def traced_liquidation(
    book_class: type[Any],
    setup_events: Sequence[Mapping[str, object]],
    sale_event: Mapping[str, object],
    time_limit_seconds: float | None,
) -> dict[str, object]:
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc must not already be running")
    gc.collect()
    processed = 0
    stopped = False
    stop_reason: str | None = None
    tracemalloc.start()
    try:
        book = book_class()
        final_output: dict[str, object] | None = None
        try:
            with time_limit(time_limit_seconds):
                for event in setup_events:
                    book.ProcessEvent(event)
                    processed += 1
                final_output = book.ProcessEvent(sale_event)
                processed += 1
        except MeasurementTimeout as error:
            stopped = True
            stop_reason = str(error)
        current, peak = tracemalloc.get_traced_memory()
        assert book is not None
        assert final_output is not None or stopped
    finally:
        tracemalloc.stop()
    result: dict[str, object] = {
        "current_traced_bytes": current,
        "peak_traced_bytes": peak,
        "events_processed": processed,
        "input_included": False,
        "book_included": True,
        "final_output_included": True,
        "prior_outputs_retained": False,
        "tracing_scope": "fresh_per_version_and_sale_size",
        "allocator_scope": "Python allocations traced by tracemalloc; native allocations excluded",
        "stopped": stopped,
    }
    if stop_reason is not None:
        result["stop_reason"] = stop_reason
    return result


def liquidation_correctness_attempt(
    book_class: type[Any],
    setup_events: Sequence[Mapping[str, object]],
    sale_event: Mapping[str, object],
    time_limit_seconds: float | None,
) -> dict[str, object]:
    """Build, sell, and inspect within the same declared diagnostic limit."""

    processed = 0
    try:
        with time_limit(time_limit_seconds):
            book = book_class()
            for event in setup_events:
                book.ProcessEvent(event)
                processed += 1
            result = book.ProcessEvent(sale_event)
            processed += 1
            state = book.InspectBook()
    except MeasurementTimeout as error:
        return {
            "events_processed": processed,
            "stopped": True,
            "stop_reason": str(error),
        }
    return {
        "events_processed": processed,
        "result": result,
        "state": state,
        "stopped": False,
    }


def liquidation_measurements(
    setup_events: Sequence[Mapping[str, object]],
    metadata: Mapping[str, object],
    versions: Sequence[str],
    repeats: int,
    warmup_events: int,
    time_limit_seconds: float | None,
    include_memory: bool,
    diagnostic_events: int | None = None,
) -> list[dict[str, object]]:
    base = common_fields(metadata)
    records: list[dict[str, object]] = []
    total_bid_qty = sum(int(event["qty_units"]) for event in setup_events)

    diagnostic_input = (
        setup_events
        if diagnostic_events is None
        else setup_events[: min(len(setup_events), diagnostic_events)]
    )
    build_diagnostics = replay_diagnostics(
        RevisedOrderBook,
        diagnostic_input,
        time_limit_seconds,
    )
    records.append(
        {
            **base,
            "measurement_kind": "operation_counts",
            "phase": "liquidation_book_build_instrumented",
            "version": "revised",
            **build_diagnostics,
        }
    )

    for percent in (10, 100, 200):
        requested = liquidation_request(total_bid_qty, percent)
        sale_event = {
            "seq": len(setup_events) + 1,
            "event_id": f"liquidation-{percent}",
            "type": "MARKET_SELL",
            "order_id": f"liquidation-{percent}",
            "qty_units": requested,
        }
        attempts = {
            name: liquidation_correctness_attempt(
                book_class,
                setup_events,
                sale_event,
                time_limit_seconds,
            )
            for name, book_class in IMPLEMENTATIONS.items()
        }
        stopped_versions = [
            name for name, attempt in attempts.items() if attempt["stopped"]
        ]
        if stopped_versions:
            stop_reason = "; ".join(
                f"{name}: {attempts[name]['stop_reason']}"
                for name in stopped_versions
            )
            records.append(
                {
                    **base,
                    "measurement_kind": "correctness",
                    "phase": "individual_sale",
                    "version": "shared",
                    "liquidation_percent": percent,
                    "requested_qty_units": requested,
                    "attempt_events_processed": {
                        name: attempt["events_processed"]
                        for name, attempt in attempts.items()
                    },
                    "completed_versions": [
                        name for name in attempts if name not in stopped_versions
                    ],
                    "stopped": True,
                    "stop_reason": stop_reason,
                }
            )
            del attempts, stopped_versions
            gc.collect()
            continue

        results = {name: attempt["result"] for name, attempt in attempts.items()}
        states = {name: attempt["state"] for name, attempt in attempts.items()}
        if results["baseline"] != results["revised"] or states["baseline"] != states["revised"]:
            raise AssertionError(f"liquidation versions disagree at {percent}%")
        fills = results["revised"]["fills"]
        records.append(
            {
                **base,
                "measurement_kind": "correctness",
                "phase": "individual_sale",
                "version": "shared",
                "liquidation_percent": percent,
                "requested_qty_units": requested,
                "ordered_results_equal": True,
                "final_books_equal": True,
                "fill_count": len(fills),
                "maker_price_levels_visited": len({fill["price_ticks"] for fill in fills}),
                "unfilled_qty_units": results["revised"]["unfilled_qty_units"],
                "stopped": False,
            }
        )
        # Correctness states and fill lists can be large. Release them before
        # warm-up, timing, or tracing so later phases start from a clean
        # lifecycle boundary.
        del fills, results, states, attempts, stopped_versions
        gc.collect()

    for version in versions:
        book_class = IMPLEMENTATIONS[version]
        warm_up(book_class, setup_events[: min(len(setup_events), warmup_events)])
        for percent in (10, 100, 200):
            requested = liquidation_request(total_bid_qty, percent)
            sale_event = {
                "seq": len(setup_events) + 1,
                "event_id": f"liquidation-{percent}",
                "type": "MARKET_SELL",
                "order_id": f"liquidation-{percent}",
                "qty_units": requested,
            }
            phase_raw: dict[str, list[dict[str, object]]] = {
                "book_build": [],
                "individual_sale": [],
                "build_plus_sale": [],
            }
            for repeat in range(repeats):
                book: Any | None = None
                build_events_processed = 0
                build_started: float | None = None
                build_stopped = False
                try:
                    with time_limit(time_limit_seconds):
                        build_started = perf_counter()
                        book = book_class()
                        for event in setup_events:
                            book.ProcessEvent(event)
                            build_events_processed += 1
                        build_elapsed = perf_counter() - build_started
                except MeasurementTimeout as error:
                    build_elapsed = (
                        0.0
                        if build_started is None
                        else perf_counter() - build_started
                    )
                    build_stopped = True
                    stop_reason = str(error)

                build_record: dict[str, object] = {
                    **base,
                    "measurement_kind": "timing",
                    "phase": "book_build",
                    "version": version,
                    "repeat": repeat,
                    "liquidation_percent": percent,
                    "requested_qty_units": requested,
                    "elapsed_seconds": build_elapsed,
                    "time_unit": "seconds",
                    "events_processed": build_events_processed,
                    "attempted": True,
                    "stopped": build_stopped,
                }
                if build_stopped:
                    build_record["stop_reason"] = stop_reason
                else:
                    build_record["throughput_events_per_second"] = len(setup_events) / build_elapsed
                records.append(build_record)
                phase_raw["book_build"].append(build_record)

                if build_stopped:
                    sale_not_attempted = {
                        **base,
                        "measurement_kind": "timing",
                        "phase": "individual_sale",
                        "version": version,
                        "repeat": repeat,
                        "liquidation_percent": percent,
                        "requested_qty_units": requested,
                        "elapsed_seconds": None,
                        "time_unit": "seconds",
                        "events_processed": 0,
                        "attempted": False,
                        "stopped": True,
                        "stop_reason": "book build stopped; sale not attempted",
                    }
                    partial_combined = {
                        **base,
                        "measurement_kind": "timing",
                        "phase": "build_plus_sale",
                        "version": version,
                        "repeat": repeat,
                        "liquidation_percent": percent,
                        "requested_qty_units": requested,
                        "elapsed_seconds": build_elapsed,
                        "time_unit": "seconds",
                        "events_processed": build_events_processed,
                        "attempted": True,
                        "stopped": True,
                        "stop_reason": "book build stopped; sale not attempted",
                    }
                    records.extend((sale_not_attempted, partial_combined))
                    phase_raw["individual_sale"].append(sale_not_attempted)
                    phase_raw["build_plus_sale"].append(partial_combined)
                    del book
                    gc.collect()
                    continue

                assert book is not None
                sale_result: dict[str, object] | None = None
                fills: list[dict[str, object]] | None = None
                sale_started: float | None = None
                try:
                    with time_limit(time_limit_seconds):
                        sale_started = perf_counter()
                        sale_result = book.ProcessEvent(sale_event)
                        sale_elapsed = perf_counter() - sale_started
                except MeasurementTimeout as error:
                    sale_elapsed = (
                        0.0
                        if sale_started is None
                        else perf_counter() - sale_started
                    )
                    sale_stopped = True
                    sale_stop_reason = str(error)
                    fill_count = None
                    levels_visited = None
                    unfilled = None
                else:
                    sale_stopped = False
                    fills = sale_result["fills"]
                    fill_count = len(fills)
                    levels_visited = len({fill["price_ticks"] for fill in fills})
                    unfilled = sale_result["unfilled_qty_units"]

                sale_record: dict[str, object] = {
                    **base,
                    "measurement_kind": "timing",
                    "phase": "individual_sale",
                    "version": version,
                    "repeat": repeat,
                    "liquidation_percent": percent,
                    "requested_qty_units": requested,
                    "elapsed_seconds": sale_elapsed,
                    "time_unit": "seconds",
                    "fill_count": fill_count,
                    "maker_price_levels_visited": levels_visited,
                    "unfilled_qty_units": unfilled,
                    "events_processed": 0 if sale_stopped else 1,
                    "attempted": True,
                    "stopped": sale_stopped,
                }
                if sale_stopped:
                    sale_record["stop_reason"] = sale_stop_reason
                records.append(sale_record)
                phase_raw["individual_sale"].append(sale_record)

                combined_record = {
                    **base,
                    "measurement_kind": "timing",
                    "phase": "build_plus_sale",
                    "version": version,
                    "repeat": repeat,
                    "liquidation_percent": percent,
                    "requested_qty_units": requested,
                    "elapsed_seconds": build_elapsed + sale_elapsed,
                    "time_unit": "seconds",
                    "events_processed": len(setup_events) + (0 if sale_stopped else 1),
                    "attempted": True,
                    "stopped": sale_stopped,
                }
                if sale_stopped:
                    combined_record["stop_reason"] = sale_stop_reason
                records.append(combined_record)
                phase_raw["build_plus_sale"].append(combined_record)

                # The next construction repeat must not pay to release this
                # trial's book or fill output.
                del fills, sale_result, book
                gc.collect()

            phase_base = {
                **base,
                "liquidation_percent": percent,
                "requested_qty_units": requested,
            }
            for phase, raw in phase_raw.items():
                append_timing_summary(
                    records,
                    raw,
                    phase_base,
                    phase,
                    version,
                    expected_repeat_count=repeats,
                )

            if include_memory:
                memory = traced_liquidation(
                    book_class,
                    setup_events,
                    sale_event,
                    time_limit_seconds,
                )
                records.append(
                    {
                        **phase_base,
                        "measurement_kind": "memory",
                        "phase": "build_plus_sale",
                        "version": version,
                        "memory_unit": "traced_bytes",
                        **memory,
                    }
                )
    return records


def main() -> int:
    args = parse_args()
    versions = args.versions or list(IMPLEMENTATIONS)
    repeats = args.repeats if args.repeats is not None else (2 if args.profile == "smoke" else 5)
    parse_repeats = (
        args.parse_repeats
        if args.parse_repeats is not None
        else (2 if args.profile == "smoke" else 5)
    )
    warmup_events = (
        args.warmup_events
        if args.warmup_events is not None
        else (100 if args.profile == "smoke" else 1_000)
    )
    latency_events = args.latency_events
    if latency_events is None and args.profile == "smoke":
        latency_events = 1_000
    for name, value in (
        ("repeats", repeats),
        ("parse_repeats", parse_repeats),
        ("warmup_events", warmup_events),
        ("diagnostic_events", args.diagnostic_events),
    ):
        if value < 1:
            raise SystemExit(f"{name} must be positive")
    if parse_repeats != repeats:
        raise SystemExit(
            "parse_repeats must equal repeats so every application-total repeat "
            "has an immutable one-to-one parse/replay pair"
        )

    environment = environment_metadata()
    if args.profile == "canonical" and environment["git_dirty"]:
        raise SystemExit(
            "canonical measurement refused: commit the measurement code and run "
            "from a clean Assignment1 tree first"
        )

    paths = sorted(args.data_dir.glob("*.jsonl.gz"))
    if not paths:
        raise SystemExit(
            f"no prepared datasets found in {args.data_dir}; run "
            "tools/prepare_benchmarks.py first"
        )

    datasets: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    for path in paths:
        events, metadata = load_dataset(path)
        datasets.append(metadata)
        records.extend(parse_measurements(path, metadata, parse_repeats))
        if metadata["experiment"] == "liquidation":
            records.extend(
                liquidation_measurements(
                    events,
                    metadata,
                    versions,
                    repeats,
                    warmup_events,
                    args.time_limit_seconds,
                    not args.skip_memory,
                    diagnostic_events=args.diagnostic_events,
                )
            )
        else:
            records.extend(
                stream_measurements(
                    events,
                    metadata,
                    versions,
                    repeats,
                    warmup_events,
                    args.diagnostic_events,
                    latency_events,
                    args.time_limit_seconds,
                    not args.skip_memory,
                )
            )
        print(f"measured {metadata['dataset_id']}")

    append_application_totals(records)

    report: dict[str, object] = {
        "schema_version": 1,
        "run_label": "provisional_smoke" if args.profile == "smoke" else "canonical",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "settings": {
            "profile": args.profile,
            "versions": versions,
            "repeats": repeats,
            "parse_repeats": parse_repeats,
            "warmup_events": warmup_events,
            "diagnostic_events": args.diagnostic_events,
            "latency_events": latency_events,
            "operation_time_limit_seconds": args.time_limit_seconds,
            "time_limit_scope": (
                "engine replay, per-event latency, liquidation build/sale, "
                "bounded correctness attempts, and memory tracing; input parsing "
                "and derived application totals are not independently limited"
            ),
            "completed_timing_boundary": (
                "perf_counter starts after timeout-handler setup and stops before "
                "timeout-handler teardown"
            ),
            "stopped_timing_boundary": (
                "after an operation starts, elapsed time ends in the exception "
                "handler after timeout-context teardown; a pre-start timeout records zero"
            ),
            "memory_enabled": not args.skip_memory,
            "measurement_integrity_revision": MEASUREMENT_INTEGRITY_REVISION,
            "same_prepared_event_tuple_for_versions": True,
            "fresh_book_per_replay_and_liquidation_size": True,
            "primary_timing_excludes_input_read_parse": True,
            "latency_instrumentation_separate_from_primary_timing": True,
            "operation_counts_separate_from_primary_timing": True,
            "memory_tracing_separate_from_primary_timing": True,
            "command": [sys.executable, *sys.argv],
        },
        "datasets": datasets,
        "records": records,
    }
    validate_report(report)
    write_report(args.output, report)
    print(f"run_label={report['run_label']}")
    print(f"datasets={len(datasets)}")
    print(f"records={len(records)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
