"""Calibration of the binomial tree from observed closes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import statistics
from collections.abc import Sequence


SECONDS_PER_JULIAN_YEAR = 365.25 * 24.0 * 60.0 * 60.0


@dataclass(frozen=True)
class Calibration:
    periods: int
    sample_std: float
    up: float
    down: float
    elapsed_years: float
    gross_rate: float


def calibrate_tree(
    prices: Sequence[float],
    timestamps: Sequence[datetime],
    annual_rate: float = 0.04,
) -> Calibration:
    """Apply the lab formulas to N+1 prices and their UTC timestamps."""
    if len(prices) != len(timestamps):
        raise ValueError("prices and timestamps must have equal lengths")
    if len(prices) < 3:
        raise ValueError("sample volatility requires at least three prices")
    if not math.isfinite(annual_rate):
        raise ValueError("annual_rate must be finite")

    converted_prices = tuple(float(price) for price in prices)
    if any(not math.isfinite(price) or price <= 0.0 for price in converted_prices):
        raise ValueError("prices must be finite and positive")
    if any(timestamp.tzinfo is None for timestamp in timestamps):
        raise ValueError("timestamps must be timezone-aware")
    if any(later <= earlier for earlier, later in zip(timestamps, timestamps[1:])):
        raise ValueError("timestamps must be strictly increasing")

    returns = tuple(
        math.log(later / earlier)
        for earlier, later in zip(converted_prices, converted_prices[1:])
    )
    sample_std = statistics.stdev(returns)
    if sample_std == 0.0:
        raise ValueError("zero volatility cannot define a nondegenerate binomial tree")

    periods = len(converted_prices) - 1
    elapsed_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
    elapsed_years = elapsed_seconds / SECONDS_PER_JULIAN_YEAR
    if elapsed_years <= 0.0:
        raise ValueError("elapsed time must be positive")

    up = math.exp(sample_std)
    down = 1.0 / up
    gross_rate = math.exp(annual_rate * elapsed_years / periods)
    if not down <= gross_rate <= up:
        raise ValueError("calibration violates down <= gross_rate <= up")

    return Calibration(periods, sample_std, up, down, elapsed_years, gross_rate)
