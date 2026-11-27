"""Cases aimed at realistic search implementation mistakes."""

from __future__ import annotations

import pytest

from conftest import SearchFunction


FAILURE_MODE_CASES = (
    ("first_position_hit", [4, 8, 12, 16], [4], [True]),
    ("middle_position_hit", [4, 8, 12, 16, 20], [12], [True]),
    ("last_position_hit", [4, 8, 12, 16], [16], [True]),
    ("absent_after_first", [4, 8, 12], [9], [False]),
    ("two_elements_sorted", [2, 8], [2, 8, 5], [True, True, False]),
    ("two_elements_unsorted", [8, 2], [2, 8, 5], [True, True, False]),
    ("odd_length", [9, 1, 7, 3, 5], [1, 5, 9, 4], [True, True, True, False]),
    ("even_length", [8, 2, 6, 4], [2, 8, 5], [True, True, False]),
    ("below_minimum", [3, 7, 11], [-1], [False]),
    ("above_maximum", [3, 7, 11], [15], [False]),
    ("between_adjacent", [3, 7, 11], [5, 9], [False, False]),
    (
        "duplicates_around_midpoint",
        [9, 4, 4, 4, 1, 7],
        [4, 7, 6],
        [True, True, False],
    ),
    ("reverse_sorted", [9, 7, 5, 3, 1], [1, 9, 4], [True, True, False]),
    ("all_identical", [6, 6, 6, 6, 6], [6, 5], [True, False]),
    ("sparse_range", [-1_000_000, 0, 1_000_000], [1, 999_999], [False, False]),
)


@pytest.mark.parametrize(
    ("case_name", "array", "queries", "expected"),
    FAILURE_MODE_CASES,
    ids=[case[0] for case in FAILURE_MODE_CASES],
)
def test_algorithm_failure_modes(
    algorithm: SearchFunction,
    case_name: str,
    array: list[int],
    queries: list[int],
    expected: list[bool],
) -> None:
    del case_name
    original_array = array.copy()

    result = algorithm(array, queries)

    assert result == expected
    assert array == original_array
