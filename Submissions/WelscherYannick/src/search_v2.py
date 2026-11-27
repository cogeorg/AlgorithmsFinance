"""Version 2 (the revision) of the three search methods (contract: see interface.py).

The only change from v1: binary search uses a while loop instead of recursion.
The half-open range [lo, hi), the midpoint and the comparisons are exactly the
same as in v1, so any difference in measurements comes from removing the
recursive calls and nothing else.

Linear search, hash membership and binary preparation are imported from v1
unchanged (not copied), so the two versions cannot drift apart.
"""

from interface import Method
from search_v1 import binary_prepare, hash_prepare, hash_query, linear_prepare, linear_query


def _binary_search_iterative(s, q):
    """Return True if q occurs in the sorted list s."""
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi) // 2
        if s[mid] == q:
            return True
        if s[mid] < q:
            lo = mid + 1
        else:
            hi = mid
    return False


def binary_query(sorted_ids, queries):
    return [_binary_search_iterative(sorted_ids, q) for q in queries]


METHODS = {
    "linear": Method("linear", linear_prepare, linear_query),
    "binary": Method("binary", binary_prepare, binary_query),
    "hash": Method("hash", hash_prepare, hash_query),
}
