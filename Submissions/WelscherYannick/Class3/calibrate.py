"""Lab data and calibration of the binomial tree (Class 3 lab slides 29-30).

Window   last N + 1 hourly closes of a file, P_0, ..., P_N (P_0 first, P_N last).
Contract American put written at P_0, expiring at P_N, strike K = S_0 = P_0.
Tree     one period per hourly price change, so N periods.
         s = sample standard deviation (divisor N - 1) of r_t = ln(P_t / P_{t-1});
         u = e^s, d = 1 / u; R = e^(0.04 T / N).
T        time from P_0 to P_N in years, from the timestamps (missing hours count as
         elapsed time). Year convention (our choice): 365 days = 8,760 hours, the
         convention under which the slides call N = 8,760 "one year".
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

ANNUAL_RATE = 0.04
HOURS_PER_YEAR = 8760.0
ONE_YEAR_STEPS = 8760

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "Class3" / "data" / "hourly"


@dataclass(frozen=True)
class Series:
    symbol: str
    timestamps: List[datetime]
    closes: List[float]


@dataclass(frozen=True)
class TreeParams:
    spot: float
    strike: float
    up: float
    down: float
    gross_rate: float
    steps: int
    sigma: float            # hourly s
    years: float            # T
    q: float                # risk-neutral probability of an up move

    def pricing_args(self):
        return (self.spot, self.strike, self.up, self.down, self.gross_rate, self.steps)


@dataclass(frozen=True)
class Exercise:
    t: int
    timestamp: datetime
    price: float
    boundary: float
    payoff: float


def parse_timestamp(text: str) -> datetime:
    stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def load_series(symbol: str, data_dir: Path = DATA_DIR) -> Series:
    path = Path(data_dir) / f"{symbol}.csv"
    timestamps, closes = [], []
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header[:2] != ["timestamp_utc", "close"]:
            raise ValueError(f"{path}: unexpected header {header}")
        for stamp, close in reader:
            timestamps.append(parse_timestamp(stamp))
            closes.append(float(close))
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError(f"{path}: timestamps are not strictly increasing")
    if any(not c > 0 for c in closes):
        raise ValueError(f"{path}: non-positive close")
    return Series(symbol, timestamps, closes)


def available_symbols(data_dir: Path = DATA_DIR) -> List[str]:
    return sorted(p.stem for p in Path(data_dir).glob("*.csv") if p.stem != "SP500")


def last_window(series: Series, steps: Optional[int]) -> Series:
    """The last N + 1 closes; steps=None means the full file (N = rows - 1)."""
    rows = len(series.closes)
    if steps is None:
        steps = rows - 1
    if steps < 1 or steps + 1 > rows:
        raise ValueError(f"{series.symbol}: need {steps + 1} closes, file has {rows}")
    return Series(series.symbol, series.timestamps[-(steps + 1):], series.closes[-(steps + 1):])


def hourly_volatility(closes: Sequence[float]) -> float:
    """Sample standard deviation (divisor N - 1) of the hourly log returns."""
    returns = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    n = len(returns)
    if n < 2:
        raise ValueError("need at least two returns (three closes) for a sample deviation")
    mean = sum(returns) / n
    return math.sqrt(sum((r - mean) ** 2 for r in returns) / (n - 1))


def calibrate(window: Series, annual_rate: float = ANNUAL_RATE) -> TreeParams:
    steps = len(window.closes) - 1
    sigma = hourly_volatility(window.closes)
    up = math.exp(sigma)
    down = 1 / up
    hours = (window.timestamps[-1] - window.timestamps[0]).total_seconds() / 3600
    years = hours / HOURS_PER_YEAR
    gross_rate = math.exp(annual_rate * years / steps)
    if not 0 < down < gross_rate < up:
        raise ValueError(f"{window.symbol}: no-arbitrage condition d < R < u fails")
    q = (gross_rate - down) / (up - down)
    spot = window.closes[0]
    return TreeParams(spot, spot, up, down, gross_rate, steps, sigma, years, q)


def first_exercise(window: Series, strike: float,
                   boundary: Sequence[Optional[float]]) -> Optional[Exercise]:
    """Task 3: the first hour t with P_t at or below the boundary, or None ("never")."""
    if len(boundary) != len(window.closes):
        raise ValueError("boundary and price window differ in length")
    for t, (price, edge) in enumerate(zip(window.closes, boundary)):
        if edge is not None and price <= edge:
            return Exercise(t, window.timestamps[t], price, edge, strike - price)
    return None
