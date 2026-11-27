"""Shared functional contract and mandatory correctness examples."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from conftest import SearchFunction


EDGE_CASES = (
    ("empty_everything", [], [], []),
    ("empty_array", [], [1, -1], [False, False]),
    ("empty_queries", [1, 2], [], []),
    ("single_hit", [7], [7], [True]),
    ("single_miss", [7], [8], [False]),
    ("duplicates", [7, 11, 7], [11, 9, 7], [True, False, True]),
    (
        "unsorted",
        [5, 1, 9, 3],
        [3, 5, 4, 9],
        [True, True, False, True],
    ),
    ("all_identical", [2, 2, 2], [2, 3, 2], [True, False, True]),
    ("negative_and_zero", [-3, 0, 4], [-3, 1, 0], [True, False, True]),
    (
        "repeated_queries",
        [1, 2, 3],
        [3, 1, 3, 2],
        [True, True, True, True],
    ),
    (
        "binary_boundaries",
        [10, 20, 30, 40],
        [10, 40, 25],
        [True, True, False],
    ),
    ("input_immutability", [3, 1, 2], [2], [True]),
    ("very_large_integers", [10**100, 0], [10**100, -(10**100)], [True, False]),
)


@pytest.mark.parametrize(
    ("case_name", "array", "queries", "expected"),
    EDGE_CASES,
    ids=[case[0] for case in EDGE_CASES],
)
def test_shared_search_contract(
    algorithm: SearchFunction,
    case_name: str,
    array: list[int],
    queries: list[int],
    expected: list[bool],
) -> None:
    """Every implementation must satisfy the same observable contract."""

    del case_name
    original_array = array.copy()
    original_queries = queries.copy()

    result = algorithm(array, queries)

    assert isinstance(result, list)
    assert result == expected
    assert len(result) == len(queries)
    assert all(type(value) is bool for value in result)
    assert array == original_array
    assert queries == original_queries


@pytest.mark.parametrize(
    ("array", "queries"),
    (
        ([4, 1, 7], [7, 2, 1]),
        ([5, 5, 8], [5, 9, 5]),
        ([-10, 0, 10], [11, -10, 0]),
    ),
)
def test_output_matches_independent_membership_oracle(
    algorithm: SearchFunction,
    array: list[int],
    queries: list[int],
) -> None:
    result = algorithm(array, queries)
    assert result == [query in array for query in queries]
