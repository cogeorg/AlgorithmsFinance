"""Revised manual Binary Search implementation using iteration."""

from __future__ import annotations

from collections.abc import Sequence


def prepare_binary_search(array: Sequence[int]) -> list[int]:
    """Create the sorted copy required by Binary Search."""

    return sorted(array)


def _contains_iterative(
    sorted_array: Sequence[int],
    target: int,
) -> bool:
    left = 0
    right = len(sorted_array) - 1

    while left <= right:
        midpoint = left + (right - left) // 2
        midpoint_value = sorted_array[midpoint]

        if midpoint_value == target:
            return True
        if target < midpoint_value:
            right = midpoint - 1
        else:
            left = midpoint + 1

    return False


def query_binary_search_iterative(
    sorted_array: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Search an already sorted array once for every ordered query."""

    return [_contains_iterative(sorted_array, query) for query in queries]


def binary_search_iterative(
    array: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Sort a copy, then run iterative Binary Search for every query."""

    sorted_array = prepare_binary_search(array)
    return query_binary_search_iterative(sorted_array, queries)
