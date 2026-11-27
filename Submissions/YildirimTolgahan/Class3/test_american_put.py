"""Tests that try to break price_band.

Run:  python test_american_put.py            (about a minute)
      python test_american_put.py --slow     (adds the five-year dense cross-check)
Also collectable by pytest.
"""

import csv
import math
import random
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

from american_put import (
    calibrate, first_exercise, node_price, price_band, price_dense, price_exact,
    price_slides, PutResult, _first_leaf_out_of_money,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "Class3" / "data" / "hourly"
sys.path.insert(0, str(ROOT / "Class3"))


def raises(kind, call, *args, **kwargs):
    try:
        call(*args, **kwargs)
    except kind:
        return True
    except Exception as error:  # wrong kind of failure
        raise AssertionError(f"expected {kind.__name__}, got {error!r}")
    raise AssertionError(f"expected {kind.__name__}, nothing raised: {args}")


def close(a, b, rel=1e-10, floor=0.0):
    return abs(a - b) <= rel * max(abs(a), abs(b)) + floor


def random_case(rng, max_n):
    """Tiny and huge volatility, q near 0 and near 1, deep in and out of the
    money, R barely above its lower limit; d = 1/u, d < 1 unrelated to u, d = 1
    exactly, and d > 1 (a "down" move that goes up, allowed by 0 < d < R < u)."""
    N = rng.randint(0, max_n)
    s = 10 ** rng.uniform(-4, 0)
    kind = rng.random()
    if kind < 0.4:
        u, d = math.exp(s), 1.0 / math.exp(s)
    elif kind < 0.8:
        u, d = math.exp(s * rng.uniform(0.2, 2)), math.exp(-s * rng.uniform(0.2, 2))
    elif kind < 0.85:
        u, d = math.exp(s), 1.0
    else:
        d = math.exp(s * rng.uniform(0.01, 0.5))
        u = d * math.exp(s * rng.uniform(0.2, 2))
    R = max(1.0, d) + (u - max(1.0, d)) * 10 ** rng.uniform(-6, -0.001)
    S0 = 10 ** rng.uniform(-6, 6)
    K = S0 * math.exp(rng.uniform(-3, 3) * s * math.sqrt(N + 1))
    return S0, K, u, d, R, N


# ------------------------------------------------------------ slide examples

def test_slide_two_period_tree():
    for price in (price_band, price_dense):
        r = price(100, 100, 1.2, 0.8, 1.05, 2)
        assert round(r.value, 4) == 7.9932
        assert list(r.jstar) == [-1, 0, 1]
        assert math.isnan(r.boundary[0]) and r.boundary[1] == 80
        assert close(r.boundary[2], 96, 1e-14)
    assert price_exact(100, 100, Fraction(6, 5), Fraction(4, 5), Fraction(21, 20), 2)[0] \
        == Fraction(1175, 147)


def test_slide_one_period_replication_price():
    assert round(price_band(100, 100, 1.2, 0.8, 1.05, 1).value, 2) == 7.14


def test_zero_periods():
    r = price_band(80, 100, 1.2, 0.8, 1.05, 0)
    assert r.value == 20 and list(r.jstar) == [0] and r.boundary[0] == 80
    r = price_band(100, 100, 1.2, 0.8, 1.05, 0)
    assert r.value == 0 and list(r.jstar) == [-1]
    r = price_band(120, 100, 1.2, 0.8, 1.05, 0)
    assert r.value == 0 and list(r.jstar) == [-1]


# ----------------------------------------------------------- against oracles

def test_band_equals_exact_fractions():
    rng = random.Random(1)
    for _ in range(600):
        S0, K, u, d, R, N = random_case(rng, 30)
        value, jstar = price_exact(S0, K, u, d, R, N)
        r = price_band(S0, K, u, d, R, N)
        assert close(r.value, float(value), 1e-9, 1e-300), (S0, K, u, d, R, N)
        assert list(r.jstar) == jstar, (S0, K, u, d, R, N, list(r.jstar), jstar)


def test_band_equals_exponential_course_oracle():
    from class3_evidence import recursive_put_oracle
    rng = random.Random(2)
    for _ in range(40):
        S0, K, u, d, R, N = random_case(rng, 11)
        exact = recursive_put_oracle(*(Fraction(x) for x in (S0, K, u, d, R)), N)
        assert close(price_band(S0, K, u, d, R, N).value, float(exact), 1e-9, 1e-300)


def test_band_equals_dense_and_slides_medium_trees():
    rng = random.Random(3)
    for i in range(250):
        S0, K, u, d, R, N = random_case(rng, 400)
        band, dense = price_band(S0, K, u, d, R, N), price_dense(S0, K, u, d, R, N)
        assert close(band.value, dense.value, 1e-9, 1e-300), (S0, K, u, d, R, N)
        assert np.array_equal(band.jstar, dense.jstar), (S0, K, u, d, R, N)
        both = ~np.isnan(band.boundary)
        assert np.allclose(band.boundary[both], dense.boundary[both], rtol=1e-9, atol=0)
        assert band.nodes <= dense.nodes
        if i < 60 and u ** N < 1e150 and d ** N > 1e-150:   # where the slides are safe
            value, jstar, _ = price_slides(S0, K, u, d, R, N)
            assert close(band.value, value, 1e-8, 1e-300), (S0, K, u, d, R, N)


def test_every_small_tree_shape_exhaustively():
    """All N up to 12 crossed with moneyness on and around tree nodes."""
    for N in range(13):
        for u, d, R in ((1.2, 0.8, 1.05), (2.0, 0.5, 1.25), (1.1, 0.95, 1.0001),
                        (3.0, 0.1, 2.9), (1.01, 0.5, 1.0), (1.5, 0.9, 1.0)):
            for k in range(-N - 1, N + 2):
                for nudge in (1 - 1e-9, 1.0, 1 + 1e-9):
                    K = 64.0 * u ** max(k, 0) * d ** max(-k, 0) * nudge
                    value, jstar = price_exact(64.0, K, u, d, R, N)
                    r = price_band(64.0, K, u, d, R, N)
                    # nudge == 1.0 puts K within an ulp of a node: whether that
                    # node pays 1e-15 or nothing is beyond any float algorithm.
                    knife_edge = any(
                        abs(float(Fraction(64) * Fraction(u) ** j * Fraction(d) ** (t - j)
                                  - Fraction(K))) < 1e-13 * K
                        for t in range(N + 1) for j in range(t + 1))
                    assert close(r.value, float(value), 1e-10, 1e-13 * K), (K, u, d, R, N)
                    if not knife_edge:
                        assert list(r.jstar) == jstar, (K, u, d, R, N, list(r.jstar), jstar)


# -------------------------------------------------------- exact ties (dyadic)

def test_strike_exactly_on_a_node_dyadic():
    """u = 2, d = 1/2: every tree price is an exact float.  A node with S == K
    pays nothing and must not count as exercise."""
    for N in range(0, 16):
        for k in range(-N, N + 1):
            K = math.ldexp(1024.0, k)
            for R in (1.25, 1.0, 1.75, 1.0 + 2**-20):
                value, jstar = price_exact(1024.0, K, 2.0, 0.5, R, N)
                r = price_band(1024.0, K, 2.0, 0.5, R, N)
                assert r.value == float(value) or close(r.value, float(value), 1e-13)
                assert list(r.jstar) == jstar, (K, R, N)
                assert all(b < K for b in r.boundary[~np.isnan(r.boundary)])


def test_exercise_equals_continuation_exactly_with_interest():
    """u = 2, d = 1/2, R = 1.25: a node at date N-1 with S = 3K/4 has
    K - S == c exactly.  Ties count as exercise."""
    for N in range(1, 13):
        for j in range(N):
            K = math.ldexp(4.0, 2 * j - (N - 1))
            value, jstar = price_exact(3.0, K, 2.0, 0.5, 1.25, N)
            r = price_band(3.0, K, 2.0, 0.5, 1.25, N)
            assert close(r.value, float(value), 1e-13)
            assert list(r.jstar) == jstar, (K, N, list(r.jstar), jstar)
    r = price_band(3.0, 4.0, 2.0, 0.5, 1.25, 1)
    assert list(r.jstar) == [0, 0] and r.boundary[0] == 3.0


def test_at_the_money_middle_leaf_is_exactly_the_strike():
    """Lab setting: d = 1/u computed in floating point, S0 = K.  The slide
    recombination S0 d^N (u/d)^(N/2) misses S0 by rounding; the band must not
    invent an exercise node at the strike."""
    for s in (0.0046, 0.013, 1e-4, 0.3):
        u = math.exp(s)
        d = 1.0 / u
        for N in (2, 10, 500, 8760):
            assert node_price(77582.02, u, d, N, N // 2) == 77582.02
            r = price_band(77582.02, 77582.02, u, d, math.exp(0.04 / 8760), N)
            assert r.jstar[N] == N // 2 - 1
            assert r.boundary[N] < 77582.02


# ---------------------------------------------------- overflow and underflow

def test_slides_break_on_underflow_band_does_not():
    """d^N underflows to zero: the slide pseudocode then returns the strike.
    The band never forms d^N."""
    S0 = K = 100.0
    u, d, R, N = math.exp(0.8), math.exp(-0.8), 1.0001, 1000
    broken, _, _ = price_slides(S0, K, u, d, R, N)
    assert broken == K, broken                       # documents the failure
    band, dense = price_band(S0, K, u, d, R, N), price_dense(S0, K, u, d, R, N)
    assert 0 < band.value < K
    assert close(band.value, dense.value, 1e-9)
    assert np.array_equal(band.jstar, dense.jstar)


def test_five_year_tree_with_violent_asset():
    """u^N overflows a double: hourly volatility 2% over five years, and 7%
    over a tree small enough to check against the dense algorithm."""
    R = math.exp(0.04 / 8760)
    u, N = math.exp(0.02), 43822
    raises(OverflowError, pow, u, N)
    r = price_band(0.004278, 0.004278, u, 1 / u, R, N)
    assert 0 < r.value < 0.004278 and np.isfinite(r.boundary[r.jstar >= 0]).all()
    assert (r.jstar >= 0).sum() > N // 2
    u, N = math.exp(0.07), 12000
    raises(OverflowError, pow, u, N)
    band, dense = price_band(0.004278, 0.004278, u, 1 / u, R, N), \
        price_dense(0.004278, 0.004278, u, 1 / u, R, N)
    assert close(band.value, dense.value, 1e-10)
    assert np.array_equal(band.jstar, dense.jstar)


def test_tiny_and_huge_price_levels_scale():
    """V(aS, aK) = a V(S, K) exactly for powers of two, down to a subnormal
    strike and up to the largest floats, and the boundary index does not move."""
    u, d, R, N = math.exp(0.01), math.exp(-0.01), 1.00001, 600
    base = price_band(1.0, 1.0, u, d, R, N)
    dense = price_dense(1.0, 1.0, u, d, R, N)
    assert close(base.value, dense.value, 1e-12) and np.array_equal(base.jstar, dense.jstar)
    for scale in (2.0**-1060, 2.0**-1015, 2.0**-900, 2.0**-40, 2.0**30, 2.0**900, 2.0**1020):
        r = price_band(scale, scale, u, d, R, N)
        assert r.value == base.value * scale, scale
        assert np.array_equal(r.jstar, base.jstar), scale


def test_price_levels_at_the_ends_of_the_float_range():
    """Found by review: S0 / mantissa overflowed for nodes below a huge S0, a
    subnormal S0 times a mantissa rounded to zero, and an absolute cut-off ate
    values that were normal floats."""
    assert node_price(1e308, 2.0, 0.5, 2, 0) == 2.5e307
    assert node_price(5e-324, 2.0, 0.5, 3, 3) == 4e-323
    for case in ((1e308, 1e308, 2.0, 0.5, 1.25, 2),
                 (1.7e308, 1.7e308, math.exp(0.01), 1 / math.exp(0.01), 1.0001, 5),
                 (5e-324, 1e-323, 2.0, 0.5, 1.25, 3),
                 (1e-306, 1e-306, 1.2, 0.8, 1.05, 2),
                 (2.0**-1015, 2.0**-1015, 2.0, 0.5, 1.25, 60)):
        value, jstar = price_exact(*case)
        r = price_band(*case)
        assert close(r.value, float(value), 1e-12, 5e-324), case
        assert list(r.jstar) == jstar, case


def test_value_never_below_intrinsic_when_q_is_at_rounding_level():
    """Found by review: q = 5e-16, so 1 - q rounds the same way 3,481 times."""
    S0, K = 1.5840210426189045e-172, 4.3467516368140235e-171
    r = price_band(S0, K, 1.2124775868955844, 0.9999999999999999, 1.0, 3481)
    assert r.value >= K - S0


def test_far_out_of_the_money_keeps_relative_accuracy():
    """Value around 1e-100: must still match the dense algorithm digit by digit,
    and anything below the smallest normal float may be flushed to zero."""
    u, d, R, N = math.exp(0.05), math.exp(-0.05), 1.0002, 300
    for ups in (100, 200, 260, 296):
        S0 = 100.0 * u ** ups
        band, dense = price_band(S0, 100.0, u, d, R, N), price_dense(S0, 100.0, u, d, R, N)
        assert dense.value > 0
        assert close(band.value, dense.value, 1e-9), (ups, band.value, dense.value)
    band = price_band(1.0, 1.0, 1e6, 0.5, 1.0000001, 400)       # q = 5e-7
    dense = price_dense(1.0, 1.0, 1e6, 0.5, 1.0000001, 400)
    assert close(band.value, dense.value, 1e-12) and np.array_equal(band.jstar, dense.jstar)
    value, jstar = price_exact(1.0, 1.0, 1e6, 0.5, 1.0000001, 60)
    r = price_band(1.0, 1.0, 1e6, 0.5, 1.0000001, 60)
    assert close(r.value, float(value), 1e-12) and list(r.jstar) == jstar


def test_all_leaves_in_the_money_and_none():
    u, d, R, N = 1.1, 0.9, 1.01, 50
    deep = price_band(1.0, 1e6, u, d, R, N)            # exercise at once
    assert deep.value == 1e6 - 1.0 and deep.jstar[0] == 0
    assert list(deep.jstar) == list(range(N + 1))
    none = price_band(1e6, 1.0, u, d, R, N)            # no leaf pays
    assert none.value == 0.0 and (none.jstar == -1).all() and np.isnan(none.boundary).all()
    zero = price_band(1.0, 0.0, u, d, R, N)            # strike zero
    assert zero.value == 0.0 and (zero.jstar == -1).all() and zero.nodes == 0


# ----------------------------------------------------------- interest regimes

def test_zero_interest_american_equals_european():
    """R = 1: waiting costs nothing.  The value is the European value, and with
    ties counted as exercise the boundary retreats one column per date."""
    rng = random.Random(4)
    for _ in range(100):
        N = rng.randint(1, 25)
        u, d = 1 + rng.random(), 1 / (1 + 3 * rng.random())
        S0 = 100.0
        K = S0 * rng.uniform(0.3, 3)
        value, jstar = price_exact(S0, K, u, d, 1.0, N)
        q = (1 - Fraction(d)) / (Fraction(u) - Fraction(d))
        european = sum(
            math.comb(N, j) * q**j * (1 - q) ** (N - j)
            * max(Fraction(K) - Fraction(S0) * Fraction(u) ** j * Fraction(d) ** (N - j), 0)
            for j in range(N + 1))
        assert value == european
        r = price_band(S0, K, u, d, 1.0, N)
        assert close(r.value, float(european), 1e-11)
        assert list(r.jstar) == jstar


def test_negative_interest_never_exercises_early():
    rng = random.Random(5)
    for _ in range(100):
        N = rng.randint(1, 25)
        u, d = 1 + rng.random(), 0.2 + 0.6 * rng.random()
        R = d + (1 - d) * rng.uniform(0.05, 0.95)
        K = 100.0 * rng.uniform(0.3, 3)
        value, jstar = price_exact(100.0, K, u, d, R, N)
        r = price_band(100.0, K, u, d, R, N)
        assert close(r.value, float(value), 1e-10)
        assert list(r.jstar) == jstar and all(j == -1 for j in jstar[:-1])


def test_interest_barely_positive():
    """R - 1 = 1e-12: the early-exercise premium is close to rounding level.
    On these trees value and boundary still match the exact oracle."""
    for N in (5, 20, 40):
        R = 1.0 + 1e-12
        value, jstar = price_exact(100.0, 100.0, 1.3, 0.7, R, N)
        r = price_band(100.0, 100.0, 1.3, 0.7, R, N)
        assert close(r.value, float(value), 1e-11)
        assert list(r.jstar) == jstar, N


def test_probability_at_the_edges():
    """q within 1e-9 of 0 and of 1."""
    for R in (0.8 + 1e-9, 1.2 - 1e-9, 1.0 + 1e-9):
        for N in (1, 7, 30):
            for K in (60.0, 100.0, 170.0):
                value, jstar = price_exact(100.0, K, 1.2, 0.8, R, N)
                r = price_band(100.0, K, 1.2, 0.8, R, N)
                assert close(r.value, float(value), 1e-9, 1e-300), (R, N, K)
                if R > 1 + 1e-6 or R < 1:
                    assert list(r.jstar) == jstar, (R, N, K)


# ------------------------------------------------------------------ structure

def test_structural_properties():
    rng = random.Random(6)
    for _ in range(150):
        S0, K, u, d, R, N = random_case(rng, 300)
        r = price_band(S0, K, u, d, R, N)
        assert max(K - S0, 0.0) <= r.value <= K                      # bounds
        assert r.jstar[N] <= N and (r.jstar >= -1).all()
        assert (r.jstar <= np.arange(N + 1)).all()                   # node exists
        steps = r.jstar[1:] - r.jstar[:-1]
        if d <= 1:
            assert ((steps == 0) | (steps == 1)).all()               # property (b)
        live = r.jstar >= 0
        assert (r.boundary[live] < K).all() and (r.boundary[live] > 0).all()
        assert np.isnan(r.boundary[~live]).all()
        direct = [node_price(S0, u, d, t, int(j)) for t, j in enumerate(r.jstar) if j >= 0]
        assert np.allclose(r.boundary[live], direct, rtol=1e-9, atol=0)


def test_down_factor_above_one():
    """1 < d < R < u is inside the specification, but a column can then be out
    of the money at expiry and in the money earlier: the band properties fail
    and price_band must fall back.  Found by review; it returned 0 here."""
    r = price_band(100, 150, 3, 2, 2.5, 1)
    assert r.value == 50 and list(r.jstar) == [0, -1]
    r = price_band(100, 150, 1.3, 1.1, 1.2, 3)
    assert close(r.value, 50, 1e-14) and list(r.jstar) == [0, 1, 1, 0]
    rng = random.Random(10)
    for _ in range(300):
        N = rng.randint(0, 14)
        d = 1 + rng.random()
        u = d + rng.random()
        R = d + (u - d) * rng.uniform(0.01, 0.99)
        K = 100.0 * rng.uniform(0.5, 1.5) * d ** rng.randint(0, N)
        value, jstar = price_exact(100.0, K, u, d, R, N)
        r = price_band(100.0, K, u, d, R, N)
        assert close(r.value, float(value), 1e-10), (K, u, d, R, N)
        assert list(r.jstar) == jstar, (K, u, d, R, N)


def test_work_done_is_exactly_the_band():
    """nodes counts the columns between the boundary and the last column that
    can pay; with underflow at the top it must be strictly less."""
    S0, u, R, N = 100.0, math.exp(0.02), 1.0001, 400
    r = price_band(S0, S0, u, 1 / u, R, N)
    jz = _first_leaf_out_of_money(S0, S0, u, 1 / u, N)
    assert r.nodes == sum(max(min(jz - 1, t) - int(r.jstar[t]), 0) for t in range(N))
    u, N = math.exp(0.05), 20000
    r = price_band(S0, S0, u, 1 / u, R, N)
    jz = _first_leaf_out_of_money(S0, S0, u, 1 / u, N)
    assert r.nodes < sum(max(min(jz - 1, t) - int(r.jstar[t]), 0) for t in range(N))
    assert r.nodes < N * (N + 1) // 2 // 5


def test_monotone_in_strike_spot_and_maturity():
    u, d, R = math.exp(0.02), math.exp(-0.02), 1.0001
    values = [price_band(100.0, K, u, d, R, 200).value for K in range(60, 141, 4)]
    assert all(a <= b for a, b in zip(values, values[1:]))
    slopes = [b - a for a, b in zip(values, values[1:])]
    assert all(a <= b + 1e-9 for a, b in zip(slopes, slopes[1:]))    # convex in K
    assert all(s <= 4 + 1e-9 for s in slopes)                         # slope <= 1
    values = [price_band(S, 100.0, u, d, R, 200).value for S in range(60, 141, 4)]
    assert all(a >= b for a, b in zip(values, values[1:]))
    values = [price_band(100.0, 100.0, u, d, R, N).value for N in range(0, 400, 2)]
    assert all(a <= b + 1e-12 for a, b in zip(values, values[1:]))   # more time


def test_exercise_set_is_a_prefix_checked_on_the_full_tree():
    """Property (a) is what lets the band skip nodes.  Verify it node by node on
    stored trees instead of trusting the derivation."""
    rng = random.Random(7)
    for _ in range(40):
        S0, K, u, d, R, N = random_case(rng, 120)
        if R < 1 + 1e-9:
            continue
        result, tree = price_dense(S0, K, u, d, R, N, store_tree=True)
        for t in range(N + 1):
            j = np.arange(t + 1)
            S = S0 * np.exp(j * math.log(u) + (t - j) * math.log(d))
            exercised = (K - S > 0) & (tree[t, : t + 1] <= (K - S) * (1 + 1e-12))
            count = int(exercised.sum())
            assert exercised[:count].all(), (S0, K, u, d, R, N, t)


# -------------------------------------------------------------- input checks

def test_rejects_bad_inputs():
    good = dict(S0=100.0, K=100.0, u=1.2, d=0.8, R=1.05, N=2)
    bad = [
        dict(S0=0), dict(S0=-1), dict(K=-1e-9), dict(N=-1),
        dict(d=0), dict(d=-0.5), dict(d=1.05), dict(d=1.1),      # d >= R
        dict(R=1.2), dict(R=1.3), dict(u=0.7),                    # R >= u, u < d
        dict(S0=math.nan), dict(K=math.inf), dict(u=math.inf), dict(R=math.nan),
        dict(u=1.0, d=1.0, R=1.0),
        dict(u=1e308, d=1 - 1e-16, R=1.0),                        # q underflows to 0
    ]
    for change in bad:
        for price in (price_band, price_dense):
            raises(ValueError, price, **{**good, **change})
    for change in (dict(N=2.0), dict(N=True), dict(N="2"), dict(N=None),
                   dict(S0="abc"), dict(K=None), dict(u=1 + 2j)):
        raises(TypeError, price_band, **{**good, **change})


def test_accepts_other_numeric_types_and_leaves_inputs_alone():
    reference = price_band(100.0, 100.0, 1.25, 0.75, 1.0625, 6).value
    assert price_band(100, 100, Fraction(5, 4), Fraction(3, 4), Fraction(17, 16), 6).value == reference
    assert price_band(np.float32(100), np.int64(100), np.float64(1.25), 0.75, 1.0625,
                      np.int32(6)).value == reference
    again = price_band(100.0, 100.0, 1.25, 0.75, 1.0625, 6)
    assert again.value == reference                                # no hidden state


# ---------------------------------------------------------------- calibration

def test_calibration_by_hand():
    c = calibrate([100.0, 110.0, 99.0, 108.9])
    returns = [math.log(1.1), math.log(0.9), math.log(1.1)]
    mean = sum(returns) / 3
    s = math.sqrt(sum((r - mean) ** 2 for r in returns) / 2)
    assert c.N == 3 and close(c.s, s, 1e-14) and c.u == math.exp(s) and c.d == 1 / c.u
    assert c.S0 == c.K == 100.0 and close(c.R, math.exp(0.04 * (3 / 8760) / 3), 1e-15)


def test_calibration_edge_cases():
    raises(ValueError, calibrate, [])
    raises(ValueError, calibrate, [100.0])
    raises(ValueError, calibrate, [100.0, 101.0])                  # N = 1: divide by 0
    raises(ValueError, calibrate, [100.0] * 50)                    # s = 0: u = d = 1
    raises(ValueError, calibrate, [100.0 * 1.01**i for i in range(50)])  # constant return
    raises(ValueError, calibrate, [100.0, 0.0, 100.0])
    raises(ValueError, calibrate, [0.0, 100.0, 101.0])             # not ZeroDivisionError
    raises(ValueError, calibrate, [100.0, -5.0, 100.0])
    raises(ValueError, calibrate, [100.0, math.nan, 100.0])
    raises(ValueError, calibrate, [1.0, 1.0000001, 1.0, 1.0000001])  # s below interest
    raises(ValueError, calibrate, [1.0, 2.0, 1.0], hours_elapsed=0)
    c = calibrate([1.0, 2.0, 1.0, 2.0], hours_elapsed=6)           # missing hours
    assert close(c.R, math.exp(0.04 * (6 / 8760) / 3), 1e-15)
    prices = [1.0, 2.0, 1.0, 2.0]
    calibrate(prices)
    assert prices == [1.0, 2.0, 1.0, 2.0]
    # consecutive closes whose quotient leaves the float range
    wild = [1e160, 3e-164, 3.3e-164, 4e-164, 3.6e-164]
    logs = [math.log(x) for x in wild]
    returns = [b - a for a, b in zip(logs, logs[1:])]
    mean = sum(returns) / 4
    c = calibrate(wild, rate=0.0)
    assert close(c.s, math.sqrt(sum((r - mean) ** 2 for r in returns) / 3), 1e-12)
    raises(ValueError, calibrate, [1e160, 3e-164, 1e160, 3e-164])  # e^s overflows


def test_calibration_is_scale_free():
    rng = random.Random(8)
    path = [100.0]
    for _ in range(500):
        path.append(path[-1] * math.exp(rng.gauss(0, 0.01)))
    a, b = calibrate(path), calibrate([1024.0 * x for x in path])
    assert a.u == b.u and a.R == b.R and b.K == 1024.0 * a.K
    ra = price_band(a.S0, a.K, a.u, a.d, a.R, a.N)
    rb = price_band(b.S0, b.K, b.u, b.d, b.R, b.N)
    assert rb.value == 1024.0 * ra.value and np.array_equal(ra.jstar, rb.jstar)


# -------------------------------------------------------------- exercise date

def test_first_exercise():
    result = PutResult(0.0, np.array([-1, -1, 0, 1, 2]),
                       np.array([math.nan, math.nan, 80.0, 85.0, 90.0]), 0)
    assert first_exercise([100, 50, 81, 86, 95], result) is None        # never
    assert first_exercise([100, 50, 80, 70, 60], result) == (2, 20.0)   # "at" counts
    assert first_exercise([100, 1, 81, 84.999, 60], result)[0] == 3
    assert first_exercise([100, 99, 98, 97, 90], result) == (4, 10.0)   # at expiry
    raises(ValueError, first_exercise, [100, 50], result)
    one = PutResult(20.0, np.array([0]), np.array([80.0]), 0)
    raises(ValueError, first_exercise, [100, 90, 70, 60, 50], one)     # would broadcast
    raises(ValueError, first_exercise, [100], result)
    raises(ValueError, first_exercise, [[100, 50, 80, 70, 60]], result)
    empty = PutResult(0.0, np.array([-1, -1]), np.array([math.nan, math.nan]), 0)
    assert first_exercise([100, 0.0001], empty) is None


def test_first_exercise_against_brute_force_on_random_paths():
    rng = random.Random(9)
    for _ in range(60):
        N = rng.randint(3, 400)
        path = [100.0]
        for _ in range(N):
            path.append(path[-1] * math.exp(rng.gauss(-0.0005, 0.02)))
        c = calibrate(path)
        assert c.d == 1.0 / c.u                  # not exp(-s): they differ by an ulp
        r = price_band(c.S0, c.K, c.u, c.d, c.R, c.N)
        if N % 2 == 0:                           # middle leaf is the strike itself
            assert node_price(c.S0, c.u, c.d, N, N // 2) == c.K
            assert r.jstar[N] == N // 2 - 1 and r.boundary[N] < c.K
        expected = next(((t, path[0] - path[t]) for t in range(N + 1)
                         if r.jstar[t] >= 0 and path[t] <= r.boundary[t]), None)
        got = first_exercise(path, r)
        assert got == expected or (got[0] == expected[0] and close(got[1], expected[1]))


# ------------------------------------------------------------- market data

def load(symbol, last=None):
    with open(DATA / f"{symbol}.csv", newline="") as handle:
        rows = list(csv.reader(handle))[1:]
    closes = [float(row[1]) for row in rows]
    return closes if last is None else closes[-(last + 1):]


def test_bitcoin_one_year_three_ways():
    """Band, dense NumPy and the course's own pure-Python function at N = 8,760."""
    from class3_evidence import price_american_put
    c = calibrate(load("BTCUSDT", 8760))
    band = price_band(c.S0, c.K, c.u, c.d, c.R, c.N)
    dense = price_dense(c.S0, c.K, c.u, c.d, c.R, c.N)
    assert close(band.value, dense.value, 1e-10)
    assert np.array_equal(band.jstar, dense.jstar)
    assert close(band.value, price_american_put(c.S0, c.K, c.u, c.d, c.R, c.N), 1e-8)
    assert band.nodes < dense.nodes / 4


def test_every_asset_one_year_band_equals_dense():
    for path in sorted(DATA.glob("*USDT.csv")):
        c = calibrate(load(path.stem, 8760))
        band = price_band(c.S0, c.K, c.u, c.d, c.R, c.N)
        dense = price_dense(c.S0, c.K, c.u, c.d, c.R, c.N)
        assert close(band.value, dense.value, 1e-10), path.stem
        assert np.array_equal(band.jstar, dense.jstar), path.stem


def slow_test_every_asset_five_years_band_equals_dense():
    for path in sorted(DATA.glob("*USDT.csv")):
        c = calibrate(load(path.stem))
        band = price_band(c.S0, c.K, c.u, c.d, c.R, c.N)
        dense = price_dense(c.S0, c.K, c.u, c.d, c.R, c.N)
        assert close(band.value, dense.value, 1e-9), path.stem
        assert np.array_equal(band.jstar, dense.jstar), path.stem
        print(f"    {path.stem}: ok", flush=True)


if __name__ == "__main__":
    prefixes = ("test_", "slow_test_") if "--slow" in sys.argv else ("test_",)
    tests = [(name, f) for name, f in list(globals().items())
             if name.startswith(prefixes) and callable(f)]
    failed = 0
    for name, test in tests:
        start = time.perf_counter()
        try:
            test()
            print(f"ok    {time.perf_counter() - start:6.1f}s  {name}", flush=True)
        except AssertionError as error:
            failed += 1
            print(f"FAIL  {time.perf_counter() - start:6.1f}s  {name}\n      {str(error)[:600]}",
                  flush=True)
    print(f"{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
