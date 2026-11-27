"""American put pricing with the rolling-array algorithm from the Class 3 slides."""

from math import isfinite


def price_american_put(spot, strike, up, down, gross_rate, steps):
    """Return the model value per unit of the underlying asset.

    ``gross_rate`` is the growth factor for one period, not an annual rate.
    Require a nonnegative integer number of periods and 0 < down < gross_rate
    < up. The model has no dividends or transaction costs. Working storage is
    O(steps); the backward pass takes O(steps**2) operations.

    This first implementation follows the slides directly. Very large trees
    can underflow or overflow in floating-point arithmetic; market-data
    calibration and large-tree numerical checks belong to the next stages.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    if not all(isfinite(x) for x in (spot, strike, up, down, gross_rate)):
        raise ValueError("model parameters must be finite")
    if spot <= 0 or strike < 0:
        raise ValueError("spot must be positive and strike nonnegative")
    if not 0 < down < gross_rate < up:
        raise ValueError("require 0 < down < gross_rate < up (no arbitrage)")

    probability = (gross_rate - down) / (up - down)

    # Build the expiry row, from all down moves to all up moves.
    stock = [spot] * (steps + 1)
    for _ in range(steps):
        stock[0] *= down
    for j in range(1, steps + 1):
        stock[j] = stock[j - 1] * up / down
    value = [max(strike - price, 0) for price in stock]

    # Each new row reuses the arrays holding the following date's values.
    for t in range(steps - 1, -1, -1):
        for j in range(t + 1):
            stock[j] /= down
            continuation = (
                probability * value[j + 1] + (1 - probability) * value[j]
            ) / gross_rate
            value[j] = max(strike - stock[j], 0, continuation)

    return value[0]


if __name__ == "__main__":
    result = price_american_put(100, 100, 1.2, 0.8, 1.05, 2)
    print(f"Two-period American put: {result:.10f} per unit")
    print(f"Rounded to four decimal places: {result:.4f} (slides: 7.9932)")
