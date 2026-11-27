"""PriceAmericanPut on a recombining binomial tree (Class 3 slides 21 to 27).

Model: Cox, Ross and Rubinstein (1979), 0 < d < R < u, no dividends, exercise at dates
0..N. q = (R - d)/(u - d). Node (t, j): date t, j up moves, S_t,j = S0 u^j d^(t-j).
    V_N,j = max(K - S_N,j, 0)
    V_t,j = max(K - S_t,j, 0, c_t,j),   c_t,j = (q V_t+1,j+1 + (1 - q) V_t+1,j) / R

Exercise rule (used in every version and in the tests): exercise at (t, j) if the
payoff K - S is positive and at least the continuation value c. Early-exercise
boundary b_t: the highest S_t,j where exercising is optimal; None (plain) or NaN (numpy)
if there is no such node. At expiry, b_N is the highest tree price below K.

Three versions, all returning (value at date 0, boundary list of length N + 1):
    price_plain      two arrays S[0..N], V[0..N], plain Python, exactly the slide pseudocode
                     time Theta(N^2), memory Theta(N)
    price_numpy      the same two-array recurrence, vectorized over the nodes of one date
                     time Theta(N^2) element operations but N Python-level steps; memory Theta(N)
    price_full_tree  stores every node of the tree (lists per date): memory Theta(N^2);
                     only for the memory experiment (extra 2) and as a second reference
american=False gives the European put on the same tree (extra 1: early-exercise premium).
"""
import math

import numpy as np


def _q(u, d, R):
    if not 0 < d < R < u:
        raise ValueError(f"no-arbitrage condition 0 < d < R < u fails: d={d}, R={R}, u={u}")
    return (R - d) / (u - d)


# ------------------------------------------------------------------ plain Python (slides)
def price_plain(S0, K, u, d, R, N, american=True):
    q = _q(u, d, R)
    S = [0.0] * (N + 1)
    V = [0.0] * (N + 1)
    S[0] = float(S0)
    for _ in range(N):                       # S[0] = S0 d^N by repeated multiplication
        S[0] *= d
    for j in range(1, N + 1):                # one more up move replaces a down move
        S[j] = S[j - 1] * u / d
    best = None
    for j in range(N + 1):                   # payoff at expiry
        V[j] = max(K - S[j], 0.0)
        if K - S[j] > 0 and (best is None or S[j] > best):
            best = S[j]
    boundary = [None] * (N + 1)
    boundary[N] = best
    for t in range(N - 1, -1, -1):           # backward induction
        best = None
        for j in range(t + 1):               # increasing j: V[j+1] still holds date t+1
            S[j] = S[j] / d
            c = (q * V[j + 1] + (1 - q) * V[j]) / R
            payoff = K - S[j]
            if american and payoff > 0 and payoff >= c:
                V[j] = payoff
                if best is None or S[j] > best:
                    best = S[j]
            else:
                V[j] = c                     # c >= 0, so this equals max(payoff, 0, c)
        boundary[t] = best
    return V[0], boundary


# ------------------------------------------------------------------ numpy
def tree_prices(S0, u, d, t):
    """S_t,j for j = 0..t, computed in logs (no repeated multiplication, no underflow
    of intermediate powers)."""
    j = np.arange(t + 1, dtype=np.float64)
    return S0 * np.exp(j * math.log(u) + (t - j) * math.log(d))


def price_numpy(S0, K, u, d, R, N, american=True):
    q = _q(u, d, R)
    S = tree_prices(float(S0), u, d, N)
    V = np.maximum(K - S, 0.0)
    boundary = np.full(N + 1, np.nan)
    itm = K - S > 0
    if itm.any():
        boundary[N] = S[itm].max()
    for t in range(N - 1, -1, -1):
        S = S[: t + 1] / d                   # remove one down move: date-t prices
        c = (q * V[1: t + 2] + (1 - q) * V[: t + 1]) / R
        if american:
            payoff = K - S
            ex = (payoff > 0) & (payoff >= c)
            V = np.where(ex, payoff, c)
            if ex.any():
                boundary[t] = S[ex].max()
        else:
            V = c
    return float(V[0]), boundary


# ------------------------------------------------------------------ full tree (extra 2)
def price_full_tree(S0, K, u, d, R, N, american=True):
    """Keeps every node: S_tree[t] and V_tree[t] are lists of length t + 1.
    About (N + 1)(N + 2) floats in total: memory grows like N^2."""
    q = _q(u, d, R)
    S_tree = [[S0 * u ** j * d ** (t - j) for j in range(t + 1)] for t in range(N + 1)]
    V_tree = [None] * (N + 1)
    V_tree[N] = [max(K - s, 0.0) for s in S_tree[N]]
    boundary = [None] * (N + 1)
    itm = [s for s in S_tree[N] if K - s > 0]
    boundary[N] = max(itm) if itm else None
    for t in range(N - 1, -1, -1):
        row, best, nxt = [], None, V_tree[t + 1]
        for j in range(t + 1):
            s = S_tree[t][j]
            c = (q * nxt[j + 1] + (1 - q) * nxt[j]) / R
            payoff = K - s
            if american and payoff > 0 and payoff >= c:
                row.append(payoff)
                best = s if best is None else max(best, s)
            else:
                row.append(c)
        V_tree[t] = row
        boundary[t] = best
    return V_tree[0][0], boundary


# ------------------------------------------------------------------ the real path
def first_exercise(path, boundary, K):
    """Task 3: first t >= 1 with path[t] <= boundary[t] and K - path[t] > 0.
    Returns (t, payoff K - path[t]) or None ("never"). t = 0 is excluded: with
    K = P_0 the payoff at 0 is zero."""
    for t in range(1, len(path)):
        b = boundary[t]
        if b is None or (isinstance(b, float) and math.isnan(b)):
            continue
        if path[t] <= b and K - path[t] > 0:
            return t, K - path[t]
    return None
