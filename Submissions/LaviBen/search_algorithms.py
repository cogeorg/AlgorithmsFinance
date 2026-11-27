"""Membership algorithms with a shared ordered-query contract.

Each public function accepts an integer ID sequence and an ordered query
sequence. It returns one Boolean per query without changing either input.
"""

from __future__ import annotations

from collections.abc import Sequence


def prepare_linear(ids: Sequence[int]) -> Sequence[int]:
    """Linear search needs no index; retain the read-only input reference."""

    return ids


def linear_query_batch(
    prepared_ids: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Run a complete ordered query batch by scanning left to right."""

    results: list[bool] = []
    for query in queries:
        found = False
        for candidate in prepared_ids:
            if candidate == query:
                found = True
                break
        results.append(found)
    return results


def linear_search(ids: Sequence[int], queries: Sequence[int]) -> list[bool]:
    """Prepare and run manual linear membership queries."""

    return linear_query_batch(prepare_linear(ids), queries)


def _recursive_contains(
    sorted_ids: Sequence[int],
    query: int,
    low: int,
    high: int,
) -> bool:
    """Return whether ``query`` occurs between inclusive indices low/high."""

    if low > high:
        return False

    middle = low + (high - low) // 2
    candidate = sorted_ids[middle]
    if candidate == query:
        return True
    if candidate < query:
        return _recursive_contains(sorted_ids, query, middle + 1, high)
    return _recursive_contains(sorted_ids, query, low, middle - 1)


def prepare_binary(ids: Sequence[int]) -> list[int]:
    """Create the sorted copy shared by both binary-search versions."""

    return sorted(ids)


def binary_recursive_query_batch(
    sorted_ids: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Run recursive binary search on an already sorted sequence."""

    last_index = len(sorted_ids) - 1
    return [
        _recursive_contains(sorted_ids, query, 0, last_index)
        for query in queries
    ]


def binary_search_recursive_v1(
    ids: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Version 1: prepare once, then recursively search every query."""

    return binary_recursive_query_batch(prepare_binary(ids), queries)


def binary_iterative_query_batch(
    sorted_ids: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Run iterative binary search on an already sorted sequence.

    The iterative loop preserves the same ``O(n log n + q log n)`` time bound
    as version 1 while avoiding one Python function call per search step.
    """

    results: list[bool] = []

    for query in queries:
        low = 0
        high = len(sorted_ids) - 1
        found = False

        while low <= high:
            middle = low + (high - low) // 2
            candidate = sorted_ids[middle]
            if candidate == query:
                found = True
                break
            if candidate < query:
                low = middle + 1
            else:
                high = middle - 1

        results.append(found)

    return results


def binary_search(ids: Sequence[int], queries: Sequence[int]) -> list[bool]:
    """Version 2: prepare once, then iteratively search every query."""

    return binary_iterative_query_batch(prepare_binary(ids), queries)


def prepare_hash_set(ids: Sequence[int]) -> set[int]:
    """Build the standard-library hash index used for membership queries."""

    return set(ids)


def hash_set_query_batch(
    lookup: set[int],
    queries: Sequence[int],
) -> list[bool]:
    """Run a complete ordered query batch against a prepared hash set."""

    return [query in lookup for query in queries]


def hash_set_membership(
    ids: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Build one standard-library hash set, then test queries in order."""

    return hash_set_query_batch(prepare_hash_set(ids), queries)
