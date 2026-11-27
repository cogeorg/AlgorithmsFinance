"""Generator tests that pass before the search algorithms exist."""

import pytest

from Submissions.VoronkovMaksim.synthetic_data import generate_data


@pytest.mark.parametrize("n,q,hit_rate,allow_duplicates", [
    (0, 0, 0.5, True),
    (0, 4, 0.0, True),
    (1, 1, 1.0, True),
    (100, 100, 0.0, True),
    (100, 100, 0.5, True),
    (100, 100, 1.0, True),
    (100, 100, 0.5, False),
    (1000, 1, 1.0, False),
    (10000, 100, 0.5, True),
    (100000, 1, 0.0, False),
])
def test_lengths_types_and_hit_counts(n, q, hit_rate, allow_duplicates):
    ids, queries = generate_data(n, q, hit_rate, allow_duplicates, seed=42)
    assert len(ids) == n
    assert len(queries) == q
    assert all(type(value) is int for value in ids + queries)
    assert sum(query in ids for query in queries) == int(q * hit_rate + 0.5)
    if not allow_duplicates:
        assert len(set(ids)) == len(ids)


def test_same_seed_repeats_exactly():
    assert generate_data(100, 100, seed=17) == generate_data(100, 100, seed=17)


def test_different_seeds_can_differ():
    assert generate_data(100, 10, seed=17) != generate_data(100, 10, seed=18)


def test_duplicates_are_allowed():
    ids, _ = generate_data(100, 0, allow_duplicates=True)
    assert len(set(ids)) < len(ids)


def test_empty_query_batch():
    ids, queries = generate_data(10, 0, hit_rate=1.0)
    assert len(ids) == 10
    assert queries == []


@pytest.mark.parametrize("kwargs,error", [
    ({"n": -1, "q": 1}, ValueError),
    ({"n": 1, "q": -1}, ValueError),
    ({"n": 1, "q": 1, "hit_rate": -0.1}, ValueError),
    ({"n": 1, "q": 1, "hit_rate": 1.1}, ValueError),
    ({"n": 0, "q": 1, "hit_rate": 0.5}, ValueError),
    ({"n": 0, "q": 1, "hit_rate": 1.0}, ValueError),
    ({"n": True, "q": 1}, TypeError),
    ({"n": 1, "q": False}, TypeError),
    ({"n": 1, "q": 1, "seed": True}, TypeError),
    ({"n": 1, "q": 1, "allow_duplicates": 1}, TypeError),
    ({"n": 1, "q": 1, "hit_rate": True}, ValueError),
])
def test_invalid_generator_parameters(kwargs, error):
    with pytest.raises(error):
        generate_data(**kwargs)
