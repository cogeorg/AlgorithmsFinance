"""Tests for reproducible benchmark input generation."""

import pytest

from synthetic_data import generate_synthetic_data


def test_generation_is_reproducible() -> None:
    settings = dict(n=100, q=20, hit_rate=0.5, duplicate_policy="allow", seed=2026)

    assert generate_synthetic_data(**settings) == generate_synthetic_data(**settings)


@pytest.mark.parametrize("hit_rate", [0.0, 0.5, 1.0])
def test_requested_hit_rate_is_realized(hit_rate: float) -> None:
    dataset = generate_synthetic_data(
        n=100, q=100, hit_rate=hit_rate, duplicate_policy="allow", seed=17
    )

    assert dataset.actual_hit_rate == hit_rate


def test_unique_policy_produces_unique_ids() -> None:
    dataset = generate_synthetic_data(
        n=100, q=10, hit_rate=0.5, duplicate_policy="unique", seed=17
    )

    assert len(dataset.ids) == len(set(dataset.ids))


def test_allow_policy_can_produce_duplicates() -> None:
    dataset = generate_synthetic_data(
        n=100, q=10, hit_rate=0.5, duplicate_policy="allow", seed=17
    )

    assert len(dataset.ids) > len(set(dataset.ids))


@pytest.mark.parametrize(
    "settings",
    [
        dict(n=-1, q=1, hit_rate=0.5, duplicate_policy="allow", seed=1),
        dict(n=1, q=-1, hit_rate=0.5, duplicate_policy="allow", seed=1),
        dict(n=1, q=1, hit_rate=-0.1, duplicate_policy="allow", seed=1),
        dict(n=1, q=1, hit_rate=1.1, duplicate_policy="allow", seed=1),
        dict(n=1, q=1, hit_rate=0.5, duplicate_policy="invalid", seed=1),
        dict(n=0, q=1, hit_rate=1.0, duplicate_policy="allow", seed=1),
    ],
)
def test_invalid_settings_are_rejected(settings: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        generate_synthetic_data(**settings)
