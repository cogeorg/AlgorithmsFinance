"""Membership-query algorithms sharing one public specification."""

from typing import List, Sequence, Set


def prepare_linear(ids: Sequence[int]) -> Sequence[int]:
    """Return the input reference because linear search needs no preparation."""
    return ids


def query_linear(ids: Sequence[int], queries: Sequence[int]) -> List[bool]:
    """Search the prepared ID sequence from left to right for every query."""
    results = []

    for query in queries:
        found = False
        for candidate in ids:
            if candidate == query:
                found = True
                break
        results.append(found)

    return results


def linear_search(ids: Sequence[int], queries: Sequence[int]) -> List[bool]:
    """Prepare and run linear search using the shared public interface."""
    prepared_ids = prepare_linear(ids)
    return query_linear(prepared_ids, queries)


def prepare_binary(ids: Sequence[int]) -> List[int]:
    """Return a sorted copy, leaving the caller's sequence unchanged."""
    return sorted(ids)


def _recursive_binary_contains(
    sorted_ids: Sequence[int], query: int, low: int, high: int
) -> bool:
    """Return whether one query occurs between inclusive bounds."""
    if low > high:
        return False

    middle = low + (high - low) // 2
    middle_value = sorted_ids[middle]

    if middle_value == query:
        return True
    if query < middle_value:
        return _recursive_binary_contains(sorted_ids, query, low, middle - 1)
    return _recursive_binary_contains(sorted_ids, query, middle + 1, high)


def query_binary_recursive(
    sorted_ids: Sequence[int], queries: Sequence[int]
) -> List[bool]:
    """Original version: query a prepared sequence using recursion."""
    final_index = len(sorted_ids) - 1
    return [
        _recursive_binary_contains(sorted_ids, query, 0, final_index)
        for query in queries
    ]


def binary_search_recursive(
    ids: Sequence[int], queries: Sequence[int]
) -> List[bool]:
    """Original version: sort a copy, then use recursive binary search."""
    sorted_ids = prepare_binary(ids)
    return query_binary_recursive(sorted_ids, queries)


def query_binary_iterative(
    sorted_ids: Sequence[int], queries: Sequence[int]
) -> List[bool]:
    """Revised version: query a prepared sequence using iteration."""
    results = []

    for query in queries:
        low = 0
        high = len(sorted_ids) - 1
        found = False

        while low <= high:
            middle = low + (high - low) // 2
            middle_value = sorted_ids[middle]

            if middle_value == query:
                found = True
                break
            if query < middle_value:
                high = middle - 1
            else:
                low = middle + 1

        results.append(found)

    return results


def binary_search_iterative(
    ids: Sequence[int], queries: Sequence[int]
) -> List[bool]:
    """Revised version: sort a copy, then use iterative binary search."""
    sorted_ids = prepare_binary(ids)
    return query_binary_iterative(sorted_ids, queries)


def binary_search(ids: Sequence[int], queries: Sequence[int]) -> List[bool]:
    """Run the revised binary-search version using the shared interface."""
    return binary_search_iterative(ids, queries)


def prepare_hash(ids: Sequence[int]) -> Set[int]:
    """Build the standard-library hash set used for membership queries."""
    return set(ids)


def query_hash(id_set: Set[int], queries: Sequence[int]) -> List[bool]:
    """Answer ordered membership queries against a prepared hash set."""
    return [query in id_set for query in queries]


def hash_set_search(ids: Sequence[int], queries: Sequence[int]) -> List[bool]:
    """Prepare and query a standard-library hash set."""
    id_set = prepare_hash(ids)
    return query_hash(id_set, queries)
