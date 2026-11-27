"""End-to-end analysis and measured experiment orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import gc
from pathlib import Path
from time import perf_counter
import tracemalloc
from collections.abc import Sequence

from .analysis import ExerciseObservation, first_historical_exercise
from .calibration import Calibration, calibrate_tree
from .data_io import MarketSeries, load_hourly_prices
from .pricing import PricingResult, price_american_put


@dataclass(frozen=True)
class AssetAnalysis:
    symbol: str
    periods: int
    window_start: datetime
    window_end: datetime
    strike: float
    calibration: Calibration
    pricing: PricingResult
    first_exercise: ExerciseObservation | None


@dataclass(frozen=True)
class CompactAssetResult:
    symbol: str
    periods: int
    window_start: datetime
    window_end: datetime
    option_value: float
    first_exercise_date: datetime | None
    first_exercise_price: float | None
    first_exercise_payoff: float | None


@dataclass(frozen=True)
class ExperimentResult:
    run_label: str
    requested_periods: int | None
    asset_count: int
    min_periods: int
    max_periods: int
    seconds: float
    peak_bytes: int
    assets: tuple[CompactAssetResult, ...]


def analyze_series(series: MarketSeries, annual_rate: float = 0.04) -> AssetAnalysis:
    calibration = calibrate_tree(series.prices, series.timestamps, annual_rate)
    strike = series.prices[0]
    pricing = price_american_put(
        spot=strike,
        strike=strike,
        up=calibration.up,
        down=calibration.down,
        gross_rate=calibration.gross_rate,
        steps=calibration.periods,
    )
    first_exercise = first_historical_exercise(
        series.prices,
        series.timestamps,
        pricing.exercise_boundary,
        strike,
    )
    return AssetAnalysis(
        symbol=series.symbol,
        periods=series.periods,
        window_start=series.timestamps[0],
        window_end=series.timestamps[-1],
        strike=strike,
        calibration=calibration,
        pricing=pricing,
        first_exercise=first_exercise,
    )


def compact_result(analysis: AssetAnalysis) -> CompactAssetResult:
    exercise = analysis.first_exercise
    return CompactAssetResult(
        symbol=analysis.symbol,
        periods=analysis.periods,
        window_start=analysis.window_start,
        window_end=analysis.window_end,
        option_value=analysis.pricing.value,
        first_exercise_date=None if exercise is None else exercise.timestamp,
        first_exercise_price=None if exercise is None else exercise.price,
        first_exercise_payoff=None if exercise is None else exercise.payoff,
    )


def run_experiment(
    paths: Sequence[str | Path],
    periods: int | None,
    run_label: str,
    annual_rate: float = 0.04,
) -> ExperimentResult:
    """Measure the complete workload in separate timing and memory trials.

    The untraced trial supplies elapsed seconds. A second, traced trial supplies
    peak allocated bytes. Their compact outputs must agree exactly.
    """
    if not paths:
        raise ValueError("an experiment requires at least one asset")

    def execute() -> tuple[CompactAssetResult, ...]:
        compact_assets: list[CompactAssetResult] = []
        for path in paths:
            analysis = analyze_series(load_hourly_prices(path, periods), annual_rate)
            compact_assets.append(compact_result(analysis))
            del analysis
        return tuple(compact_assets)

    gc.collect()
    started = perf_counter()
    assets = execute()
    seconds = perf_counter() - started

    gc.collect()
    tracemalloc.start()
    try:
        memory_trial_assets = execute()
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    if memory_trial_assets != assets:
        raise RuntimeError("timing and memory trials produced different outputs")
    del memory_trial_assets

    observed_periods = [asset.periods for asset in assets]
    return ExperimentResult(
        run_label=run_label,
        requested_periods=periods,
        asset_count=len(assets),
        min_periods=min(observed_periods),
        max_periods=max(observed_periods),
        seconds=seconds,
        peak_bytes=peak_bytes,
        assets=assets,
    )
