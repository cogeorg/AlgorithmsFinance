"""BinarySearch on a sorted copy.

Preparation: ``sorted(ids)`` builds a new list, O(n log n); the input is unchanged.
Query batch: O(log n) per query, O(q log n) per batch.

v1 (original) is recursive with an early exit on equality.
v2 (revised) is iterative (no call overhead, no recursion-depth concerns) and
uses the lower-bound form: it narrows to the first position whose value is
>= the query, then checks that one position.
"""


def prepare(ids):
    """Library sort (allowed by the assignment); returns a new list."""
    return sorted(ids)


# --- v1 (original): recursive ------------------------------------------------------

def _contains_recursive(a, x, lo, hi):
    """Search a[lo:hi] (hi exclusive) without slicing."""
    if lo >= hi:
        return False
    mid = (lo + hi) // 2
    value = a[mid]
    if value == x:
        return True
    if value < x:
        return _contains_recursive(a, x, mid + 1, hi)
    return _contains_recursive(a, x, lo, mid)


def query_v1(sorted_ids, queries):
    n = len(sorted_ids)
    return [_contains_recursive(sorted_ids, q, 0, n) for q in queries]


# --- v2 (revised): iterative lower bound ------------------------------------------

def _contains_iterative(a, x):
    lo, hi = 0, len(a)
    while lo < hi:  # invariant: a[:lo] < x <= a[hi:]
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(a) and a[lo] == x


def query_v2(sorted_ids, queries):
    return [_contains_iterative(sorted_ids, q) for q in queries]
