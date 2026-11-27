"""Rolling-array binomial pricing for an American put."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real

import numpy as np


@dataclass(frozen=True)
class PricingResult:
    value: float
    exercise_boundary: tuple[float, ...]


def _finite_positive(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return converted


def price_american_put(
    spot: Real,
    strike: Real,
    up: Real,
    down: Real,
    gross_rate: Real,
    steps: int,
) -> PricingResult:
    """Price an American put and return its exercise boundary at every date.

    The algorithm follows the lecture's backward induction but stores only the
    current stock and option-value rows. Runtime is Theta(N^2), auxiliary space
    is Theta(N), and the returned boundary itself has Theta(N) entries.
    """
    if isinstance(steps, bool) or not isinstance(steps, Integral):
        raise TypeError("steps must be an integer")
    steps = int(steps)
    if steps < 0:
        raise ValueError("steps must be nonnegative")

    spot = _finite_positive("spot", spot)
    strike = _finite_positive("strike", strike)
    up = _finite_positive("up", up)
    down = _finite_positive("down", down)
    gross_rate = _finite_positive("gross_rate", gross_rate)
    if not down < up:
        raise ValueError("tree requires down < up")
    if not down <= gross_rate <= up:
        raise ValueError("gross_rate must lie between down and up")

    probability_up = (gross_rate - down) / (up - down)
    indices = np.arange(steps + 1, dtype=np.float64)
    log_stocks = (
        math.log(spot)
        + steps * math.log(down)
        + indices * (math.log(up) - math.log(down))
    )
    with np.errstate(over="ignore", under="ignore"):
        stock = np.exp(log_stocks)
    value = np.maximum(strike - stock, 0.0)
    boundary = np.full(steps + 1, np.nan, dtype=np.float64)

    terminal_mask = value > 0.0
    if np.any(terminal_mask):
        boundary[steps] = stock[np.flatnonzero(terminal_mask)[-1]]

    for time_index in range(steps - 1, -1, -1):
        active = time_index + 1
        with np.errstate(over="ignore", invalid="ignore"):
            stock[:active] /= down
        continuation = (
            probability_up * value[1 : active + 1]
            + (1.0 - probability_up) * value[:active]
        ) / gross_rate
        intrinsic = np.maximum(strike - stock[:active], 0.0)
        exercise = (intrinsic > 0.0) & (intrinsic >= continuation)
        if np.any(exercise):
            boundary[time_index] = stock[np.flatnonzero(exercise)[-1]]
        value[:active] = np.maximum(intrinsic, continuation)

    return PricingResult(float(value[0]), tuple(float(x) for x in boundary))
