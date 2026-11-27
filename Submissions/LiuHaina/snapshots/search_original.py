"""Three membership-query algorithms: initial implementation.

Each function returns a Boolean list in query order and leaves the given
array unchanged. Sorting and set construction happen inside each call.
"""


def linear_search(array: list[int], queries: list[int]) -> list[bool]:
    """Scan the array for each query; worst-case O(n*q) query work."""
    results = []
    for query in queries:
        found = False
        for value in array:
            if value == query:
                found = True
                break
        results.append(found)
    return results


def binary_search(array: list[int], queries: list[int]) -> list[bool]:
    """Sort a copy, then search it with an iterative binary search.

    Preparation: O(n log n) worst case. Queries: O(q log(n+1)).
    The sorted copy uses O(n) space; required output uses O(q).
    """
    sorted_array = sorted(array)
    results = []
    for query in queries:
        left, right = 0, len(sorted_array) - 1
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


def hash_set_search(array: list[int], queries: list[int]) -> list[bool]:
    """Build a standard-library set and query membership.

    Expected preparation: O(n); expected query batch: O(q), assuming
    well-distributed hashes. These are not worst-case guarantees.
    The set uses O(u) space for u distinct IDs; required output uses O(q).
    """
    identifiers = set(array)
    return [query in identifiers for query in queries]
