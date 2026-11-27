"""American put pricing with the rolling-array algorithm from the Class 3 slides."""

from math import isfinite, log
import sys


def price_american_put(spot, strike, up, down, gross_rate, steps, *, return_boundary=False):
    """Return the model value per unit of the underlying asset.

    ``gross_rate`` is the growth factor for one period, not an annual rate.
    Require a nonnegative integer number of periods and 0 < down < gross_rate
    < up. The model has no dividends or transaction costs. Working storage is
    O(steps); the backward pass takes O(steps**2) operations.

    With return_boundary=True, return (price, boundary), with one threshold
    for each date 0..steps. A threshold is the highest tree price where
    positive-payoff exercise is optimal, or None. Ignore zero-payoff ties;
    at expiry, record the highest in-the-money node. A small floating-point
    tolerance handles indifference and near-zero rounding noise.

    Reject trees whose extreme asset prices exceed normal float range.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    if not all(isfinite(x) for x in (spot, strike, up, down, gross_rate)):
        raise ValueError("model parameters must be finite")
    if spot <= 0 or strike < 0:
        raise ValueError("spot must be positive and strike nonnegative")
    if not 0 < down < gross_rate < up:
        raise ValueError("require 0 < down < gross_rate < up (no arbitrage)")

    log_low = log(spot) + steps * min(log(up), log(down))
    log_high = log(spot) + steps * max(log(up), log(down))
    if log_low < log(sys.float_info.min) + 1 or log_high > log(sys.float_info.max) - 1:
        raise ValueError("tree asset prices exceed safe floating-point range")

    probability = (gross_rate - down) / (up - down)
    boundary = [None] * (steps + 1) if return_boundary else None
    tolerance = 32 * sys.float_info.epsilon * max(strike, 1.0)

    # Build the expiry row, from all down moves to all up moves.
    stock = [spot] * (steps + 1)
    for _ in range(steps):
        stock[0] *= down
    for j in range(1, steps + 1):
        stock[j] = stock[j - 1] * up / down
    value = [max(strike - price, 0) for price in stock]
    if boundary is not None:
        for price, payoff in zip(stock, value):
            if payoff > tolerance:
                boundary[steps] = price

    # Each new row reuses the arrays holding the following date's values.
    for t in range(steps - 1, -1, -1):
        for j in range(t + 1):
            stock[j] /= down
            continuation = (
                probability * value[j + 1] + (1 - probability) * value[j]
            ) / gross_rate
            exercise = max(strike - stock[j], 0)
            value[j] = max(exercise, continuation)
            if boundary is not None and exercise > tolerance and exercise + tolerance >= continuation:
                boundary[t] = stock[j]

    if boundary is not None:
        return value[0], boundary
    return value[0]


if __name__ == "__main__":
    result = price_american_put(100, 100, 1.2, 0.8, 1.05, 2)
    print(f"Two-period American put: {result:.10f} per unit")
    print(f"Rounded to four decimal places: {result:.4f} (slides: 7.9932)")
