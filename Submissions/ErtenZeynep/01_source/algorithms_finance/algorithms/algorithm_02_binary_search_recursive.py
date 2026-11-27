"""Original manual Binary Search implementation using recursion."""

from __future__ import annotations

from collections.abc import Sequence


def prepare_binary_search(array: Sequence[int]) -> list[int]:
    """Create the sorted copy required by Binary Search."""

    return sorted(array)


def _contains_recursive(
    sorted_array: Sequence[int],
    target: int,
    left: int,
    right: int,
) -> bool:
    if left > right:
        return False

    midpoint = left + (right - left) // 2
    midpoint_value = sorted_array[midpoint]

    if midpoint_value == target:
        return True
    if target < midpoint_value:
        return _contains_recursive(sorted_array, target, left, midpoint - 1)
    return _contains_recursive(sorted_array, target, midpoint + 1, right)


def query_binary_search_recursive(
    sorted_array: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Search an already sorted array once for every ordered query."""

    right = len(sorted_array) - 1
    return [
        _contains_recursive(sorted_array, query, 0, right)
        for query in queries
    ]


def binary_search_recursive(
    array: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Sort a copy, then run recursive Binary Search for every query."""

    sorted_array = prepare_binary_search(array)
    return query_binary_search_recursive(sorted_array, queries)
