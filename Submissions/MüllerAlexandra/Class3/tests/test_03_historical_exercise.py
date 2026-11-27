from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

import pytest

from american_put_lab.analysis import first_historical_exercise


def test_first_historical_crossing_is_reported_with_payoff() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = tuple(start + timedelta(hours=i) for i in range(4))
    result = first_historical_exercise(
        prices=(100.0, 91.0, 84.0, 82.0),
        timestamps=timestamps,
        boundary=(math.nan, 90.0, 85.0, 80.0),
        strike=100.0,
    )

    assert result is not None
    assert result.index == 2
    assert result.timestamp == timestamps[2]
    assert result.price == pytest.approx(84.0)
    assert result.boundary == pytest.approx(85.0)
    assert result.payoff == pytest.approx(16.0)


def test_no_boundary_or_no_crossing_returns_none() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = (start, start + timedelta(hours=1))
    assert first_historical_exercise(
        (100.0, 99.0), timestamps, (math.nan, math.nan), 100.0
    ) is None
    assert first_historical_exercise(
        (100.0, 99.0), timestamps, (math.nan, 98.0), 100.0
    ) is None


def test_historical_inputs_must_have_equal_lengths() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        first_historical_exercise((100.0,), (start,), (math.nan, 90.0), 100.0)
