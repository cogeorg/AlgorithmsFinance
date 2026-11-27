"""American put pricing by backward induction with row-sized storage."""

from math import isfinite

from tree_model import validate_tree


def price_american_put(spot, strike, up, down, gross_rate, steps, *, return_boundary=False):
    """Return a put value, or (value, dated boundary) when requested.

    Reconstruct log-price nodes to avoid intermediate product overflow and
    accumulated row-update drift. Preserve exact central nodes for reciprocal
    CRR moves. Time is O(N squared), working storage O(N).

    The boundary excludes payoff noise below a strike-relative tolerance.
    Compare exercise and continuation strictly, except for indifference at
    R=1. At R<1, positive-payoff early exercise is never optimal in this
    no-dividend model. Expiry records the highest positive-payoff tree node.
    """
    model = validate_tree(spot, strike, up, down, gross_rate, steps)
    if steps == 0:
        payoff = max(model.strike - model.spot, 0)
        return (payoff, [model.spot if payoff > 0 else None]) if return_boundary else payoff
    boundary = [None] * (steps + 1) if return_boundary else None
    value = [max(model.strike - model.stock(steps, j), 0) for j in range(steps + 1)]
    if boundary is not None:
        for j, payoff in enumerate(value):
            if payoff > model.payoff_tolerance:
                boundary[steps] = model.stock(steps, j)
    for t in range(steps - 1, -1, -1):
        for j in range(t + 1):
            stock = model.stock(t, j)
            exercise = max(model.strike - stock, 0)
            continuation = (model.q * value[j + 1] + (1 - model.q) * value[j]) / model.rate
            value[j] = max(exercise, continuation)
            if (boundary is not None and model.rate >= 1
                    and exercise > (0 if t == 0 else model.payoff_tolerance)
                    and exercise + model.tie_tolerance >= continuation):
                boundary[t] = stock
    if not isfinite(value[0]):
        raise ArithmeticError('option value exceeds floating-point range')
    return (value[0], boundary) if boundary is not None else value[0]


if __name__ == '__main__':
    result = price_american_put(100, 100, 1.2, .8, 1.05, 2)
    print(f'Two-period American put: {result:.10f} per unit')
    print(f'Rounded to four decimal places: {result:.4f} (slides: 7.9932)')
