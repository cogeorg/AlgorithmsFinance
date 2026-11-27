from __future__ import annotations

import math

import pytest

from american_put_lab.pricing import price_american_put
from reference_model import full_tree_american_put


def test_two_period_lecture_example_and_boundaries() -> None:
    result = price_american_put(
        spot=100.0,
        strike=100.0,
        up=1.2,
        down=0.8,
        gross_rate=1.05,
        steps=2,
    )

    assert result.value == pytest.approx(7.9932, abs=5e-5)
    assert result.value == pytest.approx(1175 / 147)
    assert result.exercise_boundary == pytest.approx((math.nan, 80.0, 96.0), nan_ok=True)


@pytest.mark.parametrize("steps", range(0, 7))
@pytest.mark.parametrize("spot", (60.0, 100.0, 140.0))
def test_rolling_algorithm_matches_independent_small_full_tree(steps: int, spot: float) -> None:
    expected_value, expected_boundary = full_tree_american_put(
        spot, 100.0, 1.2, 0.8, 1.01, steps
    )
    actual = price_american_put(spot, 100.0, 1.2, 0.8, 1.01, steps)

    assert actual.value == pytest.approx(expected_value)
    for got, expected in zip(actual.exercise_boundary, expected_boundary, strict=True):
        if expected is None:
            assert math.isnan(got)
        else:
            assert got == pytest.approx(expected)


def test_zero_period_contract_is_immediate_exercise() -> None:
    result = price_american_put(80.0, 100.0, 1.2, 0.8, 1.01, 0)
    assert result.value == pytest.approx(20.0)
    assert result.exercise_boundary == pytest.approx((80.0,))


@pytest.mark.parametrize(
    "kwargs",
    (
        {"steps": -1},
        {"steps": 1.5},
        {"steps": True},
        {"spot": 0.0},
        {"strike": 0.0},
        {"up": 0.8, "down": 1.2},
        {"up": 1.0, "down": 1.0},
        {"gross_rate": 0.79},
        {"gross_rate": 1.21},
    ),
)
def test_invalid_tree_parameters_are_rejected(kwargs: dict[str, object]) -> None:
    arguments = dict(
        spot=100.0,
        strike=100.0,
        up=1.2,
        down=0.8,
        gross_rate=1.01,
        steps=2,
    )
    arguments.update(kwargs)
    with pytest.raises((TypeError, ValueError)):
        price_american_put(**arguments)
