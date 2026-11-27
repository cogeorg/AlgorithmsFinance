"""Three membership search methods; inputs and query order are preserved."""

from bisect import bisect_left


def linear_search(ids, queries):
    """Scan the original IDs for each query: O(nq) time."""
    return [query in ids for query in queries]


def binary_search(ids, queries):
    """Sort a copy once, then bisect: O(n log n + q log n) time."""
    ordered = sorted(ids)
    answers = []
    for query in queries:
        position = bisect_left(ordered, query)
        answers.append(position < len(ordered) and ordered[position] == query)
    return answers


def set_search(ids, queries):
    """Build a set once, then look up queries: expected O(n + q) time."""
    lookup = set(ids)
    return [query in lookup for query in queries]


SEARCH_METHODS = {
    "linear": linear_search,
    "binary": binary_search,
    "set": set_search,
}
