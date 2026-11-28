#!/usr/bin/env python3
"""Run and measure a verified Bitcoin American put scenario."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import psutil

from compiled_backend import (
    compiler_metadata,
    ensure_compiled,
    price_american_put_with_boundary_compiled,
)
from market_data import (
    calibrate_window,
    find_first_exercise,
    load_price_series,
    select_full_history,
    select_last_periods,
)


SUBMISSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = SUBMISSION_DIR.parents[2]
DEFAULT_DATA = REPO_ROOT / "Class3" / "data" / "hourly" / "BTCUSDT.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=True
    )
    return completed.stdout.strip()


def _pricing_args(calibration):
    return (
        calibration.spot,
        calibration.strike,
        calibration.up,
        calibration.down,
        calibration.gross_rate,
        calibration.steps,
    )


def _memory_worker(connection, arguments):
    try:
        result = price_american_put_with_boundary_compiled(*arguments)
        connection.send(
            {
                "status": "ready",
                "pid": os.getpid(),
                "value": result.value,
                "boundary_length": len(result.boundary),
                "boundary_count": sum(x is not None for x in result.boundary),
                "node_updates": result.node_updates,
            }
        )
        connection.recv()  # Keep the required output alive until the final sample.
    except BaseException as exc:  # The parent records and raises worker failures.
        connection.send({"status": "error", "error": repr(exc)})
    finally:
        connection.close()


def measure_peak_rss(arguments, interval_seconds: float):
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe()
    process = context.Process(target=_memory_worker, args=(child_connection, arguments))
    parent_process = psutil.Process(os.getpid())
    process.start()
    child_connection.close()
    child_process = psutil.Process(process.pid)

    child_baseline = None
    child_peak = 0
    aggregate_peak = 0
    sample_count = 0
    payload = None
    while payload is None:
        try:
            child_rss = child_process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            child_rss = 0
        parent_rss = parent_process.memory_info().rss
        if child_baseline is None and child_rss:
            child_baseline = child_rss
        child_peak = max(child_peak, child_rss)
        aggregate_peak = max(aggregate_peak, parent_rss + child_rss)
        sample_count += 1
        if parent_connection.poll():
            payload = parent_connection.recv()
            break
        if not process.is_alive():
            raise RuntimeError("memory worker exited before returning a result")
        time.sleep(interval_seconds)

    # The child is waiting with its result alive. Capture one final sample.
    child_rss = child_process.memory_info().rss
    parent_rss = parent_process.memory_info().rss
    child_peak = max(child_peak, child_rss)
    aggregate_peak = max(aggregate_peak, parent_rss + child_rss)
    sample_count += 1

    if payload.get("status") != "ready":
        process.join(timeout=5)
        raise RuntimeError(f"memory worker failed: {payload.get('error')}")
    parent_connection.send("release")
    parent_connection.close()
    process.join()
    if process.exitcode != 0:
        raise RuntimeError(f"memory worker exit status {process.exitcode}")
    return {
        "method": "psutil RSS sampling of parent plus fresh child process",
        "sampling_interval_seconds": interval_seconds,
        "sample_count": sample_count,
        "child_pid": payload["pid"],
        "child_baseline_rss_bytes": child_baseline,
        "child_peak_rss_bytes": child_peak,
        "child_peak_delta_bytes": (
            child_peak - child_baseline if child_baseline is not None else None
        ),
        "aggregate_peak_rss_bytes": aggregate_peak,
        "required_output_alive_at_final_sample": True,
        "worker_result": payload,
    }


def _write_json_atomic(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _write_boundary_atomic(path: Path, window, boundary, decision) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "t",
                "timestamp_utc",
                "observed_close",
                "boundary_price",
                "at_or_below_boundary",
                "first_exercise",
            ]
        )
        for index, (stamp, observed, limit) in enumerate(
            zip(window.timestamps, window.closes, boundary)
        ):
            writer.writerow(
                [
                    index,
                    stamp.isoformat().replace("+00:00", "Z"),
                    repr(observed),
                    "" if limit is None else repr(limit),
                    limit is not None and observed <= limit,
                    decision.exercised and decision.index == index,
                ]
            )
    os.replace(temporary, path)


def run(
    data_path: Path,
    output_dir: Path,
    repeats: int,
    sample_ms: float,
    window_name: str = "one_year",
):
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    if sample_ms <= 0:
        raise ValueError("sample interval must be positive")

    # Input preparation is deliberately outside timing.
    series = load_price_series(data_path)
    if window_name == "one_year":
        window = select_last_periods(series, 8760)
    elif window_name == "full":
        window = select_full_history(series)
    else:
        raise ValueError("window_name must be 'one_year' or 'full'")
    calibration = calibrate_window(window)
    arguments = _pricing_args(calibration)
    ensure_compiled()

    # A small warm-up validates dispatch without consuming the measured input.
    warmup = price_american_put_with_boundary_compiled(100, 100, 1.2, 0.8, 1.05, 2)
    if f"{warmup.value:.4f}" != "7.9932":
        raise AssertionError("two-period warm-up did not reproduce 7.9932")

    raw_seconds = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        current = price_american_put_with_boundary_compiled(*arguments)
        elapsed = time.perf_counter() - start
        raw_seconds.append(elapsed)
        result = current
    assert result is not None
    decision = find_first_exercise(window, result.boundary, calibration.strike)

    memory = measure_peak_rss(arguments, sample_ms / 1000)
    measured_worker = memory["worker_result"]
    if measured_worker["value"] != result.value:
        raise AssertionError("memory run and timing run produced different values")
    if measured_worker["boundary_length"] != len(result.boundary):
        raise AssertionError("memory run returned a different boundary length")

    output_dir.mkdir(parents=True, exist_ok=True)
    scenario = f"bitcoin_{window_name}"
    json_path = output_dir / f"{scenario}.json"
    boundary_path = output_dir / f"{scenario}_boundary.csv"
    payload = {
        "schema_version": 1,
        "status": "completed",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario,
        "asset": window.symbol,
        "input": {
            "path": str(data_path.resolve()),
            "sha256": series.source_sha256,
            "total_observations": len(series.closes),
            "selected_observations": len(window.closes),
            "steps": window.steps,
            "start_utc": window.timestamps[0].isoformat(),
            "end_utc": window.timestamps[-1].isoformat(),
            "selected_gap_count": len(window.gaps),
        },
        "calibration": asdict(calibration),
        "output": {
            "put_value": result.value,
            "boundary_length": len(result.boundary),
            "boundary_count": sum(x is not None for x in result.boundary),
            "node_updates": result.node_updates,
            "exercise": {
                "exercised": decision.exercised,
                "index": decision.index,
                "timestamp_utc": (
                    decision.timestamp.isoformat() if decision.timestamp else None
                ),
                "observed_price": decision.observed_price,
                "boundary_price": decision.boundary_price,
                "payoff": decision.payoff,
            },
            "boundary_csv": boundary_path.name,
        },
        "timing": {
            "clock": "time.perf_counter",
            "units": "seconds",
            "warmup_calls": 1,
            "repeats": repeats,
            "raw_seconds": raw_seconds,
            "median_seconds": statistics.median(raw_seconds),
            "input_preparation_included": False,
            "required_output_construction_included": True,
        },
        "memory": memory,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "psutil_version": psutil.__version__,
            "process_start_method": "spawn",
            "compiled_backend": compiler_metadata(),
        },
        "provenance": {
            "git_commit": _git("rev-parse", "HEAD"),
            "git_branch": _git("branch", "--show-current"),
            "git_status_porcelain": _git("status", "--porcelain"),
            "american_put_sha256": _sha256(SUBMISSION_DIR / "american_put.py"),
            "market_data_sha256": _sha256(SUBMISSION_DIR / "market_data.py"),
            "runner_sha256": _sha256(Path(__file__).resolve()),
            "compiled_backend_sha256": _sha256(SUBMISSION_DIR / "compiled_backend.py"),
            "kernel_source_sha256": _sha256(SUBMISSION_DIR / "american_put_kernel.c"),
        },
    }
    _write_boundary_atomic(boundary_path, window, result.boundary, decision)
    _write_json_atomic(json_path, payload)
    return payload, json_path, boundary_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=SUBMISSION_DIR / "results")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--sample-ms", type=float, default=10.0)
    parser.add_argument("--window", choices=("one_year", "full"), default="one_year")
    args = parser.parse_args()
    payload, json_path, boundary_path = run(
        args.data, args.output_dir, args.repeats, args.sample_ms, args.window
    )
    output = payload["output"]
    timing = payload["timing"]
    memory = payload["memory"]
    print(f"value={output['put_value']:.10f}")
    print(f"median_seconds={timing['median_seconds']:.6f}")
    print(f"child_peak_rss_bytes={memory['child_peak_rss_bytes']}")
    print(f"aggregate_peak_rss_bytes={memory['aggregate_peak_rss_bytes']}")
    exercise = output["exercise"]
    if exercise["exercised"]:
        print(
            "first_exercise="
            f"{exercise['timestamp_utc']} payoff={exercise['payoff']:.10f}"
        )
    else:
        print("first_exercise=never")
    print(f"results={json_path}")
    print(f"boundary={boundary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
