from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from american_put_lab.data_io import MarketSeries
from american_put_lab.reporting import write_boundary_table, write_experiment_tables
from american_put_lab.workflow import analyze_series, run_experiment


def _write_prices(path: Path, prices: tuple[float, ...]) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("timestamp_utc", "close"))
        for index, price in enumerate(prices):
            writer.writerow(
                ((start + timedelta(hours=index)).isoformat().replace("+00:00", "Z"), price)
            )


def test_measured_experiment_reports_requested_dimensions_and_compact_assets(tmp_path: Path) -> None:
    first = tmp_path / "FIRST.csv"
    second = tmp_path / "SECOND.csv"
    _write_prices(first, (100.0, 101.0, 99.0, 102.0))
    _write_prices(second, (200.0, 198.0, 202.0, 197.0))

    result = run_experiment((first, second), periods=3, run_label="small")

    assert result.run_label == "small"
    assert result.requested_periods == 3
    assert result.asset_count == 2
    assert result.min_periods == result.max_periods == 3
    assert result.seconds > 0.0
    assert result.peak_bytes > 0
    assert [asset.symbol for asset in result.assets] == ["FIRST", "SECOND"]


def test_reporting_writes_summary_asset_and_boundary_tables(tmp_path: Path) -> None:
    input_path = tmp_path / "BTCUSDT.csv"
    _write_prices(input_path, (100.0, 101.0, 99.0, 102.0))
    result = run_experiment((input_path,), periods=3, run_label="btc")

    output_dir = tmp_path / "results"
    write_experiment_tables((result,), output_dir)
    series = MarketSeries(
        "BTCUSDT",
        tuple(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i) for i in range(4)),
        (100.0, 101.0, 99.0, 102.0),
    )
    write_boundary_table(series, analyze_series(series), output_dir)

    summary = list(csv.DictReader((output_dir / "01_run_summary.csv").open(encoding="utf-8")))
    assets = list(csv.DictReader((output_dir / "02_asset_results.csv").open(encoding="utf-8")))
    boundary = list(csv.DictReader((output_dir / "03_btc_one_year_boundary.csv").open(encoding="utf-8")))
    assert summary[0]["asset_count"] == "1"
    assert assets[0]["symbol"] == "BTCUSDT"
    assert len(boundary) == 4
