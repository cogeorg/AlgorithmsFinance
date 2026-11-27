"""PriceAmericanPut, pure-Python reference. Follows the slide pseudocode line by line.

Memory: two lists of length N+1 (prices S and values V), plus one boundary entry per
date. O(N) in total; the O(N^2) tree is never stored.
"""
from american_put.common import PutResult, check_inputs


def price_american_put(S0, K, u, d, R, N, trace=None):
    """Return PutResult(value, boundary). `trace`, if a list, receives every date's
    S, c and V (for tests on small trees only)."""
    q = check_inputs(S0, K, u, d, R, N)
    boundary = [None] * (N + 1)

    # Prices and payoffs at expiry t = N.
    S = [0.0] * (N + 1)
    V = [0.0] * (N + 1)
    S[0] = S0 * d**N
    for j in range(1, N + 1):
        S[j] = S[j - 1] * u / d
    for j in range(N + 1):
        V[j] = max(K - S[j], 0.0)
        if K - S[j] > 0:              # at expiry, exercise is optimal wherever it pays
            boundary[N] = S[j]        # S increases in j, so the last hit is the highest
    if trace is not None:
        trace.append({"t": N, "S": S[:], "c": None, "V": V[:]})

    # Backward induction, one date at a time.
    for t in range(N - 1, -1, -1):
        cs = [] if trace is not None else None
        for j in range(t + 1):        # increasing j: V[j+1] is still the old value
            S[j] = S[j] / d
            c = (q * V[j + 1] + (1 - q) * V[j]) / R
            exercise = K - S[j]
            V[j] = max(exercise, 0.0, c)
            if exercise > 0 and exercise >= c:
                boundary[t] = S[j]
            if cs is not None:
                cs.append(c)
        if trace is not None:
            trace.append({"t": t, "S": S[: t + 1], "c": cs, "V": V[: t + 1]})

    return PutResult(V[0], boundary)
