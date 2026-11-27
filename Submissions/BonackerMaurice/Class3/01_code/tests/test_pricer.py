"""Tests for PriceAmericanPut. Written before the implementations (see 00_docs/DEVLOG.md).

All three pricers must pass the same tests:
- reference: pure Python, slide pseudocode line by line, O(N) memory
- vectorised: NumPy, one vector update of V[0..t] per date, O(N) memory
- fulltree: NumPy, stores every node of the value tree, O(N^2) memory
"""
import math
import random
from functools import lru_cache

import pytest

from american_put import common, fulltree, reference, vectorised

PRICERS = {
    "reference": reference.price_american_put,
    "vectorised": vectorised.price_american_put,
    "fulltree": fulltree.price_american_put,
}

# Two-period example of slides 23-26.
SLIDE = dict(S0=100.0, K=100.0, u=1.2, d=0.8, R=1.05, N=2)


# ---------------------------------------------------------------- independent references

def european_put(S0, K, u, d, R, N):
    """Closed-form binomial sum, written independently of the pricers."""
    q = (R - d) / (u - d)
    total = 0.0
    for j in range(N + 1):
        total += math.comb(N, j) * q**j * (1 - q) ** (N - j) * max(K - S0 * u**j * d ** (N - j), 0.0)
    return total / R**N


def brute_force(S0, K, u, d, R, N):
    """Recursion over (t, j) with prices computed directly as S0 * u^j * d^(t-j).

    Returns (value, boundary) with the same boundary definition as the pricers.
    """
    q = (R - d) / (u - d)

    def price(t, j):
        return S0 * u**j * d ** (t - j)

    @lru_cache(maxsize=None)
    def value(t, j):
        exercise = K - price(t, j)
        if t == N:
            return max(exercise, 0.0)
        cont = (q * value(t + 1, j + 1) + (1 - q) * value(t + 1, j)) / R
        return max(exercise, 0.0, cont)

    boundary = []
    for t in range(N + 1):
        best = None
        for j in range(t + 1):
            exercise = K - price(t, j)
            cont = 0.0 if t == N else (q * value(t + 1, j + 1) + (1 - q) * value(t + 1, j)) / R
            if exercise > 0 and exercise >= cont:
                best = price(t, j)
        boundary.append(best)
    return value(0, 0), boundary


def random_tree(rng):
    N = rng.randint(1, 25)
    s = rng.uniform(0.005, 0.3)
    u = math.exp(s)
    S0 = rng.uniform(1.0, 1000.0)
    K = S0 * rng.uniform(0.7, 1.3)
    R = math.exp(rng.uniform(0.0001, 0.05) * s)  # strictly between d and u, and > 1
    return dict(S0=S0, K=K, u=u, d=1 / u, R=R, N=N)


# ---------------------------------------------------------------- slide example

def test_risk_neutral_probability_slide():
    assert common.risk_neutral_q(1.2, 0.8, 1.05) == pytest.approx(0.625)


@pytest.mark.parametrize("name", PRICERS)
def test_slide_value(name):
    result = PRICERS[name](**SLIDE)
    assert result.value == pytest.approx(7.9932, abs=5e-5)


@pytest.mark.parametrize("name", PRICERS)
def test_slide_boundary(name):
    # t=2: S=(64, 96, 144), exercise where K-S > 0 -> highest is 96.
    # t=1: S=(80, 120); at 80: 20 >= 15.24 exercise; at 120: 0 < 1.43 -> 80.
    # t=0: S=100 = K, K-S = 0 -> no exercise.
    boundary = PRICERS[name](**SLIDE).boundary
    assert len(boundary) == 3
    assert boundary[0] is None
    assert boundary[1] == pytest.approx(80.0)
    assert boundary[2] == pytest.approx(96.0)


def test_slide_intermediate_values_reference():
    trace = []
    reference.price_american_put(**SLIDE, trace=trace)
    by_t = {step["t"]: step for step in trace}
    assert by_t[2]["S"] == pytest.approx([64.0, 96.0, 144.0])
    assert by_t[2]["V"] == pytest.approx([36.0, 4.0, 0.0])
    assert by_t[1]["S"] == pytest.approx([80.0, 120.0])
    assert by_t[1]["c"] == pytest.approx([15.24, 1.43], abs=5e-3)
    assert by_t[1]["V"] == pytest.approx([20.0, 1.43], abs=5e-3)
    assert by_t[0]["S"] == pytest.approx([100.0])
    assert by_t[0]["V"] == pytest.approx([7.9932], abs=5e-5)


def test_slide_full_tree_nodes():
    tree = fulltree.value_tree(**SLIDE)
    assert len(tree) == 3
    assert list(tree[2]) == pytest.approx([36.0, 4.0, 0.0])
    assert list(tree[1]) == pytest.approx([20.0, 1.43], abs=5e-3)
    assert list(tree[0]) == pytest.approx([7.9932], abs=5e-5)


def test_slide_european_and_premium():
    assert european_put(**SLIDE) == pytest.approx(6.2925, abs=5e-5)
    american = reference.price_american_put(**SLIDE).value
    assert american - european_put(**SLIDE) == pytest.approx(1.7007, abs=1e-4)


# ---------------------------------------------------------------- random small trees

@pytest.mark.parametrize("seed", range(40))
def test_random_trees_reference_matches_brute_force(seed):
    params = random_tree(random.Random(seed))
    result = reference.price_american_put(**params)
    value, boundary = brute_force(**params)
    assert result.value == pytest.approx(value, rel=1e-10, abs=1e-12)
    assert len(result.boundary) == len(boundary)
    for got, want in zip(result.boundary, boundary):
        if want is None:
            assert got is None
        else:
            assert got == pytest.approx(want, rel=1e-10)


@pytest.mark.parametrize("name", ["vectorised", "fulltree"])
@pytest.mark.parametrize("seed", range(40))
def test_random_trees_match_reference_exactly(name, seed):
    """Same arithmetic in the same order: value and boundary must be identical."""
    params = random_tree(random.Random(seed))
    want = reference.price_american_put(**params)
    got = PRICERS[name](**params)
    assert got.value == want.value
    assert got.boundary == want.boundary


@pytest.mark.parametrize("name", PRICERS)
@pytest.mark.parametrize("seed", range(10))
def test_random_trees_no_arbitrage_bounds(name, seed):
    params = random_tree(random.Random(seed))
    result = PRICERS[name](**params)
    intrinsic = max(params["K"] - params["S0"], 0.0)
    assert result.value >= intrinsic - 1e-12
    assert result.value >= european_put(**params) - 1e-9
    assert result.value <= params["K"]


@pytest.mark.parametrize("name", PRICERS)
def test_boundary_is_below_strike(name):
    params = random_tree(random.Random(123))
    for b in PRICERS[name](**params).boundary:
        assert b is None or b < params["K"]


# ---------------------------------------------------------------- edge cases and contract

@pytest.mark.parametrize("name", PRICERS)
def test_zero_periods_is_intrinsic(name):
    itm = PRICERS[name](S0=90.0, K=100.0, u=1.1, d=1 / 1.1, R=1.01, N=0)
    assert itm.value == pytest.approx(10.0)
    assert itm.boundary == [pytest.approx(90.0)]
    otm = PRICERS[name](S0=110.0, K=100.0, u=1.1, d=1 / 1.1, R=1.01, N=0)
    assert otm.value == 0.0
    assert otm.boundary == [None]


@pytest.mark.parametrize("name", PRICERS)
def test_returns_python_float_and_list(name):
    result = PRICERS[name](**SLIDE)
    assert type(result.value) is float
    assert type(result.boundary) is list
    assert all(b is None or type(b) is float for b in result.boundary)


@pytest.mark.parametrize("name", PRICERS)
@pytest.mark.parametrize("R", [0.8, 0.7, 1.2, 1.3])
def test_arbitrage_parameters_rejected(name, R):
    """q must lie strictly in (0, 1), i.e. d < R < u."""
    with pytest.raises(ValueError):
        PRICERS[name](S0=100.0, K=100.0, u=1.2, d=0.8, R=R, N=2)


@pytest.mark.parametrize("name", PRICERS)
def test_negative_periods_rejected(name):
    with pytest.raises(ValueError):
        PRICERS[name](S0=100.0, K=100.0, u=1.2, d=0.8, R=1.05, N=-1)


# ---------------------------------------------------------------- numerical trap: d^N underflow

def test_tree_log_range():
    lo, hi = common.tree_log_range(S0=100.0, u=math.e, d=1 / math.e, N=10)
    assert lo == pytest.approx(math.log(100.0) - 10)
    assert hi == pytest.approx(math.log(100.0) + 10)


@pytest.mark.parametrize("name", PRICERS)
def test_underflowing_tree_is_rejected(name):
    """S0 * d^N = e^-800 is below the smallest normal float: S[0] would become 0
    and S[j] = S[j-1]*u/d would make every node 0. The pricer must refuse."""
    s = 1.0
    with pytest.raises(ValueError, match="float range"):
        PRICERS[name](S0=1.0, K=1.0, u=math.exp(s), d=math.exp(-s), R=1.0001, N=800)


@pytest.mark.parametrize("name", PRICERS)
def test_large_but_representable_tree_is_accepted(name):
    """s*N = 600 (more than any asset in the data, max 541) still fits a float."""
    N = 600
    s = 1.0
    result = PRICERS[name](S0=1.0, K=1.0, u=math.exp(s), d=math.exp(-s), R=1.0001, N=N)
    assert 0.0 < result.value < 1.0
    assert math.isfinite(result.value)
