#!/usr/bin/env python3
"""Run and measure all 40 assets with process-level parallelism."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import csv
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

from batch import prepare_jobs, run_batch_once
from compiled_backend import compiler_metadata, ensure_compiled


SUBMISSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = SUBMISSION_DIR.parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "Class3" / "data" / "hourly"


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


def _result_map(execution):
    return {result.symbol: result.value for result in execution.results}


def _memory_coordinator(connection, jobs, workers):
    try:
        execution = run_batch_once(jobs, workers)
        connection.send(
            {
                "status": "ready",
                "pid": os.getpid(),
                "execution": {
                    "wall_seconds": execution.wall_seconds,
                    "warm_worker_pids": execution.warm_worker_pids,
                    "result_worker_pids": execution.result_worker_pids,
                    "results": [asdict(result) for result in execution.results],
                },
            }
        )
        connection.recv()
    except BaseException as exc:
        connection.send({"status": "error", "error": repr(exc)})
    finally:
        connection.close()


def _sample_process_tree(root_process):
    processes = [root_process]
    try:
        processes.extend(root_process.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        pass
    rss = 0
    pids = []
    for process in processes:
        try:
            rss += process.memory_info().rss
            pids.append(process.pid)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return rss, tuple(sorted(pids))


def measure_batch_peak_rss(jobs, workers: int, interval_seconds: float):
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe()
    process = context.Process(
        target=_memory_coordinator, args=(child_connection, tuple(jobs), workers)
    )
    parent_process = psutil.Process(os.getpid())
    process.start()
    child_connection.close()
    coordinator = psutil.Process(process.pid)

    tree_peak = 0
    parent_plus_tree_peak = 0
    max_live_processes = 0
    observed_pids = set()
    samples = 0
    payload = None
    while payload is None:
        tree_rss, pids = _sample_process_tree(coordinator)
        parent_rss = parent_process.memory_info().rss
        tree_peak = max(tree_peak, tree_rss)
        parent_plus_tree_peak = max(parent_plus_tree_peak, parent_rss + tree_rss)
        max_live_processes = max(max_live_processes, len(pids))
        observed_pids.update(pids)
        samples += 1
        if parent_connection.poll():
            payload = parent_connection.recv()
            break
        if not process.is_alive():
            raise RuntimeError("memory coordinator exited before returning results")
        time.sleep(interval_seconds)

    tree_rss, pids = _sample_process_tree(coordinator)
    parent_rss = parent_process.memory_info().rss
    tree_peak = max(tree_peak, tree_rss)
    parent_plus_tree_peak = max(parent_plus_tree_peak, parent_rss + tree_rss)
    max_live_processes = max(max_live_processes, len(pids))
    observed_pids.update(pids)
    samples += 1
    if payload.get("status") != "ready":
        process.join(timeout=5)
        raise RuntimeError(f"memory coordinator failed: {payload.get('error')}")
    parent_connection.send("release")
    parent_connection.close()
    process.join()
    if process.exitcode != 0:
        raise RuntimeError(f"memory coordinator exit status {process.exitcode}")
    return {
        "method": "psutil RSS sampling of coordinator process tree",
        "sampling_interval_seconds": interval_seconds,
        "sample_count": samples,
        "coordinator_pid": payload["pid"],
        "process_tree_peak_rss_bytes": tree_peak,
        "parent_plus_tree_peak_rss_bytes": parent_plus_tree_peak,
        "max_live_processes": max_live_processes,
        "observed_pids": sorted(observed_pids),
        "worker_output_alive_before_release": True,
        "execution": payload["execution"],
    }


def _write_json_atomic(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _write_values_atomic(path: Path, jobs, results) -> None:
    jobs_by_symbol = {job.symbol: job for job in jobs}
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["symbol", "steps", "spot", "strike", "put_value"])
        for result in results:
            job = jobs_by_symbol[result.symbol]
            writer.writerow(
                [result.symbol, job.steps, repr(job.spot), repr(job.strike),
                 repr(result.value)]
            )
    os.replace(temporary, path)


def run(data_dir, output_dir, window_name, workers, repeats, sample_ms):
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    if sample_ms <= 0:
        raise ValueError("sample interval must be positive")
    prepared = prepare_jobs(data_dir, window_name=window_name)
    ensure_compiled()

    executions = []
    expected_values = None
    for _ in range(repeats):
        execution = run_batch_once(prepared.jobs, workers)
        values = _result_map(execution)
        if expected_values is None:
            expected_values = values
        elif values != expected_values:
            raise AssertionError("batch results changed across timing repeats")
        executions.append(execution)
    memory = measure_batch_peak_rss(
        prepared.jobs, workers, interval_seconds=sample_ms / 1000
    )
    memory_values = {
        result["symbol"]: result["value"]
        for result in memory["execution"]["results"]
    }
    if memory_values != expected_values:
        raise AssertionError("memory run and timing runs produced different values")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario = f"all_assets_{window_name}"
    json_path = output_dir / f"{scenario}.json"
    values_path = output_dir / f"{scenario}_values.csv"
    first_execution = executions[0]
    raw_seconds = [execution.wall_seconds for execution in executions]
    payload = {
        "schema_version": 1,
        "status": "completed",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario,
        "window_name": window_name,
        "asset_count": len(prepared.jobs),
        "workers": workers,
        "inputs": [asdict(item) for item in prepared.inputs],
        "outputs": [asdict(result) for result in first_execution.results],
        "values_csv": values_path.name,
        "timing": {
            "clock": "time.perf_counter",
            "units": "seconds",
            "repeats": repeats,
            "raw_seconds": raw_seconds,
            "median_seconds": statistics.median(raw_seconds),
            "input_preparation_included": False,
            "worker_warmup_included": False,
            "required_output_construction_included": True,
            "executions": [
                {
                    "wall_seconds": execution.wall_seconds,
                    "warm_worker_pids": execution.warm_worker_pids,
                    "result_worker_pids": execution.result_worker_pids,
                    "per_asset": [asdict(result) for result in execution.results],
                }
                for execution in executions
            ],
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
            "thread_limits": {
                name: os.environ.get(name)
                for name in (
                    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"
                )
            },
        },
        "provenance": {
            "git_commit": _git("rev-parse", "HEAD"),
            "git_branch": _git("branch", "--show-current"),
            "git_status_porcelain": _git("status", "--porcelain"),
            "american_put_sha256": _sha256(SUBMISSION_DIR / "american_put.py"),
            "market_data_sha256": _sha256(SUBMISSION_DIR / "market_data.py"),
            "batch_sha256": _sha256(SUBMISSION_DIR / "batch.py"),
            "runner_sha256": _sha256(Path(__file__).resolve()),
            "compiled_backend_sha256": _sha256(SUBMISSION_DIR / "compiled_backend.py"),
            "kernel_source_sha256": _sha256(SUBMISSION_DIR / "american_put_kernel.c"),
        },
    }
    _write_values_atomic(values_path, prepared.jobs, first_execution.results)
    _write_json_atomic(json_path, payload)
    return payload, json_path, values_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=SUBMISSION_DIR / "results")
    parser.add_argument("--window", choices=("one_year", "full"), required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--sample-ms", type=float, default=20.0)
    args = parser.parse_args()
    payload, json_path, values_path = run(
        args.data_dir, args.output_dir, args.window, args.workers,
        args.repeats, args.sample_ms
    )
    print(f"scenario={payload['scenario']}")
    print(f"workers={payload['workers']}")
    print(f"median_seconds={payload['timing']['median_seconds']:.6f}")
    print(
        "process_tree_peak_rss_bytes="
        f"{payload['memory']['process_tree_peak_rss_bytes']}"
    )
    print(f"results={json_path}")
    print(f"values={values_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
