"""PriceAmericanPut: an American put in the Cox-Ross-Rubinstein binomial model.

Backward induction (dynamic programming) over the recombining tree, exactly as on
the Class 3 slides: two arrays of N + 1 entries hold one date at a time, and the
inner loop runs over j in increasing order so that V[j] and V[j + 1] still hold
date-(t + 1) values when V[j] is overwritten.

Engines
-------
price_american_put                 pure Python, value only (slides 23-26, line by line)
price_american_put_with_boundary   pure Python, value and early-exercise boundary
price_american_put_numpy           same recurrence and boundary; the loop over j is
                                   vectorised with NumPy (same arithmetic per node)
price_european_put                 reference for tests: no early exercise

Early-exercise rule (our convention)
------------------------------------
Exercising at node (t, j) is optimal when the payoff K - S[t, j] is strictly
positive and at least the continuation value. Ties count as exercise; a node with
payoff zero never counts. At expiry the continuation value is zero, so the boundary
at date N is the highest tree price below the strike.

The boundary at date t is the highest tree price S[t, j] at which exercising is
optimal, or None if there is no such node at that date.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

Boundary = List[Optional[float]]


def _check_inputs(spot, strike, up, down, gross_rate, steps) -> None:
    if not isinstance(steps, int) or steps < 0:
        raise ValueError(f"steps must be an integer >= 0, got {steps!r}")
    if not spot > 0:
        raise ValueError(f"spot must be positive, got {spot!r}")
    if strike < 0:
        raise ValueError(f"strike must be non-negative, got {strike!r}")
    if not 0 < down < gross_rate < up:
        raise ValueError(
            f"no arbitrage requires 0 < d < R < u, got d={down!r}, R={gross_rate!r}, u={up!r}")


def _expiry_prices(spot, up, down, steps) -> list:
    """Lines 2-5: S[j] = S0 u^j d^(N-j) by repeated multiplication (no powers)."""
    stock = [spot] * (steps + 1)
    for _ in range(steps):
        stock[0] *= down
    for j in range(1, steps + 1):
        stock[j] = stock[j - 1] * up / down
    return stock


def price_american_put(spot, strike, up, down, gross_rate, steps):
    """Value at date 0 of an American put, per share (slides 23 and 25, lines 1-12)."""
    _check_inputs(spot, strike, up, down, gross_rate, steps)
    q = (gross_rate - down) / (up - down)                       # line 1
    stock = _expiry_prices(spot, up, down, steps)               # lines 2-5
    value = [max(strike - s, 0) for s in stock]                 # line 6
    for t in range(steps - 1, -1, -1):                          # line 7
        for j in range(t + 1):                                  # line 8, increasing j
            stock[j] /= down                                    # line 9
            continuation = (q * value[j + 1] + (1 - q) * value[j]) / gross_rate  # line 10
            value[j] = max(strike - stock[j], 0, continuation)  # line 11
    return value[0]                                             # line 12


def price_american_put_with_boundary(spot, strike, up, down, gross_rate, steps
                                     ) -> Tuple[float, Boundary]:
    """Value at date 0 and the early-exercise boundary for dates 0..N.

    Same two rolling arrays as price_american_put; the boundary adds one list of
    N + 1 entries, so auxiliary space stays Theta(N).
    """
    _check_inputs(spot, strike, up, down, gross_rate, steps)
    q = (gross_rate - down) / (up - down)
    stock = _expiry_prices(spot, up, down, steps)
    value = [max(strike - s, 0) for s in stock]
    boundary: Boundary = [None] * (steps + 1)

    highest = None
    for j in range(steps + 1):          # prices increase with j
        if strike - stock[j] > 0:
            highest = stock[j]
    boundary[steps] = highest

    for t in range(steps - 1, -1, -1):
        highest = None
        for j in range(t + 1):
            stock[j] /= down
            continuation = (q * value[j + 1] + (1 - q) * value[j]) / gross_rate
            exercise = strike - stock[j]
            if exercise > 0 and exercise >= continuation:
                value[j] = exercise
                highest = stock[j]       # increasing j: the last hit is the highest price
            else:
                # exercise <= 0 or exercise < continuation; continuation >= 0, so this
                # equals max(exercise, 0, continuation) from line 11.
                value[j] = continuation
        boundary[t] = highest
    return value[0], boundary


def price_american_put_numpy(spot, strike, up, down, gross_rate, steps
                             ) -> Tuple[float, Boundary]:
    """Same recurrence and boundary as price_american_put_with_boundary.

    The loop over dates stays a Python loop (backward induction is sequential); the
    loop over nodes j of one date is one vectorised NumPy step. Every node uses the
    same floating-point operations in the same order as the pure-Python engine:
    S / d, (q V[j+1] + (1-q) V[j]) / R and K - S. Preallocated buffers keep the
    auxiliary space at a constant number of arrays of N + 1 entries.
    """
    import numpy as np

    _check_inputs(spot, strike, up, down, gross_rate, steps)
    spot, strike, up, down, gross_rate = map(float, (spot, strike, up, down, gross_rate))
    q = (gross_rate - down) / (up - down)
    one_minus_q = 1 - q
    n_nodes = steps + 1

    stock = np.array(_expiry_prices(spot, up, down, steps), dtype=np.float64)
    value = np.maximum(strike - stock, 0.0)
    bound = np.full(n_nodes, np.nan)
    in_money = np.flatnonzero(strike - stock > 0)
    if in_money.size:
        bound[steps] = stock[in_money[-1]]

    cont = np.empty(n_nodes)
    work = np.empty(n_nodes)
    exer = np.empty(n_nodes)
    hit = np.empty(n_nodes, dtype=bool)
    positive = np.empty(n_nodes, dtype=bool)

    for t in range(steps - 1, -1, -1):
        n = t + 1
        s_t = stock[:n]
        s_t /= down                                            # line 9
        c = cont[:n]
        np.multiply(value[1:n + 1], q, out=c)                  # q V[j+1]
        w = work[:n]
        np.multiply(value[:n], one_minus_q, out=w)             # (1-q) V[j]
        c += w
        c /= gross_rate                                        # line 10
        e = exer[:n]
        np.subtract(strike, s_t, out=e)                        # payoff K - S
        h = hit[:n]
        np.greater_equal(e, c, out=h)
        p = positive[:n]
        np.greater(e, 0.0, out=p)
        h &= p                                                 # exercise optimal
        np.maximum(e, c, out=value[:n])                        # line 11 (c >= 0)
        if h.any():
            bound[t] = s_t[n - 1 - int(np.argmax(h[::-1]))]    # highest j with a hit
    boundary: Boundary = [None if np.isnan(b) else float(b) for b in bound]
    return float(value[0]), boundary


def price_european_put(spot, strike, up, down, gross_rate, steps):
    """European put on the same tree (no early exercise). Used as a test reference."""
    _check_inputs(spot, strike, up, down, gross_rate, steps)
    q = (gross_rate - down) / (up - down)
    stock = _expiry_prices(spot, up, down, steps)
    value = [max(strike - s, 0) for s in stock]
    for t in range(steps - 1, -1, -1):
        for j in range(t + 1):
            value[j] = (q * value[j + 1] + (1 - q) * value[j]) / gross_rate
    return value[0]
