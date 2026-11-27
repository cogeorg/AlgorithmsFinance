"""Hourly closes: loading, windows, calibration, and the would-have-exercised check.

Contract (lab slides 29-31): take the last N+1 hourly closes P0..PN of a file. The put is
written at P0, expires at PN, at the money (S0 = K = P0), exercisable at every hour.
Missing hours are missing rows: one tree period per ROW, so N = rows - 1.
"""
import csv
import math
import statistics
from datetime import datetime, timedelta
from typing import NamedTuple

SECONDS_PER_YEAR = 365.25 * 24 * 3600
RATE = 0.04  # continuously compounded annual risk-free rate


class Calibration(NamedTuple):
    N: int          # tree periods = rows - 1
    s: float        # sample std dev of hourly log returns (divides by N - 1)
    u: float        # e^s
    d: float        # 1/u
    R: float        # e^(rate * T / N), gross return per period
    T: float        # years from the first to the last timestamp (365.25 days/year)
    S0: float       # P0
    K: float        # P0 (at the money)


class Exercise(NamedTuple):
    t: int
    timestamp: datetime
    price: float
    payoff: float   # K - P_t


class Priced(NamedTuple):
    calibration: Calibration
    value: float
    boundary: list
    exercise: Exercise | None


def load_hourly(path):
    """Return (timestamps, closes) of one hourly file; timestamps are UTC-aware."""
    timestamps, closes = [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            timestamps.append(datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00")))
            closes.append(float(row["close"]))
    return timestamps, closes


def last_window(timestamps, closes, N):
    """The last N+1 rows."""
    if N < 1 or N + 1 > len(closes):
        raise ValueError(f"need 1 <= N <= rows-1 = {len(closes) - 1}, got N={N}")
    return timestamps[-(N + 1):], closes[-(N + 1):]


def window_years(timestamps, closes, years):
    """Rows whose timestamp is at most `years` (365.25 days each) before the last row."""
    start = timestamps[-1] - timedelta(seconds=years * SECONDS_PER_YEAR)
    first = next(i for i, ts in enumerate(timestamps) if ts >= start)
    return timestamps[first:], closes[first:]


def calibrate(timestamps, closes, rate=RATE):
    """Calibrate the hourly tree on the whole window P0..PN."""
    N = len(closes) - 1
    if N < 2:
        raise ValueError("need at least 3 rows (2 returns) for a sample std dev")
    returns = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    s = statistics.stdev(returns)
    u = math.exp(s)
    T = (timestamps[-1] - timestamps[0]).total_seconds() / SECONDS_PER_YEAR
    R = math.exp(rate * T / N)
    return Calibration(N=N, s=s, u=u, d=1 / u, R=R, T=T, S0=closes[0], K=closes[0])


def first_exercise(timestamps, closes, boundary, K):
    """First date t with P_t <= boundary_t (the holder would exercise), or None."""
    if not len(timestamps) == len(closes) == len(boundary):
        raise ValueError("timestamps, closes and boundary must have the same length")
    for t, (ts, p, b) in enumerate(zip(timestamps, closes, boundary)):
        if b is not None and p <= b:
            return Exercise(t=t, timestamp=ts, price=p, payoff=K - p)
    return None


def price_window(timestamps, closes, pricer, rate=RATE):
    """Calibrate, price, and check whether the holder would have exercised."""
    cal = calibrate(timestamps, closes, rate)
    result = pricer(cal.S0, cal.K, cal.u, cal.d, cal.R, cal.N)
    hit = first_exercise(timestamps, closes, result.boundary, cal.K)
    return Priced(calibration=cal, value=result.value, boundary=result.boundary, exercise=hit)
