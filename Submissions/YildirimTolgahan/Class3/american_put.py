"""PriceAmericanPut on a Cox-Ross-Rubinstein tree: four implementations.

    price_slides   literal slide algorithm (pure Python), plus the boundary
    price_exact    the same recurrence in exact rational arithmetic (oracle)
    price_dense    slide algorithm vectorised with NumPy, every node of every date
    price_band     the fast one: only the nodes whose value is not known in
                   closed form are updated

All four return the put value at date 0 and the early-exercise boundary.

Convention.  Exercising is optimal at node (t, j) when the exercise payoff is
strictly positive and at least the continuation value:  K - S > 0  and
K - S >= c.  jstar[t] is the highest such j at date t, or -1 if there is none.

Why the band works.  Write D = V - (K - S), the value of waiting.  The slide
recurrence becomes

    D[t][j] = max(0, (q D[t+1][j+1] + (1-q) D[t+1][j]) / R - K (1 - 1/R)),

with D[N][j] = max(0, S[N][j] - K).  D is non-decreasing in j.  When d <= 1,
the price in a column does not rise going back in time and D[t][j] >= D[t+1][j].
For d <= 1 <= R (every tree calibrated as in the lab, where d = 1/u) this gives

    (a) the exercise nodes of date t are exactly j <= jstar[t];
    (b) jstar[t+1] - 1 <= jstar[t] <= jstar[t+1]: one comparison per date;
    (c) below the boundary V = K - S; in every column whose leaf is out of the
        money V = 0.

Only the nodes in between need the recurrence.  Outside d <= 1 <= R these
properties fail (with d > 1 a column can be out of the money at expiry and in
the money earlier), so price_band hands such trees to price_dense.

Memory is Theta(N): two float arrays of at most N + 3 entries (values and a
scratch row) and, per date, one integer and one float for the boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

MIN_NORMAL = np.finfo(np.float64).tiny  # 2.2e-308: below this floats are subnormal


@dataclass
class PutResult:
    value: float            # put value at date 0, per share
    jstar: np.ndarray       # jstar[t]: highest exercise node of date t, -1 if none
    boundary: np.ndarray    # tree price at (t, jstar[t]); nan if none
    nodes: int              # nodes on which the recurrence was evaluated


# ----------------------------------------------------------------- validation

def check_inputs(S0, K, u, d, R, N):
    """Reject everything outside the slide specification; return floats and int N."""
    if isinstance(N, bool) or not isinstance(N, (int, np.integer)):
        raise TypeError(f"N must be an integer, got {N!r}")
    N = int(N)
    if N < 0:
        raise ValueError(f"N must be >= 0, got {N}")
    try:
        S0, K, u, d, R = (float(x) for x in (S0, K, u, d, R))
    except (TypeError, ValueError) as error:
        raise TypeError(f"prices and factors must be real numbers: {error}") from None
    for name, x in (("S0", S0), ("K", K), ("u", u), ("d", d), ("R", R)):
        if not math.isfinite(x):
            raise ValueError(f"{name} must be finite, got {x}")
    if S0 <= 0:
        raise ValueError(f"S0 must be > 0, got {S0}")
    if K < 0:
        raise ValueError(f"K must be >= 0, got {K}")
    if not 0 < d < R < u:
        raise ValueError(f"no arbitrage needs 0 < d < R < u, got d={d}, R={R}, u={u}")
    q = (R - d) / (u - d)
    if not 0.0 < q < 1.0:
        raise ValueError(f"d, R, u are too close to separate in floating point (q={q})")
    return S0, K, u, d, R, N


# ---------------------------------------------------------------- node prices

def _pow_me(base, n):
    """base**n as (mantissa, binary exponent); never overflows or underflows."""
    rm, re = 1.0, 0
    bm, be = math.frexp(base)
    while n:
        if n & 1:
            rm, shift = math.frexp(rm * bm)
            re += be + shift
        n >>= 1
        if n:
            bm, shift = math.frexp(bm * bm)
            be = 2 * be + shift
    return rm, re


def _ldexp(m, e):
    try:
        return math.ldexp(m, e)
    except OverflowError:
        return math.inf


def node_price(S0, u, d, t, j, shift=0):
    """S0 u^j d^(t-j) / 2^shift, without chaining t multiplications.  With
    d == 1/u the price depends only on 2j - t, so a node with as many ups as
    downs is exactly S0.

    S0 is split into mantissa and exponent first: the intermediate products
    stay near 1 even when S0 is subnormal or close to the largest float.
    The powers come from repeated squaring; their relative error grows with
    the exponent (about 2e-12 at 43,822 steps).
    """
    ms, es = math.frexp(S0)
    es -= shift
    if d == 1.0 / u:
        k = 2 * j - t
        m, e = _pow_me(u, abs(k))
        return _ldexp(ms * m, es + e) if k >= 0 else _ldexp(ms / m, es - e)
    a, ea = _pow_me(u, j)
    b, eb = _pow_me(d, t - j)
    return _ldexp(ms * a * b, es + ea + eb)


def _first_leaf_out_of_money(S0, K, u, d, N, shift=0):
    """Smallest j in 0..N+1 with S[N][j] / 2^shift >= K (N + 1 if every leaf is
    in the money)."""
    lo, hi = 0, N + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if node_price(S0, u, d, N, mid, shift) >= K:
            hi = mid
        else:
            lo = mid + 1
    return lo


# ------------------------------------------------------- 1. the slides, literally

def price_slides(S0, K, u, d, R, N):
    """Slide algorithm, lines 1-12, in pure Python.  Returns (value, jstar, boundary).

    No input checks and no protection against overflow: this is the reference
    for what the pseudocode itself does.
    """
    q = (R - d) / (u - d)
    S = [S0] * (N + 1)
    for _ in range(N):
        S[0] = d * S[0]
    for j in range(1, N + 1):
        S[j] = S[j - 1] * u / d
    V = [max(K - s, 0) for s in S]
    jstar = [-1] * (N + 1)
    boundary = [math.nan] * (N + 1)
    for j in range(N, -1, -1):
        if K - S[j] > 0:
            jstar[N], boundary[N] = j, S[j]
            break
    for t in range(N - 1, -1, -1):
        for j in range(t + 1):
            S[j] = S[j] / d
            c = (q * V[j + 1] + (1 - q) * V[j]) / R
            exercise = K - S[j]
            if exercise > 0 and exercise >= c:
                jstar[t], boundary[t] = j, S[j]
            V[j] = max(exercise, 0, c)
    return V[0], jstar, boundary


# ------------------------------------------------------------ 2. exact rationals

def price_exact(S0, K, u, d, R, N):
    """The recurrence with fractions.Fraction: no rounding at all.  Floats are
    taken at their exact binary value.  Returns (value, jstar)."""
    S0, K, u, d, R = (Fraction(x) for x in (S0, K, u, d, R))
    q = (R - d) / (u - d)
    S = [S0 * u**j * d**(N - j) for j in range(N + 1)]
    V = [max(K - s, Fraction(0)) for s in S]
    jstar = [-1] * (N + 1)
    jstar[N] = max((j for j in range(N + 1) if K - S[j] > 0), default=-1)
    for t in range(N - 1, -1, -1):
        for j in range(t + 1):
            S[j] = S[j] / d
            c = (q * V[j + 1] + (1 - q) * V[j]) / R
            exercise = K - S[j]
            if exercise > 0 and exercise >= c:
                jstar[t] = j
            V[j] = max(exercise, Fraction(0), c)
    return V[0], jstar


# ------------------------------------------------------------- 3. dense NumPy

def price_dense(S0, K, u, d, R, N, store_tree=False):
    """Every node of every date, one vectorised row at a time: Theta(N^2) work.

    Prices come from S0 exp(j ln u + (t-j) ln d), so nothing overflows.  The
    exercise set of each date is found by scanning the whole row; nothing from
    the band derivation is assumed here.

    store_tree=True keeps all (N+1)^2 values, as an implementation that wants
    the boundary "afterwards" would: Theta(N^2) memory.  Returns (result, tree).
    """
    S0, K, u, d, R, N = check_inputs(S0, K, u, d, R, N)
    q = (R - d) / (u - d)
    ln_u = math.log(u)
    ln_d = -ln_u if d == 1.0 / u else math.log(d)
    index = np.arange(N + 1, dtype=np.float64)

    def prices(t):
        with np.errstate(over="ignore", under="ignore"):
            return S0 * np.exp(index[: t + 1] * ln_u + (t - index[: t + 1]) * ln_d)

    jstar = np.full(N + 1, -1, dtype=np.int64)
    boundary = np.full(N + 1, np.nan)
    tree = np.zeros((N + 1, N + 1)) if store_tree else None

    S = prices(N)
    V = np.maximum(K - S, 0.0)
    hits = np.flatnonzero(K - S > 0)
    if hits.size:
        jstar[N] = hits[-1]
        boundary[N] = S[hits[-1]]
    if store_tree:
        tree[N] = V
    for t in range(N - 1, -1, -1):
        S = prices(t)
        with np.errstate(under="ignore"):
            c = (q * V[1 : t + 2] + (1 - q) * V[: t + 1]) / R
        exercise = K - S
        hits = np.flatnonzero((exercise > 0) & (exercise >= c))
        if hits.size:
            jstar[t] = hits[-1]
            boundary[t] = S[hits[-1]]
        V = np.maximum(np.maximum(exercise, 0.0), c)
        if store_tree:
            tree[t, : t + 1] = V
    result = PutResult(float(V[0]), jstar, boundary, N * (N + 1) // 2)
    return (result, tree) if store_tree else result


# ------------------------------------------------------------------ 4. the band

def price_band(S0, K, u, d, R, N):
    """Value and boundary; updates only nodes strictly between the exercise
    boundary and the region where the value is zero.  See the module docstring.

    Trees outside d <= 1 <= R (negative interest, or a "down" move that goes
    up) are handed to price_dense: the band properties do not hold there.

    Internally all prices are divided by a power of two that puts K near
    2^1000.  That is exact, and it makes the cut-off at the top of the band
    relative: continuation values below about 2^-2022 K count as zero.
    """
    S0, K, u, d, R, N = check_inputs(S0, K, u, d, R, N)
    if R < 1.0 or d > 1.0:
        return price_dense(S0, K, u, d, R, N)
    jstar = np.full(N + 1, -1, dtype=np.int64)
    boundary = np.full(N + 1, np.nan)
    if K == 0.0:
        return PutResult(0.0, jstar, boundary, 0)
    q = (R - d) / (u - d)
    p = 1.0 - q
    shift = math.frexp(K)[1] - 1000
    K = math.ldexp(K, -shift)

    def price(t, j):
        return node_price(S0, u, d, t, j, shift)

    jz = _first_leaf_out_of_money(S0, K, u, d, N, shift)   # columns j >= jz: V = 0
    V = np.zeros(jz + 2)
    scratch = np.empty(jz + 2)

    edge = math.nan                # tree price at (t, jstar[t])
    js = jz - 1                    # at expiry every in-the-money leaf is exercised
    if js >= 0:
        edge = price(N, js)
        V[js] = K - edge
        jstar[N], boundary[N] = js, edge
    hi = jz - 1                    # V[j] = 0 for all j > hi, at this and earlier dates
    nodes = 0
    # R == 1: waiting is free, so D[t][j] = 0 exactly when no reachable leaf is
    # above the strike.  The boundary is then known without any comparison.
    last_leaf_not_above = jz if jz <= N and price(N, jz) == K else jz - 1

    for t in range(N - 1, -1, -1):
        # One comparison decides whether the boundary stays in column js or
        # moves down to js - 1.  V still holds date t + 1 here.
        if js >= 0:
            if js > t:                         # the whole date-(t+1) row exercised
                js = t
            elif R == 1.0:
                js = min(js, last_leaf_not_above - (N - t))
            else:
                exercise = K - price(t, js)
                c = (q * V[js + 1] + p * V[js]) / R
                if not (exercise > 0.0 and exercise >= c):
                    js -= 1
            # Direct, not edge * u or edge / d: N chained roundings would push
            # K - edge below the intrinsic value K - S0 at the root.
            edge = price(t, js) if js >= 0 else math.nan

        top = min(hi, t)
        n = top - js
        if n > 0:                              # nodes js+1 .. top continue
            a = V[js + 1 : top + 1]
            tmp = scratch[:n]
            with np.errstate(under="ignore"):
                np.multiply(V[js + 2 : top + 2], q, out=tmp)
                a *= p
                a += tmp
                a /= R
            nodes += n
            while top > js and V[top] < MIN_NORMAL:   # flush subnormals to zero
                V[top] = 0.0
                top -= 1
        hi = top
        if js >= 0:
            V[js] = K - edge
            jstar[t], boundary[t] = js, edge

    # The recurrence never drops below K - S0; N roundings of 1 - q can.
    value = max(float(V[0]), K - price(0, 0))
    with np.errstate(under="ignore"):
        boundary = np.ldexp(boundary, shift)
    return PutResult(_ldexp(value, shift), jstar, boundary, nodes)


# ------------------------------------------------------------- market data

HOURS_PER_YEAR = 8760.0
ANNUAL_RATE = 0.04


@dataclass
class Calibration:
    S0: float
    K: float
    u: float
    d: float
    R: float
    N: int
    s: float        # sample standard deviation of hourly log returns
    T: float        # years from the first to the last close


def calibrate(closes, hours_elapsed=None, rate=ANNUAL_RATE):
    """Lab slide 30: at-the-money put on the window P[0..N].

    hours_elapsed is the clock time from P[0] to P[N]; it exceeds N when hours
    are missing from the file.  Default: N hours.
    """
    prices = [float(x) for x in closes]
    N = len(prices) - 1
    if N < 2:
        raise ValueError("need at least three closes: s divides by N - 1")
    if any(not math.isfinite(x) or x <= 0 for x in prices):
        raise ValueError("closes must be finite and positive")

    def log_return(a, b):
        ratio = b / a
        if MIN_NORMAL <= ratio < math.inf:
            return math.log(ratio)
        return math.log(b) - math.log(a)       # the quotient left the normal range

    returns = [log_return(a, b) for a, b in zip(prices, prices[1:])]
    mean = math.fsum(returns) / N
    s = math.sqrt(math.fsum((r - mean) ** 2 for r in returns) / (N - 1))
    if hours_elapsed is None:
        hours_elapsed = N
    if hours_elapsed <= 0:
        raise ValueError("the window must span positive time")
    T = hours_elapsed / HOURS_PER_YEAR
    if s > 700.0:
        raise ValueError(f"hourly volatility s={s:.3g} is too large: e^s overflows")
    u = math.exp(s)
    d = 1.0 / u
    R = math.exp(rate * T / N)
    if not d < R < u:
        raise ValueError(
            f"calibrated tree admits arbitrage: d={d!r}, R={R!r}, u={u!r} "
            f"(hourly volatility s={s:.3g} is not above the hourly interest rate)")
    return Calibration(prices[0], prices[0], u, d, R, N, s, T)


def first_exercise(closes, result):
    """Lab task 3: first t with a boundary at date t and P[t] <= boundary[t].
    Returns (t, K - P[t]) or None.  K is the first close."""
    prices = np.asarray(closes, dtype=np.float64)
    if prices.shape != result.boundary.shape:
        raise ValueError("need one close per date of the tree")
    with np.errstate(invalid="ignore"):
        hits = np.flatnonzero(prices <= result.boundary)   # nan compares False
    if hits.size == 0:
        return None
    t = int(hits[0])
    return t, float(prices[0] - prices[t])
