"""NumPy backward induction with stable log-price rows and O(N) storage."""

import numpy as np

from tree_model import validate_tree


def price_american_put(spot, strike, up, down, gross_rate, steps, *, return_boundary=False):
    """Vectorize the same audited recurrence and boundary policy as the scalar engine."""
    model = validate_tree(spot, strike, up, down, gross_rate, steps)
    count = steps + 1
    indices = np.arange(count, dtype=np.float64)
    stock = np.empty(count, dtype=np.float64)
    continuation = np.empty(count, dtype=np.float64)
    scratch = np.empty(count, dtype=np.float64)
    exercise = np.empty(count, dtype=np.float64)
    eligible = np.empty(count, dtype=np.bool_)
    optimal = np.empty(count, dtype=np.bool_)
    boundary = [None] * count if return_boundary else None

    def price_row(t):
        row = slice(0, t + 1)
        np.multiply(indices[row], model.log_ratio, out=stock[row])
        np.add(stock[row], t * model.log_down, out=stock[row])
        np.add(stock[row], model.log_spot, out=stock[row])
        np.exp(stock[row], out=stock[row])
        if t == 0 or (model.reciprocal and t % 2 == 0):
            stock[t // 2] = model.spot

    def threshold(width):
        mask = eligible[:width]
        if mask.any():
            return float(stock[width - 1 - int(np.argmax(mask[::-1]))])
        return None

    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        price_row(steps)
        value = np.maximum(model.strike - stock, 0)
        if boundary is not None:
            np.greater(value, model.payoff_tolerance, out=eligible)
            boundary[steps] = threshold(count)
        for t in range(steps - 1, -1, -1):
            width = t + 1
            row = slice(0, width)
            price_row(t)
            np.multiply(value[1:width + 1], model.q, out=continuation[row])
            np.multiply(value[row], 1 - model.q, out=scratch[row])
            np.add(continuation[row], scratch[row], out=continuation[row])
            np.divide(continuation[row], model.rate, out=continuation[row])
            np.subtract(model.strike, stock[row], out=exercise[row])
            np.maximum(exercise[row], 0, out=exercise[row])
            np.maximum(exercise[row], continuation[row], out=value[row])
            if boundary is not None and model.rate >= 1:
                np.greater(exercise[row], model.payoff_tolerance, out=eligible[row])
                np.add(exercise[row], model.tie_tolerance, out=scratch[row])
                np.greater_equal(scratch[row], continuation[row], out=optimal[row])
                np.logical_and(eligible[row], optimal[row], out=eligible[row])
                boundary[t] = threshold(width)
        if not np.isfinite(value[0]):
            raise ArithmeticError('option value exceeds floating-point range')
    return (float(value[0]), boundary) if boundary is not None else float(value[0])
