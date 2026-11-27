"""Original membership algorithms for the Phase 1 lab."""


def prepare_linear(ids: list[int]) -> list[int]:
    """Return the read-only input reference; linear search needs no preparation."""
    return ids


def query_linear(ids: list[int], queries: list[int]) -> list[bool]:
    """Run one complete query batch using explicitly implemented linear search."""
    results: list[bool] = []
    for query in queries:
        found = False
        for id_value in ids:
            if id_value == query:
                found = True
                break
        results.append(found)
    return results


def linear_search(ids: list[int], queries: list[int]) -> list[bool]:
    """Return whether each query occurs in *ids*, using linear search."""
    return query_linear(prepare_linear(ids), queries)


def prepare_binary(ids: list[int]) -> list[int]:
    """Create the sorted copy shared by both binary-search versions."""
    return sorted(ids)


def _recursive_binary_contains(
    sorted_ids: list[int], query: int, low: int, high: int
) -> bool:
    """Search one closed interval of a sorted list recursively."""
    if low > high:
        return False

    middle = (low + high) // 2
    middle_value = sorted_ids[middle]
    if middle_value == query:
        return True
    if query < middle_value:
        return _recursive_binary_contains(sorted_ids, query, low, middle - 1)
    return _recursive_binary_contains(sorted_ids, query, middle + 1, high)


def binary_search_recursive(ids: list[int], queries: list[int]) -> list[bool]:
    """Original version: use recursive search on a sorted copy."""
    sorted_ids = prepare_binary(ids)
    return query_binary_recursive(sorted_ids, queries)


def query_binary_recursive(
    sorted_ids: list[int], queries: list[int]
) -> list[bool]:
    """Run a complete query batch using the original recursive search."""
    last_index = len(sorted_ids) - 1
    return [
        _recursive_binary_contains(sorted_ids, query, 0, last_index)
        for query in queries
    ]


def _iterative_binary_contains(sorted_ids: list[int], query: int) -> bool:
    """Search a sorted list iteratively without slicing or recursion."""
    low = 0
    high = len(sorted_ids) - 1
    while low <= high:
        middle = (low + high) // 2
        middle_value = sorted_ids[middle]
        if middle_value == query:
            return True
        if query < middle_value:
            high = middle - 1
        else:
            low = middle + 1
    return False


def binary_search(ids: list[int], queries: list[int]) -> list[bool]:
    """Revised version: use iterative search on a sorted copy."""
    sorted_ids = prepare_binary(ids)
    return query_binary_iterative(sorted_ids, queries)


def query_binary_iterative(
    sorted_ids: list[int], queries: list[int]
) -> list[bool]:
    """Run a complete query batch using the revised iterative search."""
    return [_iterative_binary_contains(sorted_ids, query) for query in queries]


def prepare_hash_set(ids: list[int]) -> set[int]:
    """Build the standard-library hash set used for membership queries."""
    return set(ids)


def query_hash_set(id_set: set[int], queries: list[int]) -> list[bool]:
    """Run one complete query batch against a prepared set."""
    return [query in id_set for query in queries]


def hash_set_membership(ids: list[int], queries: list[int]) -> list[bool]:
    """Return memberships using a standard-library set."""
    return query_hash_set(prepare_hash_set(ids), queries)
