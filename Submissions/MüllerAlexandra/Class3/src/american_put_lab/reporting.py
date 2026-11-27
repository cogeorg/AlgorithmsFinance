"""CSV output for the required lab tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from collections.abc import Sequence

from .data_io import MarketSeries
from .workflow import AssetAnalysis, ExperimentResult


def _iso(value) -> str:
    return "" if value is None else value.isoformat()


def write_experiment_tables(
    experiments: Sequence[ExperimentResult], output_dir: str | Path
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "01_run_summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "run_label",
                "requested_periods",
                "asset_count",
                "min_periods",
                "max_periods",
                "seconds",
                "peak_bytes",
                "peak_mib",
            ),
        )
        writer.writeheader()
        for result in experiments:
            writer.writerow(
                {
                    "run_label": result.run_label,
                    "requested_periods": "all" if result.requested_periods is None else result.requested_periods,
                    "asset_count": result.asset_count,
                    "min_periods": result.min_periods,
                    "max_periods": result.max_periods,
                    "seconds": f"{result.seconds:.6f}",
                    "peak_bytes": result.peak_bytes,
                    "peak_mib": f"{result.peak_bytes / 2**20:.6f}",
                }
            )

    with (output_dir / "02_asset_results.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "run_label",
                "symbol",
                "periods",
                "window_start_utc",
                "window_end_utc",
                "option_value",
                "first_exercise_date_utc",
                "first_exercise_price",
                "first_exercise_payoff",
            ),
        )
        writer.writeheader()
        for result in experiments:
            for asset in result.assets:
                writer.writerow(
                    {
                        "run_label": result.run_label,
                        "symbol": asset.symbol,
                        "periods": asset.periods,
                        "window_start_utc": asset.window_start.isoformat(),
                        "window_end_utc": asset.window_end.isoformat(),
                        "option_value": f"{asset.option_value:.10f}",
                        "first_exercise_date_utc": _iso(asset.first_exercise_date),
                        "first_exercise_price": "" if asset.first_exercise_price is None else f"{asset.first_exercise_price:.10f}",
                        "first_exercise_payoff": "" if asset.first_exercise_payoff is None else f"{asset.first_exercise_payoff:.10f}",
                    }
                )


def write_boundary_table(
    series: MarketSeries, analysis: AssetAnalysis, output_dir: str | Path
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "03_btc_one_year_boundary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ("time_index", "timestamp_utc", "historical_close", "exercise_boundary")
        )
        for index, (timestamp, price, boundary) in enumerate(
            zip(
                series.timestamps,
                series.prices,
                analysis.pricing.exercise_boundary,
                strict=True,
            )
        ):
            writer.writerow(
                (
                    index,
                    timestamp.isoformat(),
                    f"{price:.10f}",
                    "" if math.isnan(boundary) else f"{boundary:.10f}",
                )
            )
