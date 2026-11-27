"""PriceAmericanPut, NumPy version: one vector update of V[0..t] per date.

Same arithmetic, in the same order, as reference.py, so value and boundary are
identical (tested). Memory: O(N), the arrays S and V plus per-date temporaries of
length t+1.
"""
import numpy as np

from american_put.common import PutResult, check_inputs


def _initial_prices(S0, u, d, N):
    """S[0] = S0*d^N, S[j] = S[j-1]*u/d, in exactly the reference's operation order."""
    S = [0.0] * (N + 1)
    S[0] = S0 * d**N
    for j in range(1, N + 1):
        S[j] = S[j - 1] * u / d
    return np.array(S, dtype=np.float64)


def _top_index(mask):
    """Highest index where mask is True, or -1."""
    hits = np.flatnonzero(mask)
    return int(hits[-1]) if hits.size else -1


def price_american_put(S0, K, u, d, R, N):
    q = check_inputs(S0, K, u, d, R, N)
    boundary = [None] * (N + 1)

    S = _initial_prices(S0, u, d, N)
    exercise = K - S
    V = np.maximum(exercise, 0.0)
    j = _top_index(exercise > 0)
    if j >= 0:
        boundary[N] = float(S[j])

    for t in range(N - 1, -1, -1):
        St = S[: t + 1]
        St /= d                                           # in place: S[j] = S[j]/d
        # Continuation from the OLD V: the right-hand side is evaluated completely
        # into a new array before V[:t+1] is overwritten below.
        c = (q * V[1 : t + 2] + (1 - q) * V[: t + 1]) / R
        exercise = K - St
        V[: t + 1] = np.maximum(np.maximum(exercise, 0.0), c)
        j = _top_index((exercise > 0) & (exercise >= c))
        if j >= 0:
            boundary[t] = float(St[j])

    return PutResult(float(V[0]), boundary)
