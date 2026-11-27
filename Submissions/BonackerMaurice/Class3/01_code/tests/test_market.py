"""Tests for loading the hourly files, calibration and the would-have-exercised check."""
import math
import statistics
from datetime import datetime, timedelta, timezone

import pytest

from american_put import reference
from market import data

T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def write_csv(path, prices, skip_hours=()):
    """Hourly file in the lab format; hours listed in skip_hours are missing rows."""
    lines = ["timestamp_utc,close"]
    hour = 0
    for p in prices:
        while hour in skip_hours:
            hour += 1
        ts = (T0 + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f"{ts},{p}")
        hour += 1
    path.write_text("\n".join(lines) + "\n")
    return path


PRICES = [100.0, 101.0, 99.5, 102.0, 98.0, 97.0, 103.0, 100.5, 99.0, 101.5]


def test_load_reads_timestamps_and_closes(tmp_path):
    f = write_csv(tmp_path / "X.csv", PRICES)
    ts, closes = data.load_hourly(f)
    assert closes == PRICES
    assert ts[0] == T0
    assert ts[-1] == T0 + timedelta(hours=len(PRICES) - 1)
    assert all(t.tzinfo is not None for t in ts)


def test_last_window_takes_last_n_plus_one_rows(tmp_path):
    f = write_csv(tmp_path / "X.csv", PRICES)
    ts, closes = data.load_hourly(f)
    wts, wcl = data.last_window(ts, closes, N=4)
    assert wcl == PRICES[-5:]
    assert len(wts) == 5


def test_last_window_too_long_rejected(tmp_path):
    f = write_csv(tmp_path / "X.csv", PRICES)
    ts, closes = data.load_hourly(f)
    with pytest.raises(ValueError):
        data.last_window(ts, closes, N=len(PRICES))


def test_window_years_keeps_rows_within_span(tmp_path):
    f = write_csv(tmp_path / "X.csv", PRICES)
    ts, closes = data.load_hourly(f)
    # 5 hours expressed in years: keeps the rows with ts >= last - 5h, i.e. 6 rows.
    years = 5 / (365.25 * 24)
    wts, wcl = data.window_years(ts, closes, years)
    assert wcl == PRICES[-6:]


def test_window_years_longer_than_file_keeps_all(tmp_path):
    f = write_csv(tmp_path / "X.csv", PRICES)
    ts, closes = data.load_hourly(f)
    wts, wcl = data.window_years(ts, closes, 5)
    assert wcl == PRICES


def test_calibration_counts_rows_and_uses_timestamps(tmp_path):
    # Two missing hours: 10 rows span 11 hours.
    f = write_csv(tmp_path / "X.csv", PRICES, skip_hours={3, 7})
    ts, closes = data.load_hourly(f)
    cal = data.calibrate(ts, closes, rate=0.04)
    assert cal.N == len(PRICES) - 1  # one period per row, not per clock hour
    returns = [math.log(b / a) for a, b in zip(PRICES, PRICES[1:])]
    assert cal.s == pytest.approx(statistics.stdev(returns))  # divides by N - 1
    assert cal.u == pytest.approx(math.exp(cal.s))
    assert cal.d == pytest.approx(1 / cal.u)
    span_hours = (len(PRICES) - 1) + 2
    assert cal.T == pytest.approx(span_hours / (365.25 * 24))
    assert cal.R == pytest.approx(math.exp(0.04 * cal.T / cal.N))
    assert cal.S0 == cal.K == PRICES[0]


def test_calibration_inputs_unchanged(tmp_path):
    f = write_csv(tmp_path / "X.csv", PRICES)
    ts, closes = data.load_hourly(f)
    ts_copy, closes_copy = list(ts), list(closes)
    data.calibrate(ts, closes)
    assert ts == ts_copy and closes == closes_copy


def test_first_exercise_finds_first_hit():
    ts = [T0 + timedelta(hours=h) for h in range(5)]
    closes = [100.0, 99.0, 95.0, 90.0, 80.0]
    boundary = [None, 98.0, 96.0, 91.0, 99.0]
    hit = data.first_exercise(ts, closes, boundary, K=100.0)
    assert hit.t == 2
    assert hit.timestamp == ts[2]
    assert hit.price == 95.0
    assert hit.payoff == pytest.approx(5.0)


def test_first_exercise_equality_counts():
    ts = [T0 + timedelta(hours=h) for h in range(3)]
    hit = data.first_exercise(ts, [100.0, 97.0, 90.0], [None, 97.0, 95.0], K=100.0)
    assert hit.t == 1


def test_first_exercise_never():
    ts = [T0 + timedelta(hours=h) for h in range(3)]
    assert data.first_exercise(ts, [100.0, 99.0, 98.0], [None, None, 90.0], K=100.0) is None


def test_first_exercise_length_mismatch_rejected():
    with pytest.raises(ValueError):
        data.first_exercise([T0], [100.0, 99.0], [None, None], K=100.0)


def test_price_window_end_to_end(tmp_path):
    f = write_csv(tmp_path / "X.csv", PRICES)
    ts, closes = data.load_hourly(f)
    out = data.price_window(ts, closes, reference.price_american_put)
    cal = data.calibrate(ts, closes)
    direct = reference.price_american_put(cal.S0, cal.K, cal.u, cal.d, cal.R, cal.N)
    assert out.value == direct.value
    assert out.boundary == direct.boundary
    assert out.calibration == cal
