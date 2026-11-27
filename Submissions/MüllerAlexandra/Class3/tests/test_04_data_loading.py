from __future__ import annotations

from pathlib import Path

import pytest

from american_put_lab.data_io import load_hourly_prices


def test_loader_selects_last_n_plus_one_rows_and_preserves_actual_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "TESTUSDT.csv"
    path.write_text(
        "timestamp_utc,close\n"
        "2026-01-01T00:00:00Z,100\n"
        "2026-01-01T01:00:00Z,101\n"
        "2026-01-01T03:00:00Z,103\n"
        "2026-01-01T04:00:00Z,104\n",
        encoding="utf-8",
    )

    series = load_hourly_prices(path, periods=2)

    assert series.symbol == "TESTUSDT"
    assert series.prices == pytest.approx((101.0, 103.0, 104.0))
    assert series.timestamps[0].hour == 1
    assert series.timestamps[-1].hour == 4


def test_loader_rejects_request_larger_than_available_history(tmp_path: Path) -> None:
    path = tmp_path / "SHORT.csv"
    path.write_text(
        "timestamp_utc,close\n2026-01-01T00:00:00Z,100\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requires"):
        load_hourly_prices(path, periods=1)


def test_loader_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "BAD.csv"
    path.write_text("time,price\n2026-01-01,100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        load_hourly_prices(path)
