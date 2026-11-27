"""Compare the model's dated exercise thresholds with observed prices."""

from math import isfinite


def first_exercise(window, boundary, strike):
    """Return the first P[t] <= boundary[t] crossing, including expiry, or None.

    Thresholds are discrete tree-node prices; do not interpolate or substitute
    the strike at expiry. Payoff is gross intrinsic value, not profit net of
    the initial option premium. This comparison uses hindsight calibration.
    """
    if len(boundary) != len(window.prices):
        raise ValueError("need one boundary entry for every observed price")
    if not isfinite(strike) or strike < 0:
        raise ValueError("strike must be finite and nonnegative")
    for threshold in boundary:
        if threshold is not None and (
            not isfinite(threshold) or threshold <= 0 or threshold > strike
        ):
            raise ValueError("exercise thresholds must be None or positive and at most strike")
    for t, (price, threshold) in enumerate(zip(window.prices, boundary)):
        if threshold is not None and price <= threshold:
            return {
                "t": t,
                "timestamp_utc": window.timestamps[t].isoformat(),
                "observed_price": price,
                "boundary": threshold,
                "payoff": strike - price,
                "at_expiry": t == window.periods,
            }
    return None
