"""Shared input contract and stable node prices for the two pricing engines."""

from dataclasses import dataclass
from math import exp, isfinite, log
import sys


@dataclass(frozen=True)
class TreeModel:
    spot: float
    strike: float
    up: float
    down: float
    rate: float
    steps: int
    q: float
    log_spot: float
    log_down: float
    log_ratio: float
    reciprocal: bool
    payoff_tolerance: float

    @property
    def tie_tolerance(self):
        # At zero interest, linear in-the-money subtrees can be indifferent.
        return self.payoff_tolerance if self.rate == 1 else 0.0

    def stock(self, t, j):
        if t == 0 or (self.reciprocal and 2 * j == t):
            return self.spot
        return exp(j * self.log_ratio + t * self.log_down + self.log_spot)


def validate_tree(spot, strike, up, down, gross_rate, steps):
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise ValueError('steps must be a nonnegative integer')
    try:
        spot, strike, up, down, gross_rate = map(float, (spot, strike, up, down, gross_rate))
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError('model parameters must be finite real numbers') from error
    if not all(isfinite(x) for x in (spot, strike, up, down, gross_rate)):
        raise ValueError('model parameters must be finite')
    if spot <= 0 or strike < 0:
        raise ValueError('spot must be positive and strike nonnegative')
    if not 0 < down < gross_rate < up:
        raise ValueError('require 0 < down < gross_rate < up (no arbitrage)')
    log_spot, log_up = log(spot), log(up)
    reciprocal = down == 1 / up
    # Preserve the intended exact reciprocal CRR identity in node prices.
    log_down = -log_up if reciprocal else log(down)
    try:
        low = min(log_spot, log_spot + steps * min(log_up, log_down))
        high = max(log_spot, log_spot + steps * max(log_up, log_down))
    except OverflowError as error:
        raise ValueError('tree exceeds numerical range') from error
    if low < log(sys.float_info.min) + 1 or high > log(sys.float_info.max) - 1:
        raise ValueError('tree asset prices exceed safe floating-point range')
    return TreeModel(spot, strike, up, down, gross_rate, steps,
                     (gross_rate - down) / (up - down), log_spot,
                     log_down, log_up - log_down, reciprocal,
                     32 * sys.float_info.epsilon * strike)
