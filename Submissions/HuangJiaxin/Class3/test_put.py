"""Tests for PriceAmericanPut (Class 3 lab). Written before the implementation (step 3).

Run from the repository root:  python3 -m pytest -q Submissions/HuangJiaxin/Class3

Independent reference: `exact_tree` below recomputes every node of the tree with exact
fractions and plain recursion, sharing no code with put.py. Exercise rule used
everywhere: exercise at a node if the payoff K - S is positive and at least the
continuation value.
"""
import math
import random
import statistics
from fractions import Fraction as Fr
from functools import lru_cache

import numpy as np
import pytest

import data
import put

TOY = dict(S0=100, K=100, u=1.2, d=0.8, R=1.05, N=2)            # slides 17 to 27
PRICERS = {"plain": put.price_plain, "numpy": put.price_numpy, "full_tree": put.price_full_tree}


# ---------------------------------------------------------------- independent reference
def exact_tree(S0, K, u, d, R, N, american=True):
    """Exact value and boundary by recursion over all nodes (fractions, no shortcuts)."""
    S0, K, u, d, R = (Fr(str(x)) for x in (S0, K, u, d, R))   # str: 1.2 is exactly 6/5
    q = (R - d) / (u - d)

    def stock(t, j):
        return S0 * u ** j * d ** (t - j)

    @lru_cache(maxsize=None)
    def value(t, j):
        payoff = max(K - stock(t, j), 0)
        if t == N:
            return payoff
        cont = (q * value(t + 1, j + 1) + (1 - q) * value(t + 1, j)) / R
        return max(payoff, cont) if american else cont

    boundary = []
    for t in range(N + 1):
        best = None
        for j in range(t + 1):
            payoff = K - stock(t, j)
            if t == N:
                ok = payoff > 0
            else:
                cont = (q * value(t + 1, j + 1) + (1 - q) * value(t + 1, j)) / R
                ok = american and payoff > 0 and payoff >= cont
            if ok:
                best = stock(t, j) if best is None else max(best, stock(t, j))
        boundary.append(best)
    return value(0, 0), boundary


def same_boundary(got, want, rel=1e-9):
    assert len(got) == len(want)
    for t, (g, w) in enumerate(zip(got, want)):
        if w is None:
            assert g is None or (isinstance(g, float) and math.isnan(g)), f"t={t}: {g} vs none"
        else:
            assert g is not None and not math.isnan(g), f"t={t}: none vs {float(w)}"
            assert math.isclose(g, float(w), rel_tol=rel), f"t={t}: {g} vs {float(w)}"


# ---------------------------------------------------------------- the slide example
def test_reference_gives_slide_value_exactly():
    v, _ = exact_tree(**TOY)
    assert v == Fr(1175, 147)                                    # 7.9932 on slide 27
    ve, _ = exact_tree(**TOY, american=False)
    assert round(float(ve), 4) == 6.2925                         # European, slide 27


@pytest.mark.parametrize("name", PRICERS)
def test_slide_example(name):
    v, b = PRICERS[name](**TOY)
    assert math.isclose(v, 1175 / 147, rel_tol=1e-12)
    assert round(v, 4) == 7.9932
    same_boundary(b, exact_tree(**TOY)[1])                       # t=0 none, t=1: 80, t=2: 64 and 96


@pytest.mark.parametrize("name", PRICERS)
def test_slide_example_european(name):
    v, b = PRICERS[name](**TOY, american=False)
    assert math.isclose(v, float(exact_tree(**TOY, american=False)[0]), rel_tol=1e-12)
    assert all(x is None or math.isnan(x) for x in b[:-1])      # never exercised early


# ---------------------------------------------------------------- Jiaxin's hand trace
@pytest.mark.parametrize("name", PRICERS)
def test_jiaxin_hand_trace(name):
    """Three-period tree traced by hand in TRACE.md (S0 = K = 100, u = 2, d = 0.5, R = 1.25)."""
    v, b = PRICERS[name](S0=100, K=100, u=2, d=0.5, R=1.25, N=3)
    assert v == pytest.approx(23.2)
    same_boundary(b, [None, 50, 25, 50])
    assert exact_tree(S0=100, K=100, u=2, d=0.5, R=1.25, N=3)[0] == Fr(116, 5)


# ---------------------------------------------------------------- edge cases
@pytest.mark.parametrize("name", PRICERS)
@pytest.mark.parametrize("S0, want", [(90, 10), (110, 0), (100, 0)])
def test_zero_periods_is_the_payoff(name, S0, want):
    v, b = PRICERS[name](S0=S0, K=100, u=1.2, d=0.8, R=1.05, N=0)
    assert v == pytest.approx(want)
    assert len(b) == 1


@pytest.mark.parametrize("name", PRICERS)
def test_zero_strike_is_worthless(name):
    v, b = PRICERS[name](S0=100, K=0, u=1.2, d=0.8, R=1.05, N=5)
    assert v == 0
    assert all(x is None or math.isnan(x) for x in b)


@pytest.mark.parametrize("name", PRICERS)
def test_deep_in_the_money_exercises_at_once(name):
    v, b = PRICERS[name](S0=1, K=100, u=1.2, d=0.8, R=1.05, N=6)
    assert v == pytest.approx(99)                                # waiting only loses interest
    assert b[0] == pytest.approx(1)


@pytest.mark.parametrize("name", PRICERS)
def test_boundary_at_expiry_is_highest_price_below_strike(name):
    _, b = PRICERS[name](S0=100, K=100, u=1.1, d=1 / 1.1, R=1.01, N=7)
    prices = [100 * 1.1 ** (2 * j - 7) for j in range(8)]
    assert b[-1] == pytest.approx(max(p for p in prices if p < 100))


# ---------------------------------------------------------------- against the reference
def random_case(rng):
    u = rng.choice([1.05, 1.1, 1.25, 1.5, 2.0])
    d = rng.choice([1 / u, 0.5, 0.8, 0.9]) if rng.random() < 0.5 else 1 / u
    d = min(d, 0.95)
    R = rng.uniform(1.0001, min(u, 1.3) - 1e-3)
    if not d < R < u:
        R = (d + u) / 2
    return dict(S0=rng.choice([50, 100, 120]), K=rng.choice([60, 100, 150]),
                u=u, d=d, R=R, N=rng.randint(1, 9))


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("name", PRICERS)
def test_random_small_trees_match_reference(name, seed):
    case = random_case(random.Random(seed))
    for american in (True, False):
        want_v, want_b = exact_tree(**case, american=american)
        v, b = PRICERS[name](**case, american=american)
        assert math.isclose(v, float(want_v), rel_tol=1e-9, abs_tol=1e-12), case
        if american:
            same_boundary(b, want_b)


@pytest.mark.parametrize("seed", range(10))
def test_american_at_least_european_and_payoff(seed):
    case = random_case(random.Random(100 + seed))
    a, _ = put.price_plain(**case)
    e, _ = put.price_plain(**case, american=False)
    assert a >= e - 1e-12
    assert a >= max(case["K"] - case["S0"], 0) - 1e-12
    assert e >= 0


# ---------------------------------------------------------------- fast version vs plain
@pytest.mark.parametrize("n, s", [(300, 0.0046), (2000, 0.0124)])
def test_numpy_matches_plain_on_realistic_trees(n, s):
    case = dict(S0=100.0, K=100.0, u=math.exp(s), d=math.exp(-s), R=math.exp(0.04 / 8760), N=n)
    vp, bp = put.price_plain(**case)
    vn, bn = put.price_numpy(**case)
    assert math.isclose(vp, vn, rel_tol=1e-9)
    assert len(bp) == len(bn) == n + 1
    for x, y in zip(bp, bn):
        if x is None:
            assert math.isnan(y)
        else:
            assert math.isclose(x, y, rel_tol=1e-9)


def test_five_year_scale_has_no_overflow_or_underflow():
    """s * N = 541 for the most volatile asset: S0 * d^N is about 1e-235 (limit 1e-308)."""
    n, s = 43822, 0.01235
    prices = put.tree_prices(100.0, math.exp(s), math.exp(-s), n)
    lo, hi = prices[0], prices[-1]
    assert 0 < lo < 1e-200 and math.isfinite(hi) and hi > 1e200


# ---------------------------------------------------------------- did the holder exercise?
def test_first_exercise_on_a_path():
    boundary = [float("nan"), 90.0, 95.0, 99.0]
    assert put.first_exercise([100, 92, 94, 98], boundary, K=100) == (2, 6)
    assert put.first_exercise([100, 99, 99, 101], boundary, K=100) is None
    assert put.first_exercise([100, 91, 96, 99], boundary, K=100) == (3, 1)


def test_first_exercise_needs_a_positive_payoff():
    assert put.first_exercise([100, 100], [float("nan"), 100.0], K=100) is None


# ---------------------------------------------------------------- calibration
def test_calibration_on_real_data():
    times, closes = data.load_closes("BTCUSDT")
    assert len(closes) == 43823                                  # rows counted, one hour missing
    t, p = data.window(times, closes, 8760)
    assert len(p) == 8761 and p[-1] == closes[-1]
    c = data.calibrate(t, p)
    r = [math.log(b / a) for a, b in zip(p, p[1:])]
    assert c["s"] == pytest.approx(statistics.stdev(r), rel=1e-12)   # divides by N - 1
    assert c["u"] * c["d"] == pytest.approx(1)
    assert 0 < c["q"] < 1 and c["d"] < c["R"] < c["u"]
    assert c["S0"] == c["K"] == p[0]
    assert c["hours_spanned"] == 8760                            # last year has no gap


def test_calibration_rejects_a_flat_price():
    times, _ = data.load_closes("BTCUSDT")
    with pytest.raises(ValueError):
        data.calibrate(times[:5], [100.0] * 5)                   # s = 0, so u = d = 1 < R


def test_whole_file_window():
    times, closes = data.load_closes("PAXGUSDT")
    t, p = data.window(times, closes, None)
    c = data.calibrate(t, p)
    assert c["N"] == 43822 and c["hours_spanned"] == 43823
