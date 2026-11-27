"""Membership of queries in an integer ID array, three methods (Classes 3-4, Lab Phase 1).

Common interface for every method:
    method(ids, queries) -> list[bool]
One bool per query, same order as `queries`. `ids` and `queries` are never changed.

Both search procedures are written by hand. Allowed library parts: sorted() and set().
The operator `in` on a list is not used by the methods.

Each method is built from two phases so that the timing script can measure them apart:
    prepare(ids)            -> state     (sorting / set construction / nothing)
    answer(state, queries)  -> list[bool]
The public method is exactly answer(prepare(ids), queries): the code that is timed is
the code that is tested. `answer` must not change `state`, so one state can serve many
batches. `PHASES` maps each method name to its (prepare, answer) pair.
"""


# ---- linear search (v1) ---------------------------------------------------------

def _linear_prepare(ids):
    """No preparation: the state is the input itself (no copy)."""
    return ids


def _linear_answer(ids, queries):
    """For each query, scan `ids` from the first entry until a match or the end.

    Time: O(n) per query, so O(n * q) for q queries. Extra memory: O(q) for the output.
    """
    result = []
    for query in queries:
        found = False
        for item in ids:
            if item == query:
                found = True
                break
        result.append(found)
    return result


def linear_search(ids, queries):
    return _linear_answer(_linear_prepare(ids), queries)


# ---- binary search: shared preparation ------------------------------------------

def _binary_prepare(ids):
    """Sorted copy. Preparation: O(n log n) time, O(n) memory. `ids` stays as it was."""
    return sorted(ids)


# ---- binary search v1: recursive ------------------------------------------------

def _search_recursive(sorted_ids, query, low, high):
    """Is `query` among sorted_ids[low..high] (both ends included)?

    Invariant: if `query` is anywhere in sorted_ids, it lies in sorted_ids[low..high].
    Each call either finds it or cuts the range to at most half. Empty range -> absent.
    """
    if low > high:
        return False
    middle = (low + high) // 2
    value = sorted_ids[middle]
    if value == query:
        return True
    if value < query:
        return _search_recursive(sorted_ids, query, middle + 1, high)
    return _search_recursive(sorted_ids, query, low, middle - 1)


def _binary_recursive_answer(sorted_ids, queries):
    """Per query: O(log n) time, recursion depth O(log n)."""
    last = len(sorted_ids) - 1
    return [_search_recursive(sorted_ids, query, 0, last) for query in queries]


def binary_search_recursive(ids, queries):
    """Sort a copy once, then answer every query by recursive binary search.

    Total: O(n log n + q log n) time, O(n + q) extra memory.
    """
    return _binary_recursive_answer(_binary_prepare(ids), queries)


# ---- binary search v2: iterative ------------------------------------------------

def _binary_iterative_answer(sorted_ids, queries):
    """Same idea and invariant as v1: if the query is in `sorted_ids`, it lies in
    sorted_ids[low..high]; the range is cut to at most half per loop pass.
    Per query: O(log n) time, O(1) extra memory (no recursion stack, no helper call).
    """
    last = len(sorted_ids) - 1
    result = []
    for query in queries:
        low, high = 0, last
        found = False
        while low <= high:
            middle = (low + high) // 2
            value = sorted_ids[middle]
            if value == query:
                found = True
                break
            if value < query:
                low = middle + 1
            else:
                high = middle - 1
        result.append(found)
    return result


def binary_search_iterative(ids, queries):
    """Version 2 of binary search: a loop instead of recursion, no work without queries.

    The sorted copy stays (the input may be unsorted and must not change); it is skipped
    only when there is nothing to answer. Total: O(n log n + q log n) time, O(n + q) memory.
    """
    if not queries:
        return []                       # nothing to answer: do not sort or copy
    return _binary_iterative_answer(_binary_prepare(ids), queries)


# ---- hash set -------------------------------------------------------------------

def _hash_prepare(ids):
    """Python set. Preparation: O(n) on average. Duplicates collapse inside the set."""
    return set(ids)


def _hash_answer(lookup, queries):
    """Per query: O(1) on average, O(n) worst case (many hash collisions)."""
    return [query in lookup for query in queries]


def hash_set_membership(ids, queries):
    """Build a Python set once, then answer every query with a hash lookup.

    Total: O(n + q) time on average, O(n + q) extra memory.
    """
    return _hash_answer(_hash_prepare(ids), queries)


# ---- registries -----------------------------------------------------------------
# Version 1 stays unchanged; version 2 only revises binary search.
METHODS = {
    "linear_v1": linear_search,
    "binary_v1": binary_search_recursive,
    "binary_v2": binary_search_iterative,
    "hash_v1": hash_set_membership,
}

PHASES = {
    "linear_v1": (_linear_prepare, _linear_answer),
    "binary_v1": (_binary_prepare, _binary_recursive_answer),
    "binary_v2": (_binary_prepare, _binary_iterative_answer),
    "hash_v1": (_hash_prepare, _hash_answer),
}
