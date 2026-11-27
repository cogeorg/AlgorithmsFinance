"""Membership algorithms with explicit preparation and query stages.

Pre-refactoring source is preserved under snapshots/. Public interfaces are unchanged.
Preparation owns empty-input checks in the revised version.
"""


def prepare_linear_search(array, queries):
    if not queries or not array:
        return None
    return array


def query_linear_search(array, queries):
    if array is None:
        return [False] * len(queries)
    results = []
    for query in queries:
        found = False
        for value in array:
            if value == query:
                found = True
                break
        results.append(found)
    return results


def linear_search(array: list[int], queries: list[int]) -> list[bool]:
    """Prepare fresh state, then return one Boolean per ordered query."""
    state = prepare_linear_search(array, queries)
    return query_linear_search(state, queries)


def prepare_binary_search(array, queries):
    if not queries or not array:
        return None
    sorted_array = sorted(array)
    return sorted_array


def query_binary_search(sorted_array, queries):
    if sorted_array is None:
        return [False] * len(queries)
    results = []
    for query in queries:
        left, right = (0, len(sorted_array) - 1)
        found = False
        while left <= right:
            middle = (left + right) // 2
            value = sorted_array[middle]
            if value == query:
                found = True
                break
            if value < query:
                left = middle + 1
            else:
                right = middle - 1
        results.append(found)
    return results


def binary_search(array: list[int], queries: list[int]) -> list[bool]:
    """Prepare fresh state, then return one Boolean per ordered query."""
    state = prepare_binary_search(array, queries)
    return query_binary_search(state, queries)


def prepare_hash_set_search(array, queries):
    if not queries or not array:
        return None
    identifiers = set(array)
    return identifiers


def query_hash_set_search(identifiers, queries):
    if identifiers is None:
        return [False] * len(queries)
    return [query in identifiers for query in queries]


def hash_set_search(array: list[int], queries: list[int]) -> list[bool]:
    """Prepare fresh state, then return one Boolean per ordered query."""
    state = prepare_hash_set_search(array, queries)
    return query_hash_set_search(state, queries)
