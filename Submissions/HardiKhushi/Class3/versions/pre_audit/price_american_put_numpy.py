"""NumPy version of the same rolling-row recurrence; O(N) working storage."""

from math import log
import sys

import numpy as np

from price_american_put import price_american_put as scalar_price


def price_american_put(spot, strike, up, down, gross_rate, steps, *, return_boundary=False):
    """Apply the scalar model and boundary conventions to whole rows at once.

    Successor values are read into scratch arrays before replacing a row.
    float64 NumPy buffers are counted by tracemalloc on the recorded runtime.
    Work remains O(N squared); there is no full-tree allocation or pruning.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    # Reuse the scalar input contract without running a nontrivial tree.
    scalar_price(spot, strike, up, down, gross_rate, 0)
    low = log(spot) + steps * min(log(up), log(down))
    high = log(spot) + steps * max(log(up), log(down))
    if low < log(sys.float_info.min) + 1 or high > log(sys.float_info.max) - 1:
        raise ValueError("tree asset prices exceed safe floating-point range")
    q = (gross_rate - down) / (up - down)
    tolerance = 32 * sys.float_info.epsilon * max(strike, 1.0)
    width = steps + 1
    stock = np.empty(width, dtype=np.float64)
    current = spot
    for _ in range(steps):
        current *= down
    for j in range(width):
        stock[j] = current
        if j < steps:
            current = current * up / down
    value = np.maximum(strike - stock, 0)
    continuation = np.empty(width, dtype=np.float64)
    scratch = np.empty(width, dtype=np.float64)
    exercise = np.empty(width, dtype=np.float64)
    eligible = np.empty(width, dtype=np.bool_)
    optimal = np.empty(width, dtype=np.bool_)
    boundary = [None] * width if return_boundary else None

    def threshold(count):
        mask = eligible[:count]
        if mask.any():
            return float(stock[count - 1 - int(np.argmax(mask[::-1]))])
        return None

    if boundary is not None:
        np.greater(value, tolerance, out=eligible)
        boundary[steps] = threshold(width)
    for t in range(steps - 1, -1, -1):
        width = t + 1
        row = slice(0, width)
        np.divide(stock[row], down, out=stock[row])
        np.multiply(value[1:width + 1], q, out=continuation[row])
        np.multiply(value[row], 1 - q, out=scratch[row])
        np.add(continuation[row], scratch[row], out=continuation[row])
        np.divide(continuation[row], gross_rate, out=continuation[row])
        np.subtract(strike, stock[row], out=exercise[row])
        np.maximum(exercise[row], 0, out=exercise[row])
        np.maximum(exercise[row], continuation[row], out=value[row])
        if boundary is not None:
            np.greater(exercise[row], tolerance, out=eligible[row])
            np.add(exercise[row], tolerance, out=scratch[row])
            np.greater_equal(scratch[row], continuation[row], out=optimal[row])
            np.logical_and(eligible[row], optimal[row], out=eligible[row])
            boundary[t] = threshold(width)
    if boundary is not None:
        return float(value[0]), boundary
    return float(value[0])
