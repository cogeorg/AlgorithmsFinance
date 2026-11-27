"""Scalar American put pricing on a recombining binomial tree.

Backward induction uses O(N**2) time and one O(N) row of option values.
Calibration, exercise boundaries and observed-path decisions are separate APIs.
"""
import math


def _finite_float(value, name):
    """Normalize numeric inputs and give domain errors a consistent exception."""
    try:
        finite = math.isfinite(value)
        number = float(value) if finite else 0.0
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a finite real number representable as float.') from exc
    if not finite:
        raise ValueError(f'{name} must be finite.')
    return number


def price_american_put(S0: float, K: float, u: float, d: float, R: float, N: int) -> float:
    """Return the time-zero American put value in the units of S0 and K.

    Require finite numeric inputs, S0>0, K>=0 and 0<d<R<u. N must be a
    nonnegative Python integer; booleans and ALL floats (including 2.0) are
    rejected. Invalid inputs raise ValueError, including at expiry/zero strike.
    u and d are general multiplicative factors; R is a gross return per period.

    Nodes are indexed by their number of up moves. A single value row is
    overwritten left to right, preserving both successors until they are read.
    Stock-to-strike ratios use log sums and expm1, avoiding overflowing powers
    and reducing cancellation for small positive intrinsic values.

    Limits: calculations use binary64, not arbitrary precision. Very deep or
    nearly degenerate trees can lose accuracy; extremely small branch weights
    or stock contributions can underflow. If the option value itself exceeds
    the finite float range (possible when R<1), raise OverflowError. Resource
    exhaustion for enormous N remains a MemoryError/OverflowError, not an
    invalid-input ValueError. No large-market performance guarantee is implied.
    """
    return _price_tree(S0, K, u, d, R, N, record_boundary=False)[0]


def _price_tree(S0, K, u, d, R, N, *, record_boundary):
    """Shared one-row engine; optionally retain one exercise price per date."""
    S0 = _finite_float(S0, 'S0')
    K = _finite_float(K, 'K')
    u = _finite_float(u, 'u')
    d = _finite_float(d, 'd')
    R = _finite_float(R, 'R')
    if isinstance(N, bool) or not isinstance(N, int) or N < 0:
        raise ValueError('N must be a nonnegative integer, excluding booleans and floats.')
    if S0 <= 0:
        raise ValueError('S0 must be positive.')
    if K < 0:
        raise ValueError('K must be nonnegative.')
    if not 0 < d < R < u:
        raise ValueError('Factors must satisfy 0 < d < R < u.')

    # Validation deliberately precedes both contractual shortcuts.
    immediate = max(K-S0, 0.0)
    if N == 0:
        boundary = (S0 if immediate > 0 else None,) if record_boundary else None
        return immediate, boundary
    if K == 0:
        return 0.0, (None,) * (N+1) if record_boundary else None

    spread = u-d
    q = (R-d) / spread
    # Compute the complementary weight independently: 1-q can round to zero.
    down_probability = (u-R) / spread
    log_u, log_d = math.log(u), math.log(d)
    if 0.5*S0 <= K <= 2*S0:
        log_moneyness_at_root = math.log1p((S0-K)/K)
    else:
        log_moneyness_at_root = math.log(S0)-math.log(K)

    def intrinsic(t, j):
        if t == 0:
            return immediate  # preserve the input-level subtraction at the root
        log_moneyness = math.fsum((log_moneyness_at_root, (t-j)*log_d, j*log_u))
        if log_moneyness >= 0:
            return 0.0
        # expm1 only sees negative arguments; even huge stock nodes need no exp.
        return -K * math.expm1(log_moneyness)

    def stock_at(t, j):
        if t == 0:
            return S0
        # Only exercising nodes reach this function, so the exact stock is <K.
        log_moneyness = math.fsum((log_moneyness_at_root, (t-j)*log_d, j*log_u))
        stock = math.exp(math.fsum((math.log(K), log_moneyness)))
        if stock >= K:
            # A strictly ITM stock can round onto K; round inside its region.
            stock = math.nextafter(K, 0.0)
        if stock <= 0 or not math.isfinite(stock):
            raise OverflowError('Exercise boundary is outside the positive finite float range.')
        return stock

    values = [intrinsic(N, j) for j in range(N+1)]
    boundary = [None] * (N+1) if record_boundary else None
    if boundary is not None:
        last = next((j for j in range(N, -1, -1) if values[j] > 0), None)
        if last is not None:
            boundary[N] = stock_at(N, last)
    for t in range(N-1, -1, -1):
        last = None
        for j in range(t+1):
            down, up = values[j], values[j+1]
            # Interpolate from the more probable endpoint. Nonnegative finite
            # successors remain a convex average without an overflowing sum.
            if q <= down_probability:
                expected = down + q*(up-down)
            else:
                expected = up + down_probability*(down-up)
            continuation = expected / R
            if not math.isfinite(continuation):
                raise OverflowError('Discounted option value exceeds the finite float range.')
            exercise = intrinsic(t, j)
            values[j] = max(exercise, continuation)
            # At zero/negative interest, waiting weakly dominates exercising a
            # non-dividend put. This also preserves exact zero-rate value ties.
            if boundary is not None and R > 1 and exercise > continuation:
                last = j
        if boundary is not None and last is not None:
            boundary[t] = stock_at(t, last)
    return values[0], tuple(boundary) if boundary is not None else None
