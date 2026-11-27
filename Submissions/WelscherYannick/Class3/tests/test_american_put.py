"""Correctness checks for PriceAmericanPut (Task 1) and the early-exercise boundary.

Independent references:
- the two-period worked example from the slides, in exact rational arithmetic;
- an exponential recursive oracle that walks every path (no stored subproblems);
- a full-tree oracle that stores every node explicitly and reads off the boundary;
- the European put on the same tree (lower bound, and 6.2925 on the slide tree).
"""
import itertools
import math
import random
from fractions import Fraction as F

import pytest

from american_put import (
    price_american_put,
    price_american_put_numpy,
    price_american_put_with_boundary,
    price_european_put,
)

SLIDE_TREE = (F(100), F(100), F(6, 5), F(4, 5), F(21, 20), 2)   # S0, K, u, d, R, N


# --- independent oracles ----------------------------------------------------------

def recursive_oracle(spot, strike, up, down, gross_rate, steps):
    """Walk all 2^N paths; no array reuse, no stored values."""
    exercise = max(strike - spot, 0)
    if steps == 0:
        return exercise
    q = (gross_rate - down) / (up - down)
    cont = (q * recursive_oracle(spot * up, strike, up, down, gross_rate, steps - 1)
            + (1 - q) * recursive_oracle(spot * down, strike, up, down, gross_rate, steps - 1)
            ) / gross_rate
    return max(exercise, cont)


def full_tree_oracle(spot, strike, up, down, gross_rate, steps):
    """Store the whole tree; return the value and the boundary under our rule."""
    q = (gross_rate - down) / (up - down)
    price = [[spot * up ** j * down ** (t - j) for j in range(t + 1)] for t in range(steps + 1)]
    value = [[None] * (t + 1) for t in range(steps + 1)]
    boundary = [None] * (steps + 1)
    for t in range(steps, -1, -1):
        for j in range(t + 1):
            exercise = strike - price[t][j]
            cont = 0 if t == steps else (
                q * value[t + 1][j + 1] + (1 - q) * value[t + 1][j]) / gross_rate
            if exercise > 0 and exercise >= cont:
                value[t][j] = exercise
                if boundary[t] is None or price[t][j] > boundary[t]:
                    boundary[t] = price[t][j]
            else:
                value[t][j] = max(cont, 0)
    return value[0][0], boundary


# --- Task 1: the slide example ------------------------------------------------------

def test_two_period_slide_value_exact():
    assert price_american_put(*SLIDE_TREE) == F(1175, 147)          # 7.99319...


def test_two_period_slide_value_float_rounds_to_7_9932():
    v = price_american_put(100.0, 100.0, 1.2, 0.8, 1.05, 2)
    assert round(v, 4) == 7.9932


def test_two_period_european_reference_6_2925():
    assert round(float(price_european_put(*SLIDE_TREE)), 4) == 6.2925


def test_two_period_slide_boundary():
    # t=0: S=100, payoff 0 -> none. t=1: exercise at 80 (20 > 15.24), continue at 120.
    # t=2 (expiry): 64 and 96 are in the money, 144 is not -> highest is 96.
    value, boundary = price_american_put_with_boundary(*SLIDE_TREE)
    assert value == F(1175, 147)
    assert boundary == [None, F(80), F(96)]


def test_one_period_replication_example():
    # Slide 18-19: one-period put S=K=100, u=1.2, d=0.8, R=1.05 -> 7.14 (no early exercise).
    v = price_american_put(F(100), F(100), F(6, 5), F(4, 5), F(21, 20), 1)
    assert v == F(150, 21)
    assert round(float(v), 2) == 7.14


# --- exact agreement with independent oracles ---------------------------------------

GRID = list(itertools.product(
    range(0, 8),                                  # N
    (F(60), F(100), F(140)),                      # S0
    (F(0), F(80), F(100), F(120)),                # K (K = 0 is allowed by the spec)
    ((F(6, 5), F(4, 5)), (F(11, 10), F(10, 11))),  # (u, d)
    (F(1), F(101, 100), F(21, 20)),               # R
))


@pytest.mark.parametrize("steps,spot,strike,ud,gross", GRID)
def test_exact_against_recursive_and_full_tree(steps, spot, strike, ud, gross):
    up, down = ud
    if not down < gross < up:
        pytest.skip("arbitrage parameters")
    args = (spot, strike, up, down, gross, steps)
    expected = recursive_oracle(*args)
    assert price_american_put(*args) == expected
    value, boundary = price_american_put_with_boundary(*args)
    oracle_value, oracle_boundary = full_tree_oracle(*args)
    assert value == expected == oracle_value
    assert boundary == oracle_boundary


def test_inputs_are_not_mutated_and_types_kept():
    args = list(SLIDE_TREE)
    price_american_put_with_boundary(*args)
    assert args == list(SLIDE_TREE)


# --- properties ------------------------------------------------------------------------

def test_american_dominates_european_and_intrinsic():
    rng = random.Random(3)
    for _ in range(200):
        s = rng.uniform(0.001, 0.05)
        u, d = math.exp(s), math.exp(-s)
        gross = math.exp(rng.uniform(0, 0.9 * s))
        spot, strike, steps = rng.uniform(10, 200), rng.uniform(10, 200), rng.randint(0, 60)
        am = price_american_put(spot, strike, u, d, gross, steps)
        eu = price_european_put(spot, strike, u, d, gross, steps)
        assert am >= eu - 1e-12
        assert am >= max(strike - spot, 0) - 1e-12
        assert am <= strike + 1e-12


def test_boundary_is_below_strike_and_on_the_tree():
    s = 0.01
    u, d, gross = math.exp(s), math.exp(-s), math.exp(0.04 / 8760)
    value, boundary = price_american_put_with_boundary(100.0, 100.0, u, d, gross, 400)
    for t, b in enumerate(boundary):
        if b is None:
            continue
        assert b < 100.0
        # tree prices at date t are S0 u^(2j - t): the exponent must be an integer of t's parity
        k = math.log(b / 100.0) / s
        assert abs(k - round(k)) < 1e-6 and (round(k) - t) % 2 == 0


def test_numpy_engine_matches_pure_python_exactly():
    rng = random.Random(7)
    for _ in range(60):
        s = rng.uniform(0.001, 0.05)
        u, d = math.exp(s), 1 / math.exp(s)
        gross = math.exp(rng.uniform(0, 0.9 * s))
        spot, strike, steps = rng.uniform(1, 500), rng.uniform(0, 500), rng.randint(0, 400)
        py_value, py_boundary = price_american_put_with_boundary(spot, strike, u, d, gross, steps)
        np_value, np_boundary = price_american_put_numpy(spot, strike, u, d, gross, steps)
        assert py_value == np_value                     # same operations in the same order
        assert py_boundary == np_boundary
        assert price_american_put(spot, strike, u, d, gross, steps) == py_value


def test_numpy_engine_slide_tree():
    value, boundary = price_american_put_numpy(100.0, 100.0, 1.2, 0.8, 1.05, 2)
    assert round(value, 4) == 7.9932
    assert boundary == [None, pytest.approx(80.0), pytest.approx(96.0)]


@pytest.mark.parametrize("bad", [
    dict(steps=-1), dict(spot=0), dict(strike=-1),
    dict(gross_rate=1.3), dict(gross_rate=0.7), dict(down=1.25),
])
def test_rejects_invalid_inputs(bad):
    args = dict(spot=100.0, strike=100.0, up=1.2, down=0.8, gross_rate=1.05, steps=2)
    args.update(bad)
    with pytest.raises(ValueError):
        price_american_put(**args)
    with pytest.raises(ValueError):
        price_american_put_numpy(**args)


def test_zero_periods_is_intrinsic_value():
    assert price_american_put(90.0, 100.0, 1.2, 0.8, 1.05, 0) == 10.0
    assert price_american_put_with_boundary(90.0, 100.0, 1.2, 0.8, 1.05, 0) == (10.0, [90.0])
    assert price_american_put_numpy(110.0, 100.0, 1.2, 0.8, 1.05, 0) == (0.0, [None])
