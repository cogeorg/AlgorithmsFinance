"""The same behavioral specification is applied to every algorithm."""

from collections.abc import Callable

import pytest

from algorithms import (
    binary_search,
    binary_search_recursive,
    hash_set_membership,
    linear_search,
)


SearchMethod = Callable[[list[int], list[int]], list[bool]]


@pytest.fixture(
    params=[
        linear_search,
        binary_search_recursive,
        binary_search,
        hash_set_membership,
    ],
    ids=lambda function: function.__name__,
)
def search_method(request: pytest.FixtureRequest) -> SearchMethod:
    return request.param


@pytest.mark.parametrize(
    ("ids", "queries", "expected"),
    [
        ([], [], []),
        ([], [1, -1], [False, False]),
        ([5], [], []),
        ([5], [5, 4], [True, False]),
        ([7, 11, 7], [11, 9, 7], [True, False, True]),
        ([4, 1, 9, 2], [2, 8, 4, 1], [True, False, True, True]),
        ([3, 3, 3], [3, 2, 3], [True, False, True]),
        ([0, -4, 12], [-4, 0, 13, 12], [True, True, False, True]),
    ],
)
def test_membership_specification(
    search_method: SearchMethod,
    ids: list[int],
    queries: list[int],
    expected: list[bool],
) -> None:
    original_ids = ids.copy()

    result = search_method(ids, queries)

    assert result == expected
    assert ids == original_ids


def test_result_contains_real_booleans(search_method: SearchMethod) -> None:
    result = search_method([10, 20], [20, 99])

    assert all(type(value) is bool for value in result)
