"""Deterministic process-parallel pricing of independent assets."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import math
import multiprocessing
import os
from pathlib import Path
import time

from compiled_backend import ensure_compiled, price_american_put_compiled
from market_data import (
    calibrate_window,
    load_price_series,
    select_full_history,
    select_last_periods,
)


for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_name, "1")


class BatchInputError(ValueError):
    """Raised before starting worker processes when a batch is invalid."""


@dataclass(frozen=True)
class ModelJob:
    symbol: str
    spot: float
    strike: float
    up: float
    down: float
    gross_rate: float
    steps: int


@dataclass(frozen=True)
class PreparedInput:
    symbol: str
    path: str
    sha256: str
    total_observations: int
    selected_observations: int
    steps: int
    start_utc: str
    end_utc: str
    gap_count: int
    volatility: float
    q: float


@dataclass(frozen=True)
class PreparedBatch:
    window_name: str
    jobs: tuple[ModelJob, ...]
    inputs: tuple[PreparedInput, ...]


@dataclass(frozen=True)
class AssetResult:
    symbol: str
    value: float
    node_updates: int
    pid: int
    kernel_seconds: float


@dataclass(frozen=True)
class BatchExecution:
    results: tuple[AssetResult, ...]
    workers: int
    wall_seconds: float
    warm_worker_pids: tuple[int, ...]
    result_worker_pids: tuple[int, ...]


def _run_job(job: ModelJob) -> AssetResult:
    start = time.perf_counter()
    value = price_american_put_compiled(
        job.spot, job.strike, job.up, job.down, job.gross_rate, job.steps
    )
    elapsed = time.perf_counter() - start
    return AssetResult(
        symbol=job.symbol,
        value=value,
        node_updates=job.steps * (job.steps + 1) // 2,
        pid=os.getpid(),
        kernel_seconds=elapsed,
    )


def _warm_worker(_: int) -> int:
    value = price_american_put_compiled(100, 100, 1.2, 0.8, 1.05, 2)
    if f"{value:.4f}" != "7.9932":
        raise AssertionError("worker warm-up failed the two-period fixture")
    time.sleep(0.05)
    return os.getpid()


def _warm_pool(executor: ProcessPoolExecutor, workers: int) -> tuple[int, ...]:
    pids = set()
    for _ in range(8):
        tokens = range(max(workers * 2, 2))
        pids.update(executor.map(_warm_worker, tokens, chunksize=1))
        if len(pids) >= workers:
            return tuple(sorted(pids))
    raise RuntimeError(f"started only {len(pids)} of {workers} requested workers")


def _validate_batch(jobs: tuple[ModelJob, ...], workers: int) -> None:
    if not jobs:
        raise BatchInputError("at least one job is required")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise BatchInputError("workers must be a positive integer")
    if workers > len(jobs):
        raise BatchInputError("workers cannot exceed the number of jobs")
    symbols = [job.symbol for job in jobs]
    if any(not symbol for symbol in symbols) or len(symbols) != len(set(symbols)):
        raise BatchInputError("job symbols must be nonempty and unique")


def run_batch_once(jobs, workers: int) -> BatchExecution:
    jobs = tuple(jobs)
    _validate_batch(jobs, workers)
    ensure_compiled()
    context = multiprocessing.get_context("spawn")
    executor = ProcessPoolExecutor(max_workers=workers, mp_context=context)
    try:
        warm_pids = _warm_pool(executor, workers)
        start = time.perf_counter()
        results = tuple(executor.map(_run_job, jobs, chunksize=1))
        wall_seconds = time.perf_counter() - start
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    results = tuple(sorted(results, key=lambda result: result.symbol))
    for result in results:
        if not math.isfinite(result.value) or result.value < 0:
            raise ArithmeticError(f"{result.symbol} returned an invalid value")
    return BatchExecution(
        results=results,
        workers=workers,
        wall_seconds=wall_seconds,
        warm_worker_pids=warm_pids,
        result_worker_pids=tuple(sorted({result.pid for result in results})),
    )


def prepare_jobs(data_dir: str | Path, *, window_name: str) -> PreparedBatch:
    data_dir = Path(data_dir).resolve()
    if window_name not in {"one_year", "full"}:
        raise BatchInputError("window_name must be 'one_year' or 'full'")
    paths = sorted(data_dir.glob("*USDT.csv"))
    if len(paths) != 40:
        raise BatchInputError(
            f"expected exactly 40 tracked USDT assets, found {len(paths)}"
        )
    jobs = []
    inputs = []
    for path in paths:
        series = load_price_series(path)
        window = (
            select_last_periods(series, 8760)
            if window_name == "one_year"
            else select_full_history(series)
        )
        calibration = calibrate_window(window)
        jobs.append(
            ModelJob(
                symbol=series.symbol,
                spot=calibration.spot,
                strike=calibration.strike,
                up=calibration.up,
                down=calibration.down,
                gross_rate=calibration.gross_rate,
                steps=calibration.steps,
            )
        )
        inputs.append(
            PreparedInput(
                symbol=series.symbol,
                path=str(path),
                sha256=series.source_sha256,
                total_observations=len(series.closes),
                selected_observations=len(window.closes),
                steps=window.steps,
                start_utc=window.timestamps[0].isoformat(),
                end_utc=window.timestamps[-1].isoformat(),
                gap_count=len(window.gaps),
                volatility=calibration.volatility,
                q=calibration.q,
            )
        )
    return PreparedBatch(window_name, tuple(jobs), tuple(inputs))
