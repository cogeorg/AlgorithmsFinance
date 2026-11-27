"""Checks for the data window, the calibration (slide 30) and the Task 3 exercise check."""
import math
import statistics
from datetime import datetime, timedelta, timezone

import pytest

from calibrate import (
    DATA_DIR,
    Series,
    available_symbols,
    calibrate,
    first_exercise,
    hourly_volatility,
    last_window,
    load_series,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_series(closes, gaps=()):
    """Hourly series; an index in gaps is shifted one extra hour (a missing hour before it)."""
    stamps, shift = [], 0
    for i in range(len(closes)):
        if i in gaps:
            shift += 1
        stamps.append(START + timedelta(hours=i + shift))
    return Series("TEST", stamps, list(closes))


def test_window_takes_last_n_plus_one_closes():
    s = make_series([1, 2, 3, 4, 5, 6])
    w = last_window(s, 3)
    assert w.closes == [3, 4, 5, 6]
    assert w.timestamps[0] == START + timedelta(hours=2)
    assert last_window(s, None).closes == s.closes
    with pytest.raises(ValueError):
        last_window(s, 6)


def test_volatility_is_sample_std_of_log_returns():
    closes = [100, 101, 99.5, 102, 101.2, 103.9]
    returns = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    assert hourly_volatility(closes) == pytest.approx(statistics.stdev(returns), rel=1e-12)


def test_calibration_formulas():
    closes = [100, 101, 99.5, 102, 101.2, 103.9]
    p = calibrate(make_series(closes))
    s = statistics.stdev([math.log(b / a) for a, b in zip(closes, closes[1:])])
    assert p.steps == 5
    assert p.spot == p.strike == 100
    assert p.up == pytest.approx(math.exp(s)) and p.down == pytest.approx(1 / p.up)
    assert p.years == pytest.approx(5 / 8760)
    assert p.gross_rate == pytest.approx(math.exp(0.04 / 8760))     # T/N = one hour
    assert p.q == pytest.approx((p.gross_rate - p.down) / (p.up - p.down))
    assert 0 < p.q < 1


def test_missing_hour_counts_as_elapsed_time():
    p = calibrate(make_series([100, 101, 99.5, 102, 101.2, 103.9], gaps={3}))
    assert p.steps == 5
    assert p.years == pytest.approx(6 / 8760)
    assert p.gross_rate == pytest.approx(math.exp(0.04 * (6 / 8760) / 5))


def test_first_exercise_finds_first_hour_at_or_below_boundary():
    w = make_series([100, 98, 95, 94, 97])
    boundary = [None, 90, 95, 96, 99]
    hit = first_exercise(w, 100, boundary)
    assert (hit.t, hit.price, hit.boundary, hit.payoff) == (2, 95, 95, 5)
    assert hit.timestamp == START + timedelta(hours=2)
    assert first_exercise(w, 100, [None, 90, 90, None, 90]) is None


@pytest.mark.skipif(not DATA_DIR.exists(), reason="course data not present (git pull upstream)")
def test_lab_data_shape():
    symbols = available_symbols()
    assert len(symbols) == 40 and "BTCUSDT" in symbols and "PAXGUSDT" in symbols
    btc = load_series("BTCUSDT")
    assert len(btc.closes) == 43_823            # five years minus one missing hour
    assert btc.timestamps[0].isoformat() == "2021-11-01T00:00:00+00:00"
    assert btc.timestamps[-1].isoformat() == "2026-10-31T23:00:00+00:00"
    one_year = calibrate(last_window(btc, 8760))
    assert one_year.steps == 8760 and one_year.years == pytest.approx(1.0)
