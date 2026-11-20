"""Tests for the synthetic benchmark-data generator."""

import pytest

from synthetic_data import generate_synthetic_data


def test_sizes_and_requested_hit_rate():
    ids, queries = generate_synthetic_data(200, 80, hit_rate=0.25, seed=7)

    assert len(ids) == 200
    assert len(queries) == 80
    assert sum(query in set(ids) for query in queries) == 20


def test_equal_seeds_are_reproducible():
    first = generate_synthetic_data(50, 30, seed=17)
    second = generate_synthetic_data(50, 30, seed=17)

    assert first == second


def test_empty_inputs_and_empty_id_array():
    assert generate_synthetic_data(0, 0) == ([], [])

    ids, queries = generate_synthetic_data(0, 4, hit_rate=1.0, seed=3)
    assert ids == []
    assert len(queries) == 4
    assert all(query not in ids for query in queries)


@pytest.mark.parametrize(
    ("hit_rate", "expected_hits"),
    [
        (1.0, 20),
        (0.0, 0),
        (0.5, 10),
    ],
)
def test_required_query_scenarios(hit_rate, expected_hits):
    ids, queries = generate_synthetic_data(
        num_ids=100,
        num_queries=20,
        hit_rate=hit_rate,
        seed=21,
    )
    id_set = set(ids)
    actual_hits = sum(query in id_set for query in queries)

    assert actual_hits == expected_hits


def test_duplicate_policy_can_require_unique_ids():
    ids, _ = generate_synthetic_data(
        num_ids=500,
        num_queries=0,
        seed=11,
        allow_duplicates=False,
    )

    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    ("num_ids", "num_queries", "hit_rate"),
    [
        (-1, 10, 0.5),
        (10, -1, 0.5),
        (10, 10, -0.01),
        (10, 10, 1.01),
    ],
)
def test_invalid_parameters_raise_value_error(num_ids, num_queries, hit_rate):
    with pytest.raises(ValueError):
        generate_synthetic_data(num_ids, num_queries, hit_rate)