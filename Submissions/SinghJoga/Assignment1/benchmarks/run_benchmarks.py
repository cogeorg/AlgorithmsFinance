"""Run reproducible order-book timing and diagnostic experiments."""

import argparse
import cProfile
import ctypes
import hashlib
import inspect
import json
import math
import multiprocessing
import os
import platform
import pstats
import random
import statistics
import subprocess
import sys
import time
import traceback
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.metrics import (  # noqa: E402
    book_state_counts,
    ceil_percent,
    counter_replay,
    load_events,
    percentile_nearest_rank,
    phase_row,
    replay_without_history,
    state_peak_replay,
    stopped_phase_row,
    summarize_seconds,
    validate_event_stream,
)
from benchmarks import metrics as _metrics  # noqa: E402


SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
VERSIONS = ("baseline", "revised")
RUNS_DIR = ROOT / "results" / "benchmarks"
TIMING_REPEATS = 5
MEMORY_POLL_SECONDS = 0.05
LEGACY_RUNNER_SHA256 = "aa88c4cd76d8f3b0d26bdb47c68e290ea184e8aa352ee939f7999f03243ff09b"
LEGACY_METRICS_SHA256 = "3fdb7a3d356544d76894c7778ea0f7be8295c2bdc8185dc17e2513c490fdb4eb"
DEFAULT_PHASE_BUDGETS = {
    "primary": 300.0,
    "latency": 300.0,
    "memory": 300.0,
    "state_peaks": 300.0,
    "counters": 60.0,
    "profile": 60.0,
}
SMOKE_PHASE_BUDGETS = {
    "primary": 60.0,
    "latency": 60.0,
    "memory": 60.0,
    "state_peaks": 60.0,
    "counters": 30.0,
    "profile": 30.0,
}
PHASE_DEFINITION_IDS = {
    "input_read_parse": "primary-input-read-parse-v1",
    "empty_engine_construction": "primary-empty-construction-v1",
    "engine_replay": "primary-replay-v1",
    "total_application": "primary-total-application-v1",
    "initial_book_construction": "primary-initial-book-v1",
    "latency": "event-latency-v1",
    "memory": "tracemalloc-checkpoints-v1",
    "state_peaks": "event-result-state-peaks-v1",
    "counters": "small-snapshot-counter-estimates-v2",
    "profile": "bounded-cprofile-v1",
}
GENERIC_PRIMARY_PHASES = (
    "input_read_parse",
    "empty_engine_construction",
    "engine_replay",
    "total_application",
)


def _json_write_exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _write_custom_jsonl(path, events, settings):
    path = Path(path)
    metadata_path = Path(str(path) + ".metadata.json")
    if path.exists() or metadata_path.exists():
        if not path.is_file() or not metadata_path.is_file():
            raise FileExistsError(f"incomplete existing input: {path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        actual_hash = _sha256_file(path)
        if metadata.get("settings") != settings:
            raise ValueError(f"existing input settings differ: {path}")
        if metadata.get("sha256") != actual_hash:
            raise ValueError(f"existing input checksum differs: {path}")
        return metadata

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(json.dumps(event, separators=(",", ":")))
            stream.write("\n")

    metadata = {
        "generator": "benchmarks.run_benchmarks custom deterministic workload",
        "settings": settings,
        "event_count": len(events),
        "sha256": _sha256_file(path),
    }
    _json_write_exclusive(metadata_path, metadata)
    return metadata


def _generated_events_path(run_dir, scenario, event_count, seed, levels):
    supplied = ROOT / "data" / f"{scenario}_10000.jsonl.gz"
    if event_count == 10000 and seed == 42 and levels == 1000 and supplied.is_file():
        return supplied

    inputs_dir = Path(run_dir) / "inputs"
    output = inputs_dir / (
        f"{scenario}_M{event_count}_seed{seed}_levels{levels}.jsonl.gz"
    )
    metadata_path = Path(str(output) + ".metadata.json")
    expected = {
        "scenario": scenario,
        "events": event_count,
        "seed": seed,
        "levels": levels,
    }
    if output.exists() or metadata_path.exists():
        if not output.is_file() or not metadata_path.is_file():
            raise FileExistsError(f"incomplete generated input: {output}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise ValueError(f"existing generated input settings differ: {output}")
        if metadata.get("sha256") != _sha256_file(output):
            raise ValueError(f"existing generated input checksum differs: {output}")
        return output

    command = [
        sys.executable,
        str(ROOT / "generate_orders.py"),
        "--scenario",
        scenario,
        "--events",
        str(event_count),
        "--levels",
        str(levels),
        "--seed",
        str(seed),
        "--out",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(completed.stdout.strip().splitlines()[-1])
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(f"generator returned unexpected settings for {output}")
    return output


def _make_fixed_book_events(order_count, seed):
    rng = random.Random(seed)
    price_levels = min(100, order_count)
    events = []
    for index in range(order_count):
        seq = index + 1
        order_id = f"fixed-bid-{index:08d}"
        events.append(
            {
                "seq": seq,
                "event_id": f"fixed-event-{seq:08d}",
                "type": "LIMIT",
                "order_id": order_id,
                "side": "BUY",
                "price_ticks": 6000000 - (index % price_levels),
                "qty_units": rng.randint(1, 7) * 1000000,
            }
        )
    return events


def _make_queue_events(order_count, price_count, seed):
    rng = random.Random(seed)
    events = []
    for index in range(order_count):
        seq = index + 1
        events.append(
            {
                "seq": seq,
                "event_id": f"queue-event-{seq:08d}",
                "type": "LIMIT",
                "order_id": f"queue-order-{index:08d}",
                "side": "BUY",
                "price_ticks": 5500000 + ((index + seed) % price_count),
                "qty_units": rng.randint(1, 9) * 100000,
            }
        )
    return events


def _make_anchored_churn_events(cycles):
    events = [
        {
            "seq": 1,
            "event_id": "anchor-event",
            "type": "LIMIT",
            "order_id": "anchor-bid",
            "side": "BUY",
            "price_ticks": 6000000,
            "qty_units": 1000000,
        }
    ]
    for index in range(cycles):
        add_seq = 2 + index * 2
        order_id = f"churn-order-{index:08d}"
        events.append(
            {
                "seq": add_seq,
                "event_id": f"churn-add-{index:08d}",
                "type": "LIMIT",
                "order_id": order_id,
                "side": "BUY",
                "price_ticks": 1000000 + index,
                "qty_units": 1000000,
            }
        )
        events.append(
            {
                "seq": add_seq + 1,
                "event_id": f"churn-cancel-{index:08d}",
                "type": "CANCEL",
                "target_order_id": order_id,
            }
        )
    return events


def _custom_case(run_dir, case_id, experiment, scenario, seed, events, settings):
    input_path = Path(run_dir) / "inputs" / f"{case_id}.jsonl"
    _write_custom_jsonl(input_path, events, settings)
    validate_event_stream(events, expected_count=len(events))
    return {
        "case_id": case_id,
        "experiment": experiment,
        "scenario": scenario,
        "seed": seed,
        "event_count": len(events),
        "input_path": str(input_path.resolve()),
        "input_paths": [str(input_path.resolve())],
        "input_checksums": {input_path.name: _sha256_file(input_path)},
        "generator_settings": settings,
    }


def build_cases(settings, run_dir):
    cases = []
    for scenario in settings["scenarios"]:
        for event_count in settings["event_sizes"]:
            for seed in settings["seeds"]:
                input_path = _generated_events_path(
                    run_dir,
                    scenario,
                    event_count,
                    seed,
                    settings["levels"],
                )
                events = load_events(input_path)
                validate_event_stream(events, expected_count=event_count)
                sidecar = Path(str(input_path) + ".metadata.json")
                sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
                expected_settings = {
                    "scenario": scenario,
                    "events": event_count,
                    "seed": seed,
                    "levels": settings["levels"],
                }
                if any(
                    sidecar_data.get(key) != value
                    for key, value in expected_settings.items()
                ):
                    raise ValueError(f"input metadata mismatch: {input_path}")
                if sidecar_data.get("sha256") != _sha256_file(input_path):
                    raise ValueError(f"input checksum mismatch: {input_path}")
                cases.append(
                    {
                        "case_id": (
                            f"workload_{scenario}_M{event_count}_seed{seed}"
                        ),
                        "experiment": "workload_replay",
                        "scenario": scenario,
                        "seed": seed,
                        "event_count": event_count,
                        "input_path": str(input_path.resolve()),
                        "input_paths": [str(input_path.resolve())],
                        "input_checksums": {
                            input_path.name: _sha256_file(input_path)
                        },
                        "generator_settings": {
                            "generator": "generate_orders.py",
                            "scenario": scenario,
                            "events": event_count,
                            "seed": seed,
                            "levels": settings["levels"],
                            "source": (
                                "supplied" if input_path.parent == ROOT / "data"
                                else "generated"
                            ),
                        },
                        "profile": (
                            scenario == "mixed"
                            and event_count == min(settings["event_sizes"])
                            and seed == settings["seeds"][0]
                        ),
                    }
                )

    fixed_events = _make_fixed_book_events(
        settings["fixed_book_orders"], settings["seeds"][0]
    )
    fixed_total = sum(event["qty_units"] for event in fixed_events)
    fixed_input = _custom_case(
        run_dir,
        f"fixed_bid_book_M{len(fixed_events)}_seed{settings['seeds'][0]}",
        "fixed_liquidation",
        "fixed_bid_book",
        settings["seeds"][0],
        fixed_events,
        {
            "generator": "fixed bid-book builder",
            "orders": len(fixed_events),
            "seed": settings["seeds"][0],
            "price_levels": min(100, len(fixed_events)),
            "quantity_rule": "seeded integer multiples of 1,000,000 units",
        },
    )
    fixed_input.update(
        {
            "event_count": len(fixed_events) + 1,
            "initial_book_event_count": len(fixed_events),
            "available_bid_qty_units": fixed_total,
            "sell_quantities": [
                {"percent": percent, "qty_units": ceil_percent(fixed_total, percent)}
                for percent in (10, 100, 200)
            ],
        }
    )
    cases.append(fixed_input)

    for price_count in (4, 1000):
        queue_events = _make_queue_events(
            settings["queue_orders"], price_count, settings["seeds"][0]
        )
        queue_case = _custom_case(
            run_dir,
            f"queue_concentration_prices{price_count}_M{len(queue_events)}",
            "queue_concentration",
            f"queue_{price_count}_prices",
            settings["seeds"][0],
            queue_events,
            {
                "generator": "queue concentration builder",
                "orders": len(queue_events),
                "available_prices": price_count,
                "seed": settings["seeds"][0],
                "quantity_rule": (
                    "same seeded quantity sequence across price concentrations"
                ),
            },
        )
        queue_case["available_price_count"] = price_count
        cases.append(queue_case)

    churn_events = _make_anchored_churn_events(settings["churn_cycles"])
    churn_case = _custom_case(
        run_dir,
        f"churn_with_anchor_cycles{settings['churn_cycles']}",
        "cancellation_churn",
        "churn_with_anchor",
        settings["seeds"][0],
        churn_events,
        {
            "generator": "anchored cancellation churn builder",
            "cycles": settings["churn_cycles"],
            "events": len(churn_events),
            "anchor_order_remains_active": True,
            "transient_prices": "unique prices below the anchor",
        },
    )
    cases.append(churn_case)
    return cases


def _case_manifest(case):
    result = {}
    for name in (
        "case_id",
        "experiment",
        "scenario",
        "seed",
        "event_count",
        "input_checksums",
        "generator_settings",
        "initial_book_event_count",
        "available_bid_qty_units",
        "sell_quantities",
        "available_price_count",
        "profile",
    ):
        if name in case:
            result[name] = case[name]
    result["input_paths"] = [_relative_path(path) for path in case["input_paths"]]
    return result


def _get_engine_class(version):
    if version == "baseline":
        from orderbook.baseline import OrderBook
    elif version == "revised":
        from orderbook.revised import OrderBook
    else:
        raise ValueError(f"unknown engine version: {version}")
    return OrderBook


def _validate_pair(events, event_limit):
    compared_events = events[:event_limit]
    baseline = _get_engine_class("baseline")()
    revised = _get_engine_class("revised")()
    for position, event in enumerate(compared_events, start=1):
        baseline_result = baseline.process_event(event)
        revised_result = revised.process_event(event)
        if revised_result != baseline_result:
            raise AssertionError(
                f"result parity failed at event {position}: {event!r}"
            )
        if revised.last_accepted_seq != baseline.last_accepted_seq:
            raise AssertionError(
                f"accepted-sequence parity failed at event {position}"
            )
        if revised.inspect_book() != baseline.inspect_book():
            raise AssertionError(f"book parity failed at event {position}")
    return len(compared_events)


def validate_case(case, event_limit):
    events = load_events(case["input_path"])
    validate_event_stream(events, expected_count=case["event_count"]
                          if case["experiment"] != "fixed_liquidation"
                          else case["initial_book_event_count"])
    if case["experiment"] != "fixed_liquidation":
        return {
            "status": "passed",
            "events_compared": _validate_pair(events, event_limit),
            "sale_cases_compared": 0,
        }

    initial_events = events[:event_limit]
    events_compared = _validate_pair(initial_events, event_limit)
    available_qty = sum(event["qty_units"] for event in initial_events)
    sale_cases_compared = 0
    for percent in (10, 100, 200):
        qty_units = ceil_percent(available_qty, percent)
        sale_event = {
            "seq": len(initial_events) + 1,
            "event_id": f"parity-sale-{percent}",
            "type": "MARKET_SELL",
            "order_id": f"parity-taker-{percent}",
            "qty_units": qty_units,
        }
        event_stream = initial_events + [sale_event]
        if _validate_pair(event_stream, len(event_stream)) != len(event_stream):
            raise AssertionError("fixed-book sale parity length mismatch")
        sale_cases_compared += 1
    return {
        "status": "passed",
        "events_compared": events_compared,
        "sale_cases_compared": sale_cases_compared,
    }


def _environment_snapshot():
    requirement_path = ROOT / "requirements.txt"
    dependencies = [
        line.strip()
        for line in requirement_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_dirty = bool(git_status.strip())
    except (OSError, subprocess.CalledProcessError) as error:
        head = None
        branch = None
        git_dirty = None
        git_error = str(error)
    else:
        git_error = None
    return {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "dependencies": dependencies,
        "machine": platform.machine(),
        "processor": platform.processor(),
        "platform": platform.platform(),
        "os": os.name,
        "git_head": head,
        "git_branch": branch,
        "git_dirty": git_dirty,
        "git_error": git_error,
    }


def _code_hashes():
    paths = {
        "baseline.py": ROOT / "orderbook" / "baseline.py",
        "revised.py": ROOT / "orderbook" / "revised.py",
        "generate_orders.py": ROOT / "generate_orders.py",
        "run_benchmarks.py": Path(__file__),
        "metrics.py": Path(__file__).with_name("metrics.py"),
        "test_specification.py": ROOT / "tests" / "test_specification.py",
        "test_generated_streams.py": ROOT / "tests" / "test_generated_streams.py",
        "test_benchmark_tools.py": ROOT / "tests" / "test_benchmark_tools.py",
    }
    return {
        name: _sha256_file(path)
        for name, path in paths.items()
        if path.is_file()
    }


def _sale_event(case, percent, qty_units):
    seq = case["initial_book_event_count"] + 1
    return {
        "seq": seq,
        "event_id": f"liquidation-event-{percent}",
        "type": "MARKET_SELL",
        "order_id": f"liquidation-taker-{percent}",
        "qty_units": qty_units,
    }


def _emit(connection, row):
    connection.send({"kind": "row", "row": row})


def _timing_phase(connection, phase, repeats, warmup, measure, event_count):
    warmup()
    values = []
    for repeat in range(1, repeats + 1):
        elapsed, details = measure()
        values.append(elapsed)
        row = phase_row(phase, repeat=repeat, elapsed_seconds=elapsed)
        row.update(details)
        if event_count is not None and phase in (
            "engine_replay",
            "total_application",
        ):
            row["throughput_events_per_second"] = (
                event_count / elapsed if elapsed > 0 else None
            )
        _emit(connection, row)

    summary = summarize_seconds(values, event_count or 0)
    row = phase_row(
        f"{phase}_summary",
        status="completed",
        elapsed_seconds=summary["median_seconds"],
    )
    row["raw_repeats_seconds"] = values
    row["median_seconds"] = summary["median_seconds"]
    row["throughput_events_per_second"] = summary[
        "throughput_events_per_second"
    ] if event_count else None
    _emit(connection, row)


def _measure_input_parse(path):
    started = time.perf_counter()
    events = load_events(path)
    elapsed = time.perf_counter() - started
    return elapsed, {"parsed_event_count": len(events)}


def _measure_engine_replay(book_type, events):
    book = book_type()
    started = time.perf_counter()
    replay_without_history(book, events)
    return time.perf_counter() - started, {}


def _measure_total_application(path, book_type):
    started = time.perf_counter()
    events = load_events(path)
    book = book_type()
    replay_without_history(book, events)
    return time.perf_counter() - started, {"parsed_event_count": len(events)}


def _build_book(book_type, events):
    book = book_type()
    replay_without_history(book, events)
    return book


def _measure_initial_book(book_type, initial_events):
    started = time.perf_counter()
    _build_book(book_type, initial_events)
    return time.perf_counter() - started, {}


def _measure_sell_operation(book_type, initial_events, sale_event):
    book = _build_book(book_type, initial_events)
    started = time.perf_counter()
    result = book.process_event(sale_event)
    elapsed = time.perf_counter() - started
    return elapsed, {"returned_fill_count": len(result.get("fills", []))}


def _measure_total_sell(path, book_type, sale_event):
    started = time.perf_counter()
    initial_events = load_events(path)
    book = _build_book(book_type, initial_events)
    result = book.process_event(sale_event)
    elapsed = time.perf_counter() - started
    return elapsed, {
        "parsed_event_count": len(initial_events),
        "returned_fill_count": len(result.get("fills", [])),
    }


def _state_checkpoint(book, event_position, label, last_result):
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    row = phase_row("memory", repeat=1)
    row.update(book_state_counts(book))
    row.update(
        {
            "checkpoint": label,
            "event_position": event_position,
            "traced_current_bytes": current_bytes,
            "traced_peak_bytes": peak_bytes,
            "current_result_retained": last_result is not None,
        }
    )
    return row


def _memory_replay(book_type, events, case):
    if not events:
        raise ValueError("memory replay requires events")
    tracemalloc.start()
    rows = []
    try:
        book = book_type()
        last_result = None
        positions = {
            max(1, math.ceil(len(events) * fraction))
            for fraction in (0.25, 0.5, 0.75, 1.0)
        }
        if case["experiment"] == "fixed_liquidation":
            positions.add(len(events) - 1)
        for position, event in enumerate(events, start=1):
            last_result = book.process_event(event)
            if position in positions:
                label = (
                    "final"
                    if position == len(events)
                    else f"after_event_{position}"
                )
                rows.append(_state_checkpoint(book, position, label, last_result))
    finally:
        tracemalloc.stop()
    return rows


def _counter_event_replay(book_type, events):
    return counter_replay(book_type, events)


def _latency_replay(book_type, events, raw_path):
    replay_without_history(book_type(), events)
    book = book_type()
    raw_latencies = []
    raw_path = Path(raw_path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("x", encoding="utf-8", newline="\n", buffering=1) as stream:
        for position, event in enumerate(events, start=1):
            started = time.perf_counter()
            book.process_event(event)
            elapsed = time.perf_counter() - started
            raw_latencies.append(elapsed)
            stream.write(
                json.dumps(
                    {
                        "event_position": position,
                        "event_seq": event["seq"],
                        "event_type": event["type"],
                        "latency_seconds": elapsed,
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
            stream.flush()
    if not raw_latencies:
        raise ValueError("latency replay requires events")
    window_size = max(1, math.ceil(len(raw_latencies) / 10))
    early_window = raw_latencies[:window_size]
    late_window = raw_latencies[-window_size:]
    return {
        "latency_median_seconds": statistics.median(raw_latencies),
        "latency_p95_seconds": percentile_nearest_rank(raw_latencies, 95),
        "latency_p99_seconds": percentile_nearest_rank(raw_latencies, 99),
        "latency_percentile_convention": "nearest rank; median uses statistics.median",
        "latency_raw_count": len(raw_latencies),
        "latency_raw_path": str(raw_path),
        "latency_process_throughput_events_per_second": (
            len(raw_latencies) / sum(raw_latencies)
            if sum(raw_latencies) > 0
            else None
        ),
        "early_window_event_count": len(early_window),
        "early_window_median_seconds": statistics.median(early_window),
        "early_window_p95_seconds": percentile_nearest_rank(early_window, 95),
        "early_window_p99_seconds": percentile_nearest_rank(early_window, 99),
        "early_window_process_throughput_events_per_second": (
            len(early_window) / sum(early_window)
            if sum(early_window) > 0
            else None
        ),
        "late_window_event_count": len(late_window),
        "late_window_median_seconds": statistics.median(late_window),
        "late_window_p95_seconds": percentile_nearest_rank(late_window, 95),
        "late_window_p99_seconds": percentile_nearest_rank(late_window, 99),
        "late_window_process_throughput_events_per_second": (
            len(late_window) / sum(late_window)
            if sum(late_window) > 0
            else None
        ),
    }


def _profile_replay(book_type, events, artifact_dir, max_events):
    profiled_events = events[:max_events]
    book = book_type()
    profiler = cProfile.Profile()
    profiler.enable()
    replay_without_history(book, profiled_events)
    profiler.disable()

    artifact_dir = Path(artifact_dir)
    binary_path = artifact_dir / "profile.prof"
    text_path = artifact_dir / "profile.txt"
    profiler.dump_stats(str(binary_path))
    with text_path.open("x", encoding="utf-8", newline="\n") as stream:
        stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
        stats.print_stats(40)
    return {
        "profiled_event_count": len(profiled_events),
        "profile_data_path": str(binary_path),
        "profile_text_path": str(text_path),
        "profiler": "cProfile",
    }


def _generic_worker(connection, case, version, repeats, artifact_dir,
                    profile_event_limit, phase_job, settings):
    book_type = _get_engine_class(version)
    events = load_events(case["input_path"])
    event_count = len(events)
    path = case["input_path"]

    def warm_parse():
        load_events(path)

    def warm_empty():
        book_type()

    def warm_replay():
        replay_without_history(book_type(), events)

    if phase_job == "input_read_parse":
        _timing_phase(
            connection,
            "input_read_parse",
            repeats,
            warm_parse,
            lambda: _measure_input_parse(path),
            event_count,
        )
    elif phase_job == "empty_engine_construction":
        _timing_phase(
            connection,
            "empty_engine_construction",
            repeats,
            warm_empty,
            lambda: _measure_constructor(book_type),
            None,
        )
    elif phase_job == "engine_replay":
        _timing_phase(
            connection,
            "engine_replay",
            repeats,
            warm_replay,
            lambda: _measure_engine_replay(book_type, events),
            event_count,
        )

    def warm_total():
        _measure_total_application(path, book_type)

    if phase_job == "total_application":
        _timing_phase(
            connection,
            "total_application",
            repeats,
            warm_total,
            lambda: _measure_total_application(path, book_type),
            event_count,
        )
    if phase_job in (
        "input_read_parse",
        "empty_engine_construction",
        "engine_replay",
        "total_application",
    ):
        return

    if phase_job == "state_peaks":
        peak_row = phase_row("state_peaks", repeat=1)
        peak_row.update(state_peak_replay(book_type, events))
        _emit(connection, peak_row)
    elif phase_job == "counters":
        if event_count > settings["counter_max_events"]:
            raise ValueError("snapshot counters are restricted to small workloads")
        counter = _counter_event_replay(book_type, events)
        counter_row = phase_row("counters", repeat=1)
        counter_row.update(counter)
        if "available_price_count" in case:
            counter_row["available_price_count"] = case["available_price_count"]
            counter_row["realized_price_count"] = counter["final_state"][
                "occupied_price_levels"
            ]
        _emit(connection, counter_row)
    elif phase_job == "latency":
        latency_path = Path(artifact_dir) / "latencies.jsonl"
        latency_summary = _latency_replay(book_type, events, latency_path)
        latency_row = phase_row("latency_summary", repeat=1)
        latency_row.update(latency_summary)
        _emit(connection, latency_row)
    elif phase_job == "memory":
        for memory_row in _memory_replay(book_type, events, case):
            _emit(connection, memory_row)
    elif phase_job == "profile" and case.get("profile"):
        profile_summary = _profile_replay(
            book_type, events, artifact_dir, profile_event_limit
        )
        profile_row = phase_row("profile", repeat=1)
        profile_row.update(profile_summary)
        _emit(connection, profile_row)
    elif phase_job != "profile":
        raise ValueError(f"unsupported phase {phase_job!r} for generic workload")


def _measure_constructor(book_type):
    started = time.perf_counter()
    book_type()
    return time.perf_counter() - started, {}


def _fixed_worker(connection, case, version, repeats, artifact_dir, phase_job,
                   settings):
    book_type = _get_engine_class(version)
    initial_events = load_events(case["input_path"])
    event_count = len(initial_events)
    path = case["input_path"]

    def warm_parse():
        load_events(path)

    if phase_job == "input_read_parse":
        _timing_phase(
            connection,
            "input_read_parse",
            repeats,
            warm_parse,
            lambda: _measure_input_parse(path),
            event_count,
        )
    elif phase_job == "empty_engine_construction":
        _timing_phase(
            connection,
            "empty_engine_construction",
            repeats,
            lambda: book_type(),
            lambda: _measure_constructor(book_type),
            None,
        )
    elif phase_job == "initial_book_construction":
        _timing_phase(
            connection,
            "initial_book_construction",
            repeats,
            lambda: _build_book(book_type, initial_events),
            lambda: _measure_initial_book(book_type, initial_events),
            event_count,
        )

    for sale_case in case["sell_quantities"]:
        percent = sale_case["percent"]
        sale_event = _sale_event(case, percent, sale_case["qty_units"])
        phase = f"sell_operation_{percent}pct"

        def warm_sell(book_type=book_type, initial_events=initial_events,
                      sale_event=sale_event):
            _measure_sell_operation(book_type, initial_events, sale_event)

        def warm_total_sell(path=path, book_type=book_type,
                            sale_event=sale_event):
            _measure_total_sell(path, book_type, sale_event)

        if phase_job == phase:
            _timing_phase(
                connection,
                phase,
                repeats,
                warm_sell,
                lambda book_type=book_type, initial_events=initial_events,
                sale_event=sale_event: _measure_sell_operation(
                    book_type, initial_events, sale_event
                ),
                1,
            )
        elif phase_job == f"total_application_sell_{percent}pct":
            _timing_phase(
                connection,
                f"total_application_sell_{percent}pct",
                repeats,
                warm_total_sell,
                lambda path=path, book_type=book_type,
                sale_event=sale_event: _measure_total_sell(
                    path, book_type, sale_event
                ),
                len(initial_events) + 1,
            )

    if phase_job == "state_peaks":
        peak_rows = []
        for sale_case in case["sell_quantities"]:
            sale_event = _sale_event(
                case, sale_case["percent"], sale_case["qty_units"]
            )
            peaks = state_peak_replay(book_type, initial_events + [sale_event])
            peak_rows.append(peaks)
        peak_row = phase_row("state_peaks", repeat=1)
        peak_row.update(
            {
                "active_order_peak": max(
                    row["active_order_peak"] for row in peak_rows
                ),
                "occupied_price_level_peak": max(
                    row["occupied_price_level_peak"] for row in peak_rows
                ),
                "state_peak_method": "event_result_shadow_bookkeeping",
                "state_peak_counts_are": "logical event-boundary counts",
                "sale_scenarios": len(peak_rows),
            }
        )
        _emit(connection, peak_row)
    elif phase_job == "counters":
        if event_count > settings["counter_max_events"]:
            raise ValueError("snapshot counters are restricted to small workloads")
        counter_rows = []
        for sale_case in case["sell_quantities"]:
            sale_event = _sale_event(
                case, sale_case["percent"], sale_case["qty_units"]
            )
            counter_rows.append(
                (
                    sale_case,
                    _counter_event_replay(
                        book_type, initial_events + [sale_event]
                    ),
                )
            )
        counter_row = phase_row("counters", repeat=1)
        counter_row.update(
            {
                "counter_method": "per_event_canonical_snapshot",
                "inferred_operation_counts_are_estimates": True,
                "fill_count": sum(
                    row["fill_count"] for _, row in counter_rows
                ),
                "maker_touches_estimate": sum(
                    row["maker_touches_estimate"] for _, row in counter_rows
                ),
                "visited_price_levels_estimate": sum(
                    row["visited_price_levels_estimate"]
                    for _, row in counter_rows
                ),
                "active_order_peak": max(
                    row["active_order_peak"] for _, row in counter_rows
                ),
                "occupied_price_level_peak": max(
                    row["occupied_price_level_peak"]
                    for _, row in counter_rows
                ),
            }
        )
        _emit(connection, counter_row)
    elif phase_job == "memory":
        for sale_case in case["sell_quantities"]:
            sale_event = _sale_event(
                case, sale_case["percent"], sale_case["qty_units"]
            )
            for row in _memory_replay(
                book_type, initial_events + [sale_event], case
            ):
                row["requested_sell_qty_units"] = sale_event["qty_units"]
                row["sell_percent"] = sale_case["percent"]
                _emit(connection, row)
    elif phase_job == "latency":
        representative_sale = case["sell_quantities"][1]
        sale_event = _sale_event(
            case, representative_sale["percent"], representative_sale["qty_units"]
        )
        combined_events = initial_events + [sale_event]
        latency_path = Path(artifact_dir) / "latencies.jsonl"
        latency_summary = _latency_replay(
            book_type, combined_events, latency_path
        )
        latency_row = phase_row("latency_summary", repeat=1)
        latency_row.update(latency_summary)
        latency_row["requested_sell_qty_units"] = sale_event["qty_units"]
        _emit(connection, latency_row)


def _measure_worker(connection, case, version, repeats, artifact_dir,
                    profile_event_limit, phase_job, settings):
    try:
        if case["experiment"] == "fixed_liquidation":
            _fixed_worker(
                connection, case, version, repeats, artifact_dir,
                phase_job, settings,
            )
        else:
            _generic_worker(
                connection,
                case,
                version,
                repeats,
                artifact_dir,
                profile_event_limit,
                phase_job,
                settings,
            )
        connection.send({"kind": "done"})
    except Exception as error:
        connection.send(
            {
                "kind": "error",
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        connection.close()


def _phase_category(phase_job):
    if phase_job in GENERIC_PRIMARY_PHASES or phase_job == "initial_book_construction":
        return "primary"
    if phase_job.startswith("sell_operation_") or phase_job.startswith(
        "total_application_sell_"
    ):
        return "primary"
    if phase_job in ("latency", "memory", "state_peaks", "counters", "profile"):
        return phase_job
    raise ValueError(f"unknown benchmark phase {phase_job!r}")


def _phase_definition_id(phase_job):
    if phase_job.startswith("sell_operation_"):
        return f"primary-{phase_job}-v1"
    if phase_job.startswith("total_application_sell_"):
        return f"primary-{phase_job}-v1"
    if phase_job in PHASE_DEFINITION_IDS:
        return PHASE_DEFINITION_IDS[phase_job]
    raise ValueError(f"unknown benchmark phase {phase_job!r}")


def _phase_source_objects(phase_job):
    primary_sources = {
        "input_read_parse": ("_timing_phase", "_measure_input_parse", "load_events"),
        "empty_engine_construction": (
            "_timing_phase",
            "_measure_constructor",
        ),
        "engine_replay": (
            "_timing_phase",
            "_measure_engine_replay",
            "replay_without_history",
        ),
        "total_application": (
            "_timing_phase",
            "_measure_total_application",
            "load_events",
            "replay_without_history",
        ),
        "initial_book_construction": (
            "_timing_phase",
            "_measure_initial_book",
            "_build_book",
        ),
    }
    if phase_job.startswith("sell_operation_"):
        names = ("_timing_phase", "_measure_sell_operation", "_build_book")
    elif phase_job.startswith("total_application_sell_"):
        names = (
            "_timing_phase",
            "_measure_total_sell",
            "load_events",
            "_build_book",
        )
    elif phase_job in primary_sources:
        names = primary_sources[phase_job]
    elif phase_job == "latency":
        names = ("_latency_replay", "percentile_nearest_rank", "replay_without_history")
    elif phase_job == "memory":
        names = ("_memory_replay", "_state_checkpoint", "book_state_counts")
    elif phase_job == "state_peaks":
        names = ("state_peak_replay", "EventResultBookkeeping")
    elif phase_job == "counters":
        names = ("counter_replay", "_price_visits", "book_state_counts")
    elif phase_job == "profile":
        names = ("_profile_replay", "replay_without_history")
    else:
        raise ValueError(f"unknown benchmark phase {phase_job!r}")

    objects = []
    for name in names:
        if hasattr(_metrics, name):
            objects.append(getattr(_metrics, name))
        else:
            objects.append(globals()[name])
    return objects


def _phase_definition_hash(phase_job):
    sources = [inspect.getsource(obj) for obj in _phase_source_objects(phase_job)]
    definition = {
        "definition_id": _phase_definition_id(phase_job),
        "sources": sources,
    }
    encoded = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _phase_budget_seconds(phase_job, settings):
    return settings["phase_budgets"][_phase_category(phase_job)]


def _phase_settings_snapshot(phase_job, case, settings):
    category = _phase_category(phase_job)
    snapshot = {
        "event_count": case["event_count"],
        "generator_settings": case["generator_settings"],
        "input_checksums": case["input_checksums"],
    }
    if category == "primary":
        snapshot["timing_repeats"] = settings["timing_repeats"]
        if case["experiment"] == "fixed_liquidation":
            snapshot["sell_quantities"] = case["sell_quantities"]
    elif category == "latency":
        snapshot["latency_definition"] = "event-position-raw-v1"
    elif category == "memory":
        snapshot["memory_checkpoint_fractions"] = [0.25, 0.5, 0.75, 1.0]
    elif category == "state_peaks":
        snapshot["count_source"] = "accepted-event-results"
    elif category == "counters":
        snapshot["counter_max_events"] = settings["counter_max_events"]
    elif category == "profile":
        snapshot["profile_event_limit"] = settings["profile_event_limit"]
    return snapshot


def _phase_jobs(case, settings):
    if case["experiment"] == "fixed_liquidation":
        primary = [
            "input_read_parse",
            "empty_engine_construction",
            "initial_book_construction",
        ]
        for sale_case in case["sell_quantities"]:
            percent = sale_case["percent"]
            primary.extend(
                [
                    f"sell_operation_{percent}pct",
                    f"total_application_sell_{percent}pct",
                ]
            )
    else:
        primary = list(GENERIC_PRIMARY_PHASES)

    jobs = primary + ["state_peaks", "latency", "memory"]
    small_representative = (
        case["event_count"] <= settings["counter_max_events"]
        and case.get("profile")
    )
    if small_representative:
        jobs.append("counters")
    if small_representative:
        jobs.append("profile")
    return jobs


_WINDOWS_MEMORY_API = None
_WINDOWS_MEMORY_COUNTERS = None


def _peak_working_set_bytes(pid):
    if os.name == "nt":
        global _WINDOWS_MEMORY_API
        global _WINDOWS_MEMORY_COUNTERS
        if _WINDOWS_MEMORY_API is None:
            from ctypes import wintypes

            class ProcessMemoryCountersEx(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("Psapi", use_last_error=True)
            kernel32.OpenProcess.argtypes = [
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
            ]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCountersEx),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            _WINDOWS_MEMORY_API = (kernel32, psapi)
            _WINDOWS_MEMORY_COUNTERS = ProcessMemoryCountersEx

        kernel32, psapi = _WINDOWS_MEMORY_API
        counters_type = _WINDOWS_MEMORY_COUNTERS
        handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return None
            raise OSError(error, "OpenProcess failed for memory monitoring")
        try:
            counters = counters_type()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            ):
                raise OSError(
                    ctypes.get_last_error(),
                    "GetProcessMemoryInfo failed",
                )
            return int(counters.PeakWorkingSetSize)
        finally:
            kernel32.CloseHandle(handle)

    if sys.platform.startswith("linux"):
        status_path = Path(f"/proc/{pid}/status")
        try:
            for line in status_path.read_text(encoding="ascii").splitlines():
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) * 1024
        except FileNotFoundError:
            return None
        raise RuntimeError(f"VmHWM not found in {status_path}")
    raise RuntimeError(
        "sampled memory-limit enforcement is supported on Windows and Linux"
    )


def _terminate_worker(process):
    if process.is_alive():
        process.terminate()
        process.join(timeout=3)
    if process.is_alive():
        process.kill()
        process.join(timeout=3)


def _write_jsonl_line(stream, value):
    stream.write(json.dumps(value, separators=(",", ":"), sort_keys=True))
    stream.write("\n")
    stream.flush()


def _receive_worker_message(connection, timeout=0):
    try:
        if not connection.poll(timeout):
            return None
        return connection.recv()
    except (EOFError, OSError) as error:
        return {
            "kind": "ipc_error",
            "error": f"{type(error).__name__}: {error}",
        }


def _config_id(case, version):
    case_id = case["case_id"].replace(
        "queue_concentration_prices", "queue_prices", 1
    )
    return f"{case_id}__{version}".replace("/", "_").replace("\\", "_")


def _next_attempt(records_dir, config_id):
    records_dir = Path(records_dir)
    attempt = 1
    while any(
        records_dir.glob(f"{config_id}__attempt_{attempt:03d}*")
    ):
        attempt += 1
    return attempt


def _phase_row_name(phase_job):
    return {
        "latency": "latency_summary",
        "state_peaks": "state_peaks",
        "counters": "counters",
        "memory": "memory",
        "profile": "profile",
    }.get(phase_job, phase_job)


def _phase_rows_complete(phase_job, rows, case, settings, run_dir):
    row_name = _phase_row_name(phase_job)
    matching = [
        row for row in rows
        if row.get("phase") == row_name and row.get("status") == "completed"
    ]
    if _phase_category(phase_job) == "primary":
        repeats = sorted(
            row.get("repeat") for row in matching
            if isinstance(row.get("repeat"), int)
        )
        summaries = [
            row for row in rows
            if row.get("phase") == f"{row_name}_summary"
            and row.get("status") == "completed"
        ]
        return (
            repeats == list(range(1, TIMING_REPEATS + 1))
            and len(summaries) == 1
            and len(summaries[0].get("raw_repeats_seconds", ()))
            == TIMING_REPEATS
        ), "requires five completed repeats and one matching summary"

    if phase_job == "latency":
        if len(matching) != 1:
            return False, "requires one completed latency summary"
        row = matching[0]
        raw_path = row.get("latency_raw_path")
        artifact = Path(run_dir) / raw_path if raw_path else None
        if row.get("latency_raw_count") != case["event_count"]:
            return False, "raw latency count does not equal event count"
        if artifact is None or not artifact.is_file():
            return False, "raw latency artifact is missing"
        return True, "summary and full raw latency artifact are present"

    if phase_job == "memory":
        expected_positions = {
            max(1, math.ceil(case["event_count"] * fraction))
            for fraction in (0.25, 0.5, 0.75, 1.0)
        }
        if case["experiment"] == "fixed_liquidation":
            expected_per_sale = expected_positions | {
                case["event_count"] - 1
            }
            expected = {
                (percent, position)
                for percent in (10, 100, 200)
                for position in expected_per_sale
            }
            actual = {
                (row.get("sell_percent"), row.get("event_position"))
                for row in matching
            }
            return actual == expected, "requires all memory checkpoints for each sale size"
        actual = {row.get("event_position") for row in matching}
        return actual == expected_positions, "requires all four stream checkpoints"

    if phase_job == "profile":
        if len(matching) != 1:
            return False, "requires one completed profile row"
        row = matching[0]
        expected_events = min(
            settings["profile_event_limit"], case["event_count"]
        )
        if row.get("profiled_event_count") != expected_events:
            return False, "profiled event count differs from configured limit"
        paths = (row.get("profile_data_path"), row.get("profile_text_path"))
        if any(not path or not (Path(run_dir) / path).is_file() for path in paths):
            return False, "profile artifact is missing"
        return True, "bounded profile outputs are present"

    if len(matching) != 1:
        return False, "requires one completed diagnostic row"
    if phase_job == "state_peaks" and matching[0].get(
        "state_peak_method"
    ) != "event_result_shadow_bookkeeping":
        return False, "state peaks were not derived from the event-result ledger"
    if phase_job == "counters" and not matching[0].get(
        "inferred_operation_counts_are_estimates"
    ):
        return False, "counter estimates are not labelled as estimates"
    return True, "one completed diagnostic row is present"


def _phase_candidates(records_dir, config_id):
    records_dir = Path(records_dir)
    candidates = []
    seen_attempts = set()
    for path in records_dir.glob(f"{config_id}__attempt_*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("config_id") != config_id:
            continue
        attempt = record.get("attempt")
        candidates.append(
            {
                "source": _relative_path(path),
                "attempt": attempt,
                "rows": record.get("rows", []),
                "case": record.get("case"),
                "record": record,
            }
        )
        if isinstance(attempt, int):
            seen_attempts.add(attempt)

    for path in records_dir.glob(f"{config_id}__attempt_*.progress.jsonl"):
        stem = path.name.split("__attempt_", 1)[-1]
        try:
            attempt = int(stem[:3])
        except ValueError:
            continue
        if attempt in seen_attempts:
            continue
        rows = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if item.get("kind") in ("row", "worker_stop"):
                    rows.append(item["row"])
        except (OSError, json.JSONDecodeError, KeyError):
            continue
        candidates.append(
            {
                "source": _relative_path(path),
                "attempt": attempt,
                "rows": rows,
                "case": None,
                "record": None,
            }
        )
    return sorted(
        candidates,
        key=lambda item: (item["attempt"] or 0, item["source"]),
        reverse=True,
    )


def _legacy_phase_allowed(phase_job, code_hashes):
    return (
        phase_job not in ("counters", "state_peaks")
        and code_hashes.get("run_benchmarks.py") == LEGACY_RUNNER_SHA256
        and code_hashes.get("metrics.py") == LEGACY_METRICS_SHA256
    )


def _candidate_phase_reasons(
    phase_job, candidate, case, version, settings, run_dir, current_hashes
):
    reasons = []
    rows = candidate["rows"]
    row_name = _phase_row_name(phase_job)
    matching = [
        row for row in rows
        if row.get("phase") in (row_name, f"{row_name}_summary")
    ]
    if not matching:
        return ["no saved rows for this phase"]

    if candidate["case"] is not None and candidate["case"] != _case_manifest(case):
        reasons.append("saved workload settings/case manifest differ")
    for row in matching:
        if row.get("version") != version:
            reasons.append("implementation version differs")
            break
        if row.get("event_count") != case["event_count"]:
            reasons.append("event count differs")
            break
        if row.get("generator_settings") != case["generator_settings"]:
            reasons.append("generator settings differ")
            break
        if row.get("input_checksums") != case["input_checksums"]:
            reasons.append("input checksum differs")
            break
        if row.get("scenario") != case["scenario"] or row.get("seed") != case["seed"]:
            reasons.append("scenario or seed differs")
            break

    code_hashes = matching[0].get("code_hashes", {})
    engine_hash_key = f"{version}.py"
    if code_hashes.get(engine_hash_key) != current_hashes.get(engine_hash_key):
        reasons.append(f"{engine_hash_key} hash differs")
    if (
        case["generator_settings"].get("generator") == "generate_orders.py"
        and code_hashes.get("generate_orders.py")
        != current_hashes.get("generate_orders.py")
    ):
        reasons.append("workload generator hash differs")

    definition_hash = _phase_definition_hash(phase_job)
    if matching[0].get("measurement_definition_hash"):
        if matching[0].get("measurement_definition_id") != _phase_definition_id(
            phase_job
        ):
            reasons.append("measurement definition ID differs")
        if matching[0].get("measurement_definition_hash") != definition_hash:
            reasons.append("measurement definition hash differs")
        if matching[0].get("phase_settings") != _phase_settings_snapshot(
            phase_job, case, settings
        ):
            reasons.append("phase settings differ")
    elif not _legacy_phase_allowed(phase_job, code_hashes):
        reasons.append(
            "legacy runner/metrics hashes are not an approved definition"
        )

    complete, completeness_reason = _phase_rows_complete(
        phase_job, rows, case, settings, run_dir
    )
    if not complete:
        reasons.append(completeness_reason)
    return list(dict.fromkeys(reasons))


def _build_continuation_plan(run_dir, cases, settings):
    records_dir = Path(run_dir) / "records"
    current_hashes = _code_hashes()
    configs = []
    for case in cases:
        for version in VERSIONS:
            config_id = _config_id(case, version)
            candidates = _phase_candidates(records_dir, config_id)
            phase_plans = []
            for phase_job in _phase_jobs(case, settings):
                assessments = []
                selected = None
                for candidate in candidates:
                    reasons = _candidate_phase_reasons(
                        phase_job,
                        candidate,
                        case,
                        version,
                        settings,
                        run_dir,
                        current_hashes,
                    )
                    assessment = {
                        "source": candidate["source"],
                        "attempt": candidate["attempt"],
                        "reusable": not reasons,
                        "reasons": reasons,
                    }
                    assessments.append(assessment)
                    if not reasons and selected is None:
                        selected = assessment
                if selected:
                    phase_plans.append(
                        {
                            "phase": phase_job,
                            "status": "reusable",
                            "budget_seconds": _phase_budget_seconds(
                                phase_job, settings
                            ),
                            "source": selected["source"],
                            "attempt": selected["attempt"],
                            "reason": (
                                "input, engine code, phase definition, settings, "
                                "and complete measurement set match"
                            ),
                            "candidate_assessments": assessments,
                        }
                    )
                else:
                    phase_plans.append(
                        {
                            "phase": phase_job,
                            "status": (
                                "incompatible" if assessments else "pending"
                            ),
                            "budget_seconds": _phase_budget_seconds(
                                phase_job, settings
                            ),
                            "reason": (
                                "no compatible complete phase; execute as a new "
                                "phase attempt"
                            ),
                            "candidate_assessments": assessments,
                        }
                    )
            configs.append(
                {
                    "config_id": config_id,
                    "case": _case_manifest(case),
                    "version": version,
                    "phases": phase_plans,
                }
            )
    return {
        "schema_version": 1,
        "run_id": Path(run_dir).name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
        "configs": configs,
    }


def _write_continuation_plan(run_dir, plan):
    directory = Path(run_dir) / "continuation_plans"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"plan_{timestamp}.json"
    _json_write_exclusive(path, plan)
    return path


def _continuation_counts(plan):
    counts = {}
    for config in plan["configs"]:
        for phase in config["phases"]:
            status = phase["status"]
            counts[status] = counts.get(status, 0) + 1
    return counts


def _execution_priority(case):
    experiment_priority = {
        "fixed_liquidation": 0,
        "queue_concentration": 1,
        "cancellation_churn": 2,
        "workload_replay": 3,
    }
    scenario_priority = {
        scenario: index for index, scenario in enumerate(SCENARIOS)
    }
    return (
        experiment_priority[case["experiment"]],
        case["event_count"],
        scenario_priority.get(case["scenario"], 0),
        case.get("seed", 0),
    )


def _row_common(
    case, version, environment, code_hashes, limits, phase_job, settings
):
    return {
        "version": version,
        "experiment": case["experiment"],
        "scenario": case["scenario"],
        "seed": case.get("seed"),
        "event_count": case["event_count"],
        "generator_settings": case["generator_settings"],
        "input_checksums": case["input_checksums"],
        "active_order_peak": None,
        "occupied_price_level_peak": None,
        "requested_sell_qty_units": None,
        "fill_count": None,
        "phase": None,
        "repeat": None,
        "elapsed_seconds": None,
        "traced_current_bytes": None,
        "traced_peak_bytes": None,
        "status": None,
        "environment": environment,
        "code_hashes": code_hashes,
        "time_limit_seconds": limits["time_limit_seconds"],
        "phase_budget_seconds": limits["time_limit_seconds"],
        "memory_limit_mib": limits["memory_limit_mib"],
        "measurement_definition_id": _phase_definition_id(phase_job),
        "measurement_definition_hash": _phase_definition_hash(phase_job),
        "phase_settings": _phase_settings_snapshot(
            phase_job, case, settings
        ),
    }


def _decorate_row(row, common, run_dir):
    decorated = dict(common)
    decorated.update(row)
    for path_field in ("latency_raw_path", "profile_data_path", "profile_text_path"):
        if decorated.get(path_field):
            try:
                decorated[path_field] = str(
                    Path(decorated[path_field]).resolve().relative_to(run_dir)
                )
            except ValueError:
                pass
    return decorated


def _run_one_phase(
    run_dir, case, version, phase_job, attempt, settings, budget_seconds=None
):
    records_dir = Path(run_dir) / "records"
    artifacts_root = Path(run_dir) / "artifacts"
    records_dir.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    config_id = _config_id(case, version)
    attempt_name = f"{config_id}__attempt_{attempt:03d}"
    phase_stem = f"{attempt_name}__phase_{phase_job}"
    progress_path = records_dir / f"{phase_stem}.progress.jsonl"
    result_path = records_dir / f"{phase_stem}.json"
    artifact_dir = artifacts_root / attempt_name / phase_job
    artifact_dir.mkdir(parents=True, exist_ok=False)

    environment = _environment_snapshot()
    code_hashes = _code_hashes()
    limits = {
        "time_limit_seconds": (
            _phase_budget_seconds(phase_job, settings)
            if budget_seconds is None else budget_seconds
        ),
        "memory_limit_mib": settings["memory_limit_mib"],
        "memory_limit_bytes": int(
            settings["memory_limit_mib"] * 1024 * 1024
        ),
    }
    common = _row_common(
        case, version, environment, code_hashes, limits, phase_job, settings
    )
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_measure_worker,
        args=(
            child_connection,
            case,
            version,
            TIMING_REPEATS,
            str(artifact_dir),
            settings["profile_event_limit"],
            phase_job,
            settings,
        ),
        name=f"benchmark-{config_id}",
    )

    rows = []
    worker_message = None
    stop_status = None
    stop_error = None
    started = time.monotonic()
    peak_working_set = None
    with progress_path.open("x", encoding="utf-8", newline="\n") as progress:
        process.start()
        child_connection.close()
        try:
            try:
                sampled_memory = _peak_working_set_bytes(process.pid)
                if sampled_memory is not None:
                    peak_working_set = sampled_memory
                    if sampled_memory > limits["memory_limit_bytes"]:
                        stop_status = "stopped_memory_limit"
            except (OSError, RuntimeError) as error:
                stop_status = "error"
                stop_error = (
                    f"memory monitor failed: {type(error).__name__}: {error}"
                )
            while process.is_alive():
                if stop_status is not None:
                    break
                elapsed = time.monotonic() - started
                remaining = limits["time_limit_seconds"] - elapsed
                if remaining <= 0:
                    stop_status = "stopped_timeout"
                    break
                message = _receive_worker_message(
                    parent_connection, min(MEMORY_POLL_SECONDS, remaining)
                )
                if message is not None:
                    if message["kind"] == "row":
                        row = _decorate_row(message["row"], common, Path(run_dir))
                        row["measurement_phase"] = phase_job
                        rows.append(row)
                        _write_jsonl_line(progress, {"kind": "row", "row": row})
                    elif message["kind"] == "error":
                        worker_message = message
                        stop_status = "error"
                        break
                    elif message["kind"] == "done":
                        if (
                            time.monotonic() - started
                            >= limits["time_limit_seconds"]
                        ):
                            stop_status = "stopped_timeout"
                        else:
                            worker_message = message
                        break
                    elif message["kind"] == "ipc_error":
                        worker_message = message
                        stop_status = "error"
                        stop_error = message["error"]
                        break

                elapsed = time.monotonic() - started
                if elapsed >= limits["time_limit_seconds"]:
                    stop_status = "stopped_timeout"
                    break

                try:
                    sampled_memory = _peak_working_set_bytes(process.pid)
                except (OSError, RuntimeError) as error:
                    stop_status = "error"
                    stop_error = (
                        f"memory monitor failed: {type(error).__name__}: {error}"
                    )
                    break
                if sampled_memory is not None:
                    peak_working_set = max(
                        peak_working_set or 0, sampled_memory
                    )
                    if sampled_memory > limits["memory_limit_bytes"]:
                        stop_status = "stopped_memory_limit"
                        break
            if stop_status is not None and process.is_alive():
                _terminate_worker(process)
            else:
                process.join(timeout=1)
                if process.is_alive():
                    stop_status = "error"
                    stop_error = "worker did not exit after sending completion"
                    _terminate_worker(process)

            while True:
                message = _receive_worker_message(parent_connection)
                if message is None or message["kind"] == "ipc_error":
                    if (
                        message is not None
                        and worker_message is None
                        and stop_status is None
                    ):
                        worker_message = message
                        stop_status = "error"
                        stop_error = message["error"]
                    break
                if message["kind"] == "row":
                    row = _decorate_row(message["row"], common, Path(run_dir))
                    row["measurement_phase"] = phase_job
                    rows.append(row)
                    _write_jsonl_line(progress, {"kind": "row", "row": row})
                elif message["kind"] == "error":
                    worker_message = message
                    stop_status = "error"
                elif message["kind"] == "done":
                    worker_message = message
        finally:
            parent_connection.close()
            if process.is_alive():
                _terminate_worker(process)

    duration_until_stop = time.monotonic() - started
    if stop_status is None:
        if worker_message and worker_message.get("kind") == "done":
            status = "completed"
        elif worker_message and worker_message.get("kind") == "error":
            status = "error"
        elif process.exitcode == 0:
            status = "completed"
        else:
            status = "error"
    else:
        status = stop_status

    failure = None
    if worker_message and worker_message.get("kind") == "error":
        failure = {
            "error_type": worker_message.get("error_type"),
            "error": worker_message.get("error"),
            "traceback": worker_message.get("traceback"),
        }
    elif stop_error:
        failure = {"error": stop_error}
    elif status != "completed":
        failure = {
            "message": (
                "worker stopped at its enforced wall-time limit"
                if status == "stopped_timeout"
                else "worker exceeded sampled process memory limit"
                if status == "stopped_memory_limit"
                else "worker exited without a completion message"
            ),
            "duration_until_stop_seconds": duration_until_stop,
            "peak_working_set_bytes_observed": peak_working_set,
        }
    if status != "completed":
        stop_row = stopped_phase_row(
            status, duration_until_stop, peak_working_set
        )
        decorated_stop_row = _decorate_row(stop_row, common, Path(run_dir))
        decorated_stop_row["measurement_phase"] = phase_job
        rows.append(decorated_stop_row)
        with progress_path.open("a", encoding="utf-8", newline="\n") as progress:
            _write_jsonl_line(
                progress, {"kind": "worker_stop", "row": decorated_stop_row}
            )

    record = {
        "record_type": "phase_attempt",
        "config_id": config_id,
        "attempt": attempt,
        "phase_job": phase_job,
        "measurement_definition_id": _phase_definition_id(phase_job),
        "measurement_definition_hash": _phase_definition_hash(phase_job),
        "phase_settings": _phase_settings_snapshot(
            phase_job, case, settings
        ),
        "status": status,
        "case": _case_manifest(case),
        "version": version,
        "time_limit_seconds": limits["time_limit_seconds"],
        "phase_budget_seconds": limits["time_limit_seconds"],
        "memory_limit_mib": limits["memory_limit_mib"],
        "duration_until_stop_seconds": duration_until_stop,
        "peak_working_set_bytes_observed": peak_working_set,
        "failure": failure,
        "rows": rows,
        "progress_file": _relative_path(progress_path),
        "artifact_directory": _relative_path(artifact_dir),
        "record_file": _relative_path(result_path),
    }
    _json_write_exclusive(result_path, record)
    return record


def _record_unstarted_phase(
    run_dir, case, version, phase_job, attempt, settings, reason
):
    records_dir = Path(run_dir) / "records"
    artifacts_root = Path(run_dir) / "artifacts"
    config_id = _config_id(case, version)
    attempt_name = f"{config_id}__attempt_{attempt:03d}"
    phase_stem = f"{attempt_name}__phase_{phase_job}"
    progress_path = records_dir / f"{phase_stem}.progress.jsonl"
    result_path = records_dir / f"{phase_stem}.json"
    artifact_dir = artifacts_root / attempt_name / phase_job
    records_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=False)

    phase_limit = _phase_budget_seconds(phase_job, settings)
    common = _row_common(
        case,
        version,
        _environment_snapshot(),
        _code_hashes(),
        {
            "time_limit_seconds": phase_limit,
            "memory_limit_mib": settings["memory_limit_mib"],
        },
        phase_job,
        settings,
    )
    row = _decorate_row(
        stopped_phase_row("stopped_timeout", 0, None),
        common,
        Path(run_dir),
    )
    row.update(
        {
            "measurement_phase": phase_job,
            "status_reason": reason,
        }
    )
    with progress_path.open("x", encoding="utf-8", newline="\n") as progress:
        _write_jsonl_line(progress, {"kind": "worker_stop", "row": row})

    record = {
        "record_type": "phase_attempt",
        "config_id": config_id,
        "attempt": attempt,
        "phase_job": phase_job,
        "measurement_definition_id": _phase_definition_id(phase_job),
        "measurement_definition_hash": _phase_definition_hash(phase_job),
        "phase_settings": _phase_settings_snapshot(
            phase_job, case, settings
        ),
        "status": "stopped_timeout",
        "case": _case_manifest(case),
        "version": version,
        "time_limit_seconds": phase_limit,
        "phase_budget_seconds": phase_limit,
        "memory_limit_mib": settings["memory_limit_mib"],
        "duration_until_stop_seconds": 0,
        "peak_working_set_bytes_observed": None,
        "failure": {"message": reason},
        "rows": [row],
        "progress_file": _relative_path(progress_path),
        "artifact_directory": _relative_path(artifact_dir),
        "record_file": _relative_path(result_path),
    }
    _json_write_exclusive(result_path, record)
    return record


def _run_one_configuration(run_dir, case, version, settings, phase_plan=None):
    records_dir = Path(run_dir) / "records"
    config_id = _config_id(case, version)
    attempt = _next_attempt(records_dir, config_id)
    attempt_name = f"{config_id}__attempt_{attempt:03d}"
    planned_phases = {
        item["phase"]: item
        for item in (phase_plan or {}).get("phases", [])
    }
    phase_statuses = {}
    rows = []
    category_elapsed = {}

    for phase_job in _phase_jobs(case, settings):
        planned = planned_phases.get(phase_job)
        if planned and planned["status"] == "reusable":
            phase_statuses[phase_job] = {
                "status": "reused",
                "source": planned["source"],
                "reason": planned["reason"],
            }
            continue

        category = _phase_category(phase_job)
        category_budget = _phase_budget_seconds(phase_job, settings)
        remaining_budget = category_budget - category_elapsed.get(category, 0)
        if remaining_budget <= 0:
            result = _record_unstarted_phase(
                run_dir,
                case,
                version,
                phase_job,
                attempt,
                settings,
                f"{category} phase budget exhausted before worker start",
            )
        else:
            result = _run_one_phase(
                run_dir,
                case,
                version,
                phase_job,
                attempt,
                settings,
                remaining_budget,
            )
            category_elapsed[category] = (
                category_elapsed.get(category, 0)
                + result["duration_until_stop_seconds"]
            )
        phase_statuses[phase_job] = {
            "status": result["status"],
            "record": result["record_file"],
            "reuse_assessment": planned,
        }
        rows.extend(result["rows"])

    successful = {"completed", "reused"}
    status = (
        "completed"
        if all(item["status"] in successful for item in phase_statuses.values())
        else "partial"
    )
    record = {
        "record_type": "configuration_attempt",
        "config_id": config_id,
        "attempt": attempt,
        "status": status,
        "case": _case_manifest(case),
        "version": version,
        "phase_statuses": phase_statuses,
        "rows": rows,
        "continuation_plan": phase_plan,
    }
    summary_path = records_dir / f"{attempt_name}.json"
    record["record_file"] = _relative_path(summary_path)
    _json_write_exclusive(summary_path, record)
    return record


def _parse_int_list(value, option):
    try:
        numbers = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as error:
        raise ValueError(f"{option} must be comma-separated integers") from error
    if not numbers or any(number <= 0 for number in numbers):
        raise ValueError(f"{option} values must be positive integers")
    return numbers


def _settings_from_args(args):
    smoke = args.smoke
    settings = {
        "profile": "smoke" if smoke else "full",
        "event_sizes": [25] if smoke else [1000, 10000, 100000],
        "seeds": [42] if smoke else [42, 43, 44],
        "scenarios": list(SCENARIOS),
        "levels": 1000,
        "fixed_book_orders": 40 if smoke else 1000,
        "queue_orders": 1000 if smoke else 10000,
        "churn_cycles": 20 if smoke else 5000,
        "parity_event_limit": 1000,
        "profile_event_limit": 2000,
        "time_limit_seconds": 60 if smoke else 300,
        "memory_limit_mib": 2048 if smoke else 4096,
        "counter_max_events": 1500,
        "timing_repeats": TIMING_REPEATS,
        "memory_monitor_poll_seconds": MEMORY_POLL_SECONDS,
    }
    phase_budgets = dict(
        SMOKE_PHASE_BUDGETS if smoke else DEFAULT_PHASE_BUDGETS
    )
    if args.events:
        settings["event_sizes"] = _parse_int_list(args.events, "--events")
    if args.seeds:
        settings["seeds"] = _parse_int_list(args.seeds, "--seeds")
    if args.scenarios:
        scenarios = [item.strip() for item in args.scenarios.split(",")]
        if not scenarios or any(item not in SCENARIOS for item in scenarios):
            raise ValueError(f"--scenarios values must be chosen from {SCENARIOS}")
        settings["scenarios"] = scenarios
    for option, setting in (
        ("levels", "levels"),
        ("fixed_book_orders", "fixed_book_orders"),
        ("queue_orders", "queue_orders"),
        ("churn_cycles", "churn_cycles"),
        ("parity_event_limit", "parity_event_limit"),
        ("profile_event_limit", "profile_event_limit"),
    ):
        value = getattr(args, option)
        if value is not None:
            settings[setting] = value
    if args.time_limit_seconds is not None:
        settings["time_limit_seconds"] = args.time_limit_seconds
        phase_budgets = {
            phase: args.time_limit_seconds for phase in phase_budgets
        }
    for phase in phase_budgets:
        option = f"{phase}_time_limit_seconds"
        value = getattr(args, option, None)
        if value is not None:
            phase_budgets[phase] = value
    settings["phase_budgets"] = phase_budgets
    settings["time_limit_seconds"] = phase_budgets["primary"]
    if args.memory_limit_mib is not None:
        settings["memory_limit_mib"] = args.memory_limit_mib
    positive = (
        "levels",
        "fixed_book_orders",
        "queue_orders",
        "churn_cycles",
        "parity_event_limit",
        "profile_event_limit",
        "time_limit_seconds",
        "memory_limit_mib",
        "counter_max_events",
    )
    if any(settings[key] <= 0 for key in positive):
        raise ValueError("sizes and resource limits must be positive")
    if settings["levels"] >= 6000000:
        raise ValueError("--levels must be less than 6,000,000")
    if not math.isfinite(settings["time_limit_seconds"]):
        raise ValueError("--time-limit-seconds must be finite")
    if not math.isfinite(settings["memory_limit_mib"]):
        raise ValueError("--memory-limit-mib must be finite")
    if any(
        not math.isfinite(value) or value <= 0
        for value in settings["phase_budgets"].values()
    ):
        raise ValueError("phase time limits must be positive finite values")
    if len(set(settings["event_sizes"])) != len(settings["event_sizes"]):
        raise ValueError("--events must not contain duplicate sizes")
    if len(set(settings["seeds"])) != len(settings["seeds"]):
        raise ValueError("--seeds must not contain duplicates")
    if len(set(settings["scenarios"])) != len(settings["scenarios"]):
        raise ValueError("--scenarios must not contain duplicates")
    return settings


def _argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--resume")
    parser.add_argument("--events", help="comma-separated event sizes")
    parser.add_argument("--seeds", help="comma-separated seeds")
    parser.add_argument("--scenarios", help="comma-separated scenario names")
    parser.add_argument("--levels", type=int)
    parser.add_argument("--fixed-book-orders", type=int)
    parser.add_argument("--queue-orders", type=int)
    parser.add_argument("--churn-cycles", type=int)
    parser.add_argument("--parity-event-limit", type=int)
    parser.add_argument("--profile-event-limit", type=int)
    parser.add_argument("--time-limit-seconds", type=float)
    parser.add_argument("--primary-time-limit-seconds", type=float)
    parser.add_argument("--latency-time-limit-seconds", type=float)
    parser.add_argument("--memory-time-limit-seconds", type=float)
    parser.add_argument("--state-peaks-time-limit-seconds", type=float)
    parser.add_argument(
        "--counter-time-limit-seconds",
        "--counters-time-limit-seconds",
        dest="counters_time_limit_seconds",
        type=float,
    )
    parser.add_argument("--profile-time-limit-seconds", type=float)
    parser.add_argument("--memory-limit-mib", type=float)
    parser.add_argument(
        "--plan-resume",
        action="store_true",
        help="write a phase reuse plan without starting benchmark workers",
    )
    return parser


def _apply_phase_budget_args(settings, args):
    budgets = dict(settings.get("phase_budgets", {}))
    settings.setdefault("counter_max_events", 1500)
    legacy_budget = settings.get(
        "time_limit_seconds",
        60 if settings.get("profile") == "smoke" else 300,
    )
    for phase, default in DEFAULT_PHASE_BUDGETS.items():
        budgets.setdefault(phase, legacy_budget if phase in (
            "primary", "latency", "memory", "state_peaks"
        ) else default)

    if args.time_limit_seconds is not None:
        budgets = {phase: args.time_limit_seconds for phase in budgets}
    for phase in budgets:
        value = getattr(args, f"{phase}_time_limit_seconds", None)
        if value is not None:
            budgets[phase] = value
    settings["phase_budgets"] = budgets
    settings["time_limit_seconds"] = budgets["primary"]
    if args.memory_limit_mib is not None:
        settings["memory_limit_mib"] = args.memory_limit_mib

    if any(
        not math.isfinite(value) or value <= 0
        for value in budgets.values()
    ):
        raise ValueError("phase time limits must be positive finite values")
    if (
        not math.isfinite(settings["memory_limit_mib"])
        or settings["memory_limit_mib"] <= 0
    ):
        raise ValueError("memory limit must be a positive finite value")
    return settings


def _resolve_run_path(run_id_or_path):
    candidate = Path(run_id_or_path)
    if not candidate.is_absolute():
        candidate = RUNS_DIR / candidate
    return candidate.resolve()


def _create_run_directory(run_id):
    if not run_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in run_id):
        raise ValueError("run-id may contain only letters, digits, dot, underscore, and hyphen")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "inputs").mkdir()
    (run_dir / "records").mkdir()
    (run_dir / "artifacts").mkdir()
    return run_dir


def _run(args):
    if args.resume and (
        args.run_id
        or args.smoke
        or args.events
        or args.seeds
        or args.scenarios
        or args.levels
        or args.fixed_book_orders
        or args.queue_orders
        or args.churn_cycles
    ):
        raise ValueError(
            "resume uses the saved workload configuration; specify only new limits"
        )
    if args.plan_resume and not args.resume:
        raise ValueError("--plan-resume requires --resume")

    if args.resume:
        run_dir = _resolve_run_path(args.resume)
        metadata_path = run_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        settings = _apply_phase_budget_args(
            dict(metadata["settings"]), args
        )
        cases = build_cases(settings, run_dir)
        current_cases = [_case_manifest(case) for case in cases]
        if current_cases != metadata["cases"]:
            raise ValueError("resume inputs/settings differ from saved run metadata")
        cases = sorted(cases, key=_execution_priority)
    else:
        settings = _settings_from_args(args)
        run_id = args.run_id or (
            f"{settings['profile']}_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        run_dir = _create_run_directory(run_id)
        try:
            cases = build_cases(settings, run_dir)
            parity = [
                {
                    "case_id": case["case_id"],
                    **validate_case(case, settings["parity_event_limit"]),
                }
                for case in cases
            ]
            metadata = {
                "schema_version": 1,
                "run_id": run_id,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "settings": settings,
                "cases": [_case_manifest(case) for case in cases],
                "parity_validation": parity,
                "environment": _environment_snapshot(),
                "code_hashes": _code_hashes(),
            }
            _json_write_exclusive(run_dir / "metadata.json", metadata)
        except Exception as error:
            _json_write_exclusive(
                run_dir / "generation_or_validation_error.json",
                {
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

    if args.resume:
        continuation_plan = _build_continuation_plan(
            run_dir, cases, settings
        )
        plan_path = _write_continuation_plan(run_dir, continuation_plan)
        counts = _continuation_counts(continuation_plan)
        if args.plan_resume:
            print(json.dumps({
                "run_id": run_dir.name,
                "plan_file": _relative_path(plan_path),
                "phase_status_counts": counts,
                "workers_started": 0,
            }, indent=2, sort_keys=True))
            return 0
    else:
        continuation_plan = None

    plans_by_config = {
        config["config_id"]: config
        for config in (continuation_plan or {}).get("configs", [])
    }
    run_statuses = {}
    run_phase_statuses = {}
    for case in cases:
        parity = validate_case(case, settings["parity_event_limit"])
        if parity["status"] != "passed":
            raise AssertionError(f"benchmark input parity failed for {case['case_id']}")
        for version in VERSIONS:
            config_id = _config_id(case, version)
            config_plan = plans_by_config.get(config_id)
            record = _run_one_configuration(
                run_dir, case, version, settings, config_plan
            )
            run_statuses[config_id] = record["status"]
            for phase_status in record["phase_statuses"].values():
                status = phase_status["status"]
                run_phase_statuses[status] = (
                    run_phase_statuses.get(status, 0) + 1
                )
            print(
                f"{config_id}: {record['status']} "
                f"({len(record['phase_statuses'])} phase statuses)"
            )

    status_counts = {}
    for status in run_statuses.values():
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "run_id": run_dir.name,
        "run_directory": str(run_dir),
        "profile": settings["profile"],
        "config_status_counts": status_counts,
        "phase_status_counts": run_phase_statuses,
        "continuation_plan_status_counts": (
            _continuation_counts(continuation_plan)
            if continuation_plan else None
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(status == "completed" for status in run_statuses.values()) else 2


def main(argv=None):
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except Exception as error:
        parser.exit(
            2,
            f"benchmark run failed: {type(error).__name__}: {error}\n",
        )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
