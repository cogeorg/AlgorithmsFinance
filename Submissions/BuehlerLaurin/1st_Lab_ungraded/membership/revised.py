"""Revised versions (v2) of the three membership methods.

Shared specification: see ``membership/__init__.py`` (LAB_SPEC.md F1-F6).
The original module is never edited by the revision (R5).

Decisions (LAB_SPEC.md section 4):
    Q3  binary: the fastest correct hand-written binary search we can find.
        Two candidates are implemented and tested with the same test suite:
          * ``binary_query_classic``     three-way comparison, stops early on a hit
          * ``binary_query_lower_bound`` one ``<`` per step, one ``==`` at the end
        ``binary_query`` (the registered v2) is the faster one, chosen by measurement
        with ``bench/binary_variants.py``; see docs/REVISION.md.
    Q4  linear and hash: unchanged. The v1 functions are re-exported here.

What changed against v1 binary search
    1. No slicing: the search works on index bounds ``lo``/``hi`` inside the one sorted
       copy made by ``binary_prepare``. This removes the O(n) copying per query.
    2. Iterative instead of recursive: no function call per step, no recursion depth.
    3. The search loop is inlined in the query loop: no function call per query.
    The sorted copy in ``binary_prepare`` stays; it is required, because sorting the
    caller's list in place would break F4.

Complexity (both candidates)
    prepare O(n log n) time, O(n) extra space (the sorted copy)
    query   O(log n) per query, O(q log n) per batch; O(1) extra space per query
            besides the O(q) result list.
"""

from __future__ import annotations

from collections.abc import Sequence

# Q4: unchanged in v2, reused from v1.
from membership.original import (  # noqa: F401  (re-exported)
    hash_prepare,
    hash_query,
    linear_prepare,
    linear_query,
)


def binary_prepare(ids: Sequence[int]) -> list[int]:
    """Return a new sorted list (same as v1). ``sorted`` copies, so the caller's
    array is not sorted in place (F4). O(n log n) time, O(n) extra space."""
    return sorted(ids)


def binary_query_classic(state: list[int], queries: Sequence[int]) -> list[bool]:
    """Iterative binary search with a three-way comparison and early exit.

    Invariant: if ``x`` occurs in ``state``, it occurs in ``state[lo:hi + 1]``.
        Elements left of ``lo`` are < x, elements right of ``hi`` are > x.
    Termination: every step either returns or shrinks ``hi - lo`` by at least 1;
        the loop ends when ``lo > hi`` (empty range -> absent).
    Cost per query: at most about log2(n) + 1 steps, each with up to two
    comparisons (``==`` then ``<``). A hit can stop early.
    """
    result: list[bool] = []
    last = len(state) - 1
    for x in queries:
        lo = 0
        hi = last
        found = False
        while lo <= hi:
            mid = (lo + hi) // 2
            value = state[mid]
            if value == x:
                found = True
                break
            if value < x:
                lo = mid + 1
            else:
                hi = mid - 1
        result.append(found)
    return result


def binary_query_lower_bound(state: list[int], queries: Sequence[int]) -> list[bool]:
    """Iterative lower-bound binary search: one ``<`` per step, one ``==`` at the end.

    Finds the first index ``lo`` with ``state[lo] >= x`` (or ``n`` if there is none),
    then checks whether ``state[lo] == x``.
    Invariant: all elements in ``state[:lo]`` are < x and all elements in
        ``state[hi:]`` are >= x. Start: lo = 0, hi = n (both parts empty).
    Termination: ``mid`` lies in ``[lo, hi)``, so each step shrinks ``hi - lo``;
        the loop ends with ``lo == hi`` = the first index whose value is >= x.
    Cost per query: always about log2(n) steps with one comparison each, plus one
    final comparison. It never stops early, but its loop body is shorter.
    """
    result: list[bool] = []
    n = len(state)
    for x in queries:
        lo = 0
        hi = n
        while lo < hi:
            mid = (lo + hi) // 2
            if state[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        result.append(lo < n and state[lo] == x)
    return result


# The registered v2 query (decision Q3: the faster candidate, see docs/REVISION.md).
binary_query = binary_query_lower_bound
