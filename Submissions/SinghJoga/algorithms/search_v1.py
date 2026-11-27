def linear_search(ids: list[int], queries: list[int]) -> list[bool]:
    """Return one actual bool per ordered integer query for an integer ID list.

    Preserve query order and leave both input lists unchanged.
    """
    results = []
    for query in queries:
        found = False
        for id_value in ids:
            if id_value == query:
                found = True
                break
        results.append(found)
    return results


def binary_search(ids: list[int], queries: list[int]) -> list[bool]:
    """Return one actual bool per ordered integer query for an integer ID list.

    Preserve query order and leave both input lists unchanged. Search a
    sorted copy of ``ids``.
    """
    sorted_ids = sorted(ids)

    def contains(query: int, low: int, high: int) -> bool:
        if low > high:
            return False

        middle = (low + high) // 2
        middle_value = sorted_ids[middle]
        if middle_value == query:
            return True
        if query < middle_value:
            return contains(query, low, middle - 1)
        return contains(query, middle + 1, high)

    return [
        contains(query, 0, len(sorted_ids) - 1)
        for query in queries
    ]


def hash_membership(ids: list[int], queries: list[int]) -> list[bool]:
    """Return one actual bool per ordered integer query for an integer ID list.

    Preserve query order and leave both input lists unchanged.
    """
    id_set = set(ids)
    return [query in id_set for query in queries]
