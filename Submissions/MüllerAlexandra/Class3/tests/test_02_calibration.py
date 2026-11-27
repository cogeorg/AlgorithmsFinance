from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import statistics

import pytest

from american_put_lab.calibration import calibrate_tree


def test_calibration_uses_log_returns_sample_standard_deviation_and_elapsed_time() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = (start, start + timedelta(hours=1), start + timedelta(hours=3))
    prices = (100.0, 110.0, 99.0)

    result = calibrate_tree(prices, timestamps, annual_rate=0.04)
    returns = (math.log(1.1), math.log(0.9))
    expected_s = statistics.stdev(returns)
    expected_years = 3.0 / (24.0 * 365.25)

    assert result.periods == 2
    assert result.sample_std == pytest.approx(expected_s)
    assert result.up == pytest.approx(math.exp(expected_s))
    assert result.down == pytest.approx(math.exp(-expected_s))
    assert result.elapsed_years == pytest.approx(expected_years)
    assert result.gross_rate == pytest.approx(math.exp(0.04 * expected_years / 2))


@pytest.mark.parametrize(
    "prices",
    (
        (100.0, 101.0),
        (100.0, 0.0, 101.0),
        (100.0, -1.0, 101.0),
        (100.0, float("nan"), 101.0),
    ),
)
def test_calibration_rejects_too_few_or_nonpositive_nonfinite_prices(prices) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = tuple(start + timedelta(hours=i) for i in range(len(prices)))
    with pytest.raises(ValueError):
        calibrate_tree(prices, timestamps)


def test_calibration_rejects_unsorted_or_duplicate_timestamps() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        calibrate_tree(
            (100.0, 101.0, 102.0),
            (start, start + timedelta(hours=1), start + timedelta(hours=1)),
        )


def test_calibration_rejects_zero_volatility_that_cannot_define_probability() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="volatility"):
        calibrate_tree(
            (100.0, 100.0, 100.0),
            (start, start + timedelta(hours=1), start + timedelta(hours=2)),
        )
