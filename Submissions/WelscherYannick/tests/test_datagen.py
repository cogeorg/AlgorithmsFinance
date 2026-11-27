"""Tests for the synthetic-data generator."""

import random

import pytest
from datagen import GenSettings, describe, generate


def test_same_settings_give_same_data():
    s = GenSettings(n=500, q=50, hit_rate=0.5, duplicate_rate=0.2, seed=3)
    assert generate(s) == generate(s)


def test_different_seed_gives_different_data():
    a = generate(GenSettings(n=500, q=50, hit_rate=0.5, seed=1))
    b = generate(GenSettings(n=500, q=50, hit_rate=0.5, seed=2))
    assert a != b


def test_sizes():
    ids, queries = generate(GenSettings(n=1000, q=100, hit_rate=0.5, duplicate_rate=0.3))
    assert len(ids) == 1000
    assert len(queries) == 100


@pytest.mark.parametrize("hit_rate", [0.0, 0.25, 0.5, 1.0])
def test_hit_rate_is_exact_for_q_100(hit_rate):
    ids, queries = generate(GenSettings(n=1000, q=100, hit_rate=hit_rate, seed=5))
    present = set(ids)
    assert sum(q in present for q in queries) == round(hit_rate * 100)


def test_absent_queries_are_really_absent():
    ids, queries = generate(GenSettings(n=1000, q=100, hit_rate=0.0, duplicate_rate=0.5))
    present = set(ids)
    assert not any(q in present for q in queries)


@pytest.mark.parametrize("duplicate_rate,unique", [(0.0, 1000), (0.3, 700), (0.5, 500)])
def test_duplicate_rate(duplicate_rate, unique):
    ids, _ = generate(GenSettings(n=1000, q=10, hit_rate=0.5, duplicate_rate=duplicate_rate))
    assert len(ids) == 1000
    assert len(set(ids)) == unique


def test_duplicate_rate_one_keeps_one_unique_id():
    ids, _ = generate(GenSettings(n=50, q=5, hit_rate=0.5, duplicate_rate=1.0))
    assert len(ids) == 50
    assert len(set(ids)) == 1


def test_array_is_unsorted_and_contains_negative_ids():
    ids, _ = generate(GenSettings(n=1000, q=10, hit_rate=0.5))
    assert ids != sorted(ids)
    assert min(ids) < 0 < max(ids)


def test_empty_array_with_only_absent_queries():
    ids, queries = generate(GenSettings(n=0, q=5, hit_rate=0.0))
    assert ids == []
    assert len(queries) == 5


def test_no_queries():
    ids, queries = generate(GenSettings(n=10, q=0, hit_rate=0.5))
    assert len(ids) == 10
    assert queries == []


@pytest.mark.parametrize(
    "settings",
    [
        GenSettings(n=0, q=5, hit_rate=0.5),  # hits impossible in an empty array
        GenSettings(n=-1, q=5, hit_rate=0.5),
        GenSettings(n=5, q=-1, hit_rate=0.5),
        GenSettings(n=5, q=5, hit_rate=1.5),
        GenSettings(n=5, q=5, hit_rate=-0.1),
        GenSettings(n=5, q=5, hit_rate=0.5, duplicate_rate=1.1),
    ],
)
def test_invalid_settings_raise(settings):
    with pytest.raises(ValueError):
        generate(settings)


def test_global_random_state_is_untouched():
    random.seed(1)
    expected = random.random()
    random.seed(1)
    generate(GenSettings(n=100, q=10, hit_rate=0.5, seed=9))
    assert random.random() == expected


def test_describe_reports_what_was_generated():
    s = GenSettings(n=200, q=40, hit_rate=0.25, duplicate_rate=0.5, seed=4)
    ids, queries = generate(s)
    info = describe(s, ids, queries)
    assert info["n_actual"] == 200
    assert info["n_unique"] == 100
    assert info["q_actual"] == 40
    assert info["hits"] == 10
    assert info["hit_rate_actual"] == 0.25
    assert info["seed"] == 4
