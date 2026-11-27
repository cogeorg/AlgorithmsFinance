"""Shared correctness tests for all three membership-query methods."""

import pytest

from algorithms import (
    binary_search,
    binary_search_iterative,
    binary_search_recursive,
    hash_set_search,
    linear_search,
)


SEARCH_METHODS = (
    linear_search,
    binary_search_recursive,
    binary_search_iterative,
    binary_search,
    hash_set_search,
)


@pytest.mark.parametrize("search_method", SEARCH_METHODS)
@pytest.mark.parametrize(
    ("ids", "queries", "expected"),
    [
        ([], [], []),
        ([], [1, -1], [False, False]),
        ([42], [], []),
        ([42], [42, 7], [True, False]),
        ([7, 11, 7], [11, 9, 7], [True, False, True]),
        ([5, -2, 10, 5, 0], [0, 5, 8, -2, 10], [True, True, False, True, True]),
            ([2, 4, 6], [4, 4, 5, 4], [True, True, False, True]),
   ],
)
def test_membership_results(search_method, ids, queries, expected):
    """Every method must return the same ordered Boolean results."""
    result = search_method(ids, queries)

    assert result == expected
    assert all(type(value) is bool for value in result)


@pytest.mark.parametrize("search_method", SEARCH_METHODS)
def test_input_array_is_unchanged(search_method):
    """Searching may build a copy but must not modify the given array."""
    ids = [9, 1, 9, 3, -4]
    original_ids = ids.copy()

    search_method(ids, [3, 2, 9])

    assert ids == original_ids
