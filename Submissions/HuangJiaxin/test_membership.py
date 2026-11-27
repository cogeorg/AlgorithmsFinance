"""Tests written before the implementation. Run with:  python -m pytest -q

Every method must pass exactly the same tests.
"""
import random

import pytest

from data import make_ids, make_queries
from membership import METHODS, run

ALL = list(METHODS)


def expected(ids, queries):
    """Independent reference answer (Python's own `in` on a list)."""
    return [x in ids for x in queries]


@pytest.mark.parametrize("method", ALL)
def test_slide_example(method):
    assert run(method, [7, 11, 7], [11, 9, 7]) == [True, False, True]


@pytest.mark.parametrize("method", ALL)
def test_empty_array(method):
    assert run(method, [], [1, 2, 3]) == [False, False, False]


@pytest.mark.parametrize("method", ALL)
def test_empty_queries(method):
    assert run(method, [7, 11], []) == []


@pytest.mark.parametrize("method", ALL)
def test_both_empty(method):
    assert run(method, [], []) == []


@pytest.mark.parametrize("method", ALL)
def test_one_entry(method):
    assert run(method, [5], [5, 4, 6]) == [True, False, False]


@pytest.mark.parametrize("method", ALL)
def test_duplicates(method):
    assert run(method, [3, 3, 3, 1], [3, 1, 2]) == [True, True, False]


@pytest.mark.parametrize("method", ALL)
def test_unsorted_input(method):
    assert run(method, [9, 1, 8, 2, 7], [7, 9, 1, 5]) == [True, True, True, False]


@pytest.mark.parametrize("method", ALL)
def test_first_and_last_positions(method):
    ids = [4, 8, 15, 16, 23, 42]
    assert run(method, ids, [4, 42]) == [True, True]


@pytest.mark.parametrize("method", ALL)
def test_smaller_and_larger_than_all(method):
    assert run(method, [10, 20, 30], [-5, 0, 99]) == [False, False, False]


@pytest.mark.parametrize("method", ALL)
def test_negative_ids(method):
    assert run(method, [-3, 0, -7], [-7, 3]) == [True, False]


@pytest.mark.parametrize("method", ALL)
def test_output_order_and_repeated_queries(method):
    queries = [2, 1, 2, 3, 1]
    assert run(method, [1, 2], queries) == [True, True, True, False, True]


@pytest.mark.parametrize("method", ALL)
def test_input_unchanged(method):
    ids = [7, 2, 11, 4]
    queries = [11, 3]
    run(method, ids, queries)
    assert ids == [7, 2, 11, 4]
    assert queries == [11, 3]


@pytest.mark.parametrize("method", ALL)
def test_repeated_calls_give_same_answer(method):
    ids, queries = [5, 1, 9], [9, 2]
    assert run(method, ids, queries) == run(method, ids, queries)


@pytest.mark.parametrize("method", ALL)
@pytest.mark.parametrize("dup", ["none", "allowed"])
@pytest.mark.parametrize("hit", [0.0, 0.5, 1.0])
def test_synthetic_against_reference(method, dup, hit):
    ids = make_ids(500, seed=1, duplicates=dup)
    queries = make_queries(ids, 200, hit, seed=1)
    assert run(method, ids, queries) == expected(ids, queries)


@pytest.mark.parametrize("method", ALL)
def test_random_small_cases(method):
    rng = random.Random(2026)
    for _ in range(300):
        ids = [rng.randint(-5, 5) for _ in range(rng.randint(0, 12))]
        queries = [rng.randint(-6, 6) for _ in range(rng.randint(0, 8))]
        assert run(method, ids, queries) == expected(ids, queries)


def test_generator_hit_rate_is_exact():
    ids = make_ids(1000, seed=3)
    queries = make_queries(ids, 100, 0.5, seed=3)
    hits = sum(x in set(ids) for x in queries)
    assert hits == 50
    assert len(queries) == 100


@pytest.mark.parametrize("q, hit, want", [(1, 0.5, 1), (3, 0.5, 2), (2, 0.5, 1),
                                          (1, 0.0, 0), (1, 1.0, 1), (100, 0.5, 50)])
def test_generator_small_q_rounding(q, hit, want):
    """Audit bug 1: round(0.5) == 0 made q = 1 'mixed' an all-absent batch."""
    ids = make_ids(1000, seed=5)
    queries = make_queries(ids, q, hit, seed=5)
    assert len(queries) == q
    assert sum(x in set(ids) for x in queries) == want


def test_generator_mixed_differs_from_absent_for_q1():
    ids = make_ids(1000, seed=7)
    assert make_queries(ids, 1, 0.5, seed=7) != make_queries(ids, 1, 0.0, seed=7)


@pytest.mark.parametrize("q, hit", [(10, 1.5), (10, -0.5), (10, 2.0), (-1, 0.5)])
def test_generator_rejects_invalid_arguments(q, hit):
    """Audit bug 3: invalid hit rates used to return more than q queries."""
    with pytest.raises(ValueError):
        make_queries(make_ids(10, seed=1), q, hit, seed=1)


@pytest.mark.parametrize("ids", [[1, 3, 5, 7, 9, 11], [-10, -4], [-3, 0, 3], [5]])
@pytest.mark.parametrize("hit", [0.0, 0.5, 1.0])
def test_generator_any_integer_ids(ids, hit):
    """Audit bug 4: absent queries must be absent for odd and negative IDs too."""
    queries = make_queries(ids, 10, hit, seed=1)
    assert len(queries) == 10
    assert sum(x in set(ids) for x in queries) == round(10 * hit)


def test_generator_empty_ids_all_absent():
    assert len(make_queries([], 5, 0.0, seed=1)) == 5
    with pytest.raises(ValueError):
        make_queries([], 5, 0.5, seed=1)


def test_generator_is_reproducible():
    assert make_ids(100, seed=9) == make_ids(100, seed=9)
    a = make_queries(make_ids(100, seed=9), 20, 0.5, seed=9)
    b = make_queries(make_ids(100, seed=9), 20, 0.5, seed=9)
    assert a == b
