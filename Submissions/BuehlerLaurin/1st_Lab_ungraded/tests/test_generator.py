"""Tests for the synthetic data generator (LAB_SPEC.md T5, I1-I4, decisions Q1-Q2)."""

from __future__ import annotations

import random

import pytest

from datagen.generator import make_case

GRID_N = [1_000, 10_000, 100_000]
GRID_Q = [1, 100]
GRID_HIT = [1.0, 0.0, 0.5]


def test_same_seed_gives_identical_case() -> None:
    assert make_case(1_000, 100, 0.5, seed=42) == make_case(1_000, 100, 0.5, seed=42)


def test_different_seed_gives_different_case() -> None:
    ids_a, queries_a, _ = make_case(1_000, 100, 0.5, seed=1)
    ids_b, queries_b, _ = make_case(1_000, 100, 0.5, seed=2)
    assert ids_a != ids_b
    assert queries_a != queries_b


def test_does_not_touch_global_random_state() -> None:
    random.seed(123)
    expected = random.random()
    random.seed(123)
    make_case(1_000, 100, 0.5, seed=9)
    assert random.random() == expected


@pytest.mark.parametrize("n", GRID_N)
@pytest.mark.parametrize("q", GRID_Q)
@pytest.mark.parametrize("hit_rate", GRID_HIT)
@pytest.mark.parametrize("duplicate_policy", ["allow", "unique"])
def test_benchmark_grid_lengths_and_hit_rate(
    n: int, q: int, hit_rate: float, duplicate_policy: str
) -> None:
    ids, queries, meta = make_case(n, q, hit_rate, seed=0, duplicate_policy=duplicate_policy)
    present = set(ids)
    hits = sum(1 for x in queries if x in present)

    assert len(ids) == n
    assert len(queries) == q
    assert hits == meta["n_present_queries"]
    assert q - hits == meta["n_absent_queries"]
    assert meta["realized_hit_rate"] == hits / q
    assert abs(meta["realized_hit_rate"] - hit_rate) <= 0.5 / q + 1e-12


@pytest.mark.parametrize("hit_rate", [1.0, 0.0])
def test_pure_query_sets(hit_rate: float) -> None:
    ids, queries, _ = make_case(10_000, 100, hit_rate, seed=3)
    present = set(ids)
    assert all((x in present) == (hit_rate == 1.0) for x in queries)


def test_mixed_hit_rate_is_exactly_half_for_q_100() -> None:
    _, _, meta = make_case(10_000, 100, 0.5, seed=5)
    assert meta["n_present_queries"] == 50
    assert meta["realized_hit_rate"] == 0.5


def test_absent_queries_are_odd_and_inside_the_id_span() -> None:
    """Absent queries fall between present IDs, not only above the maximum."""
    ids, queries, _ = make_case(10_000, 100, 0.0, seed=11)
    assert all(x % 2 == 1 for x in queries)
    assert any(x < max(ids) for x in queries)
    assert all(x % 2 == 0 for x in ids)


def test_unique_policy_has_no_duplicates() -> None:
    ids, _, meta = make_case(10_000, 10, 0.5, seed=4, duplicate_policy="unique")
    assert len(set(ids)) == len(ids) == meta["n_distinct"]


def test_allow_policy_produces_duplicates() -> None:
    ids, _, meta = make_case(10_000, 10, 0.5, seed=4, duplicate_policy="allow")
    assert len(set(ids)) < len(ids)
    assert meta["n_distinct"] == len(set(ids))


def test_ids_are_not_sorted() -> None:
    ids, _, _ = make_case(1_000, 10, 0.5, seed=8)
    assert ids != sorted(ids)


def test_meta_records_all_settings() -> None:
    _, _, meta = make_case(1_000, 100, 0.5, seed=6, duplicate_policy="unique")
    for key in (
        "generator",
        "generator_version",
        "n",
        "q",
        "hit_rate",
        "seed",
        "duplicate_policy",
        "id_range",
        "n_distinct",
        "n_present_queries",
        "n_absent_queries",
        "realized_hit_rate",
    ):
        assert key in meta
    assert (meta["n"], meta["q"], meta["hit_rate"], meta["seed"]) == (1_000, 100, 0.5, 6)
    assert meta["duplicate_policy"] == "unique"


def test_empty_cases() -> None:
    ids, queries, meta = make_case(0, 0, 0.5, seed=0)
    assert ids == [] and queries == []
    assert meta["realized_hit_rate"] is None

    ids, queries, _ = make_case(0, 5, 0.0, seed=0)
    assert ids == [] and len(queries) == 5


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n": -1, "q": 1, "hit_rate": 0.5},
        {"n": 1, "q": -1, "hit_rate": 0.5},
        {"n": 1, "q": 1, "hit_rate": 1.5},
        {"n": 1, "q": 1, "hit_rate": -0.1},
        {"n": 1, "q": 1, "hit_rate": 0.5, "duplicate_policy": "sometimes"},
        {"n": 0, "q": 1, "hit_rate": 1.0},
        {"n": 10, "q": 1, "hit_rate": 0.5, "duplicate_policy": "unique", "id_range": 5},
    ],
)
def test_invalid_arguments_raise(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        make_case(seed=0, **kwargs)
