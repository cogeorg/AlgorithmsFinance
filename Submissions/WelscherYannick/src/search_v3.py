"""Version 3 (second revision) of the three search methods (contract: see interface.py).

The only change from v2: the binary-search loop makes one comparison per step
instead of two.

    v2  per step: `s[mid] == q`, then `s[mid] < q`. Stops early on a hit, but
        an absent query always pays both comparisons in every step.
    v3  per step: only `s[mid] < q`. The loop narrows the range to the first
        position whose value is >= q (the "lower bound"); after the loop one
        equality check decides whether q is present. It always takes about
        log2(n) steps (no early exit), but each step is cheaper.

Correctness: before every check of `lo < hi`, all entries left of lo are < q
and all entries from hi on are >= q. Each step keeps this and shrinks hi - lo,
so the loop ends with lo == hi = the first index whose value is >= q (or
len(s)). q occurs exactly when that index exists and holds q.

Structure, half-open range and midpoint are as in v2, and linear search, hash
membership and binary preparation are imported from v1, so a difference in
measurements comes from the loop body alone.
"""

from interface import Method
from search_v1 import binary_prepare, hash_prepare, hash_query, linear_prepare, linear_query


def _binary_search_lower_bound(s, q):
    """Return True if q occurs in the sorted list s."""
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi) // 2
        if s[mid] < q:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(s) and s[lo] == q


def binary_query(sorted_ids, queries):
    return [_binary_search_lower_bound(sorted_ids, q) for q in queries]


METHODS = {
    "linear": Method("linear", linear_prepare, linear_query),
    "binary": Method("binary", binary_prepare, binary_query),
    "hash": Method("hash", hash_prepare, hash_query),
}
