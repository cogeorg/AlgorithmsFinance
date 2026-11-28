#!/usr/bin/env python3
"""Verify CPU scaling and choose a worker count before canonical batch runs."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics

from batch import prepare_jobs, run_batch_once


SUBMISSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = SUBMISSION_DIR.parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "Class3" / "data" / "hourly"


def _parse_workers(raw: str) -> tuple[int, ...]:
    values = tuple(int(item) for item in raw.split(","))
    if not values or any(value <= 0 for value in values) or len(values) != len(set(values)):
        raise argparse.ArgumentTypeError("worker list must contain unique positive integers")
    return values


def _execution_record(execution):
    return {
        "workers": execution.workers,
        "wall_seconds": execution.wall_seconds,
        "warm_worker_pids": execution.warm_worker_pids,
        "result_worker_pids": execution.result_worker_pids,
        "values": {result.symbol: result.value for result in execution.results},
        "per_asset": [asdict(result) for result in execution.results],
    }


def _run_matrix(jobs, worker_counts):
    records = []
    expected = None
    for workers in worker_counts:
        if workers > len(jobs):
            raise ValueError("workers cannot exceed jobs in pilot")
        execution = run_batch_once(jobs, workers)
        record = _execution_record(execution)
        if expected is None:
            expected = record["values"]
        elif record["values"] != expected:
            raise AssertionError("worker-count pilot changed asset values")
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path,
                        default=SUBMISSION_DIR / "results" / "worker_pilot.json")
    parser.add_argument("--one-year-workers", type=_parse_workers, default=(1, 2, 4, 8))
    parser.add_argument("--full-workers", type=_parse_workers, default=(1, 2, 4))
    parser.add_argument("--full-assets", type=int, default=4)
    args = parser.parse_args()

    one_year = prepare_jobs(args.data_dir, window_name="one_year")
    one_year_records = _run_matrix(one_year.jobs, args.one_year_workers)
    full = prepare_jobs(args.data_dir, window_name="full")
    if not 1 <= args.full_assets <= len(full.jobs):
        raise ValueError("full-assets must be between 1 and 40")
    full_jobs = full.jobs[:args.full_assets]
    full_records = _run_matrix(full_jobs, args.full_workers)

    recommended = min(one_year_records, key=lambda item: item["wall_seconds"])["workers"]
    payload = {
        "schema_version": 1,
        "status": "completed",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "one_year_all_assets": one_year_records,
        "full_history_subset": {
            "symbols": [job.symbol for job in full_jobs],
            "records": full_records,
        },
        "recommended_workers": recommended,
        "selection_rule": "lowest measured all-assets one-year wall time",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, args.output)
    for record in one_year_records:
        print(f"one_year workers={record['workers']} seconds={record['wall_seconds']:.6f}")
    for record in full_records:
        print(f"full_subset workers={record['workers']} seconds={record['wall_seconds']:.6f}")
    print(f"recommended_workers={recommended}")
    print(f"results={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
