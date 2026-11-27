"""Original versions (v1) of the three membership methods.

Shared specification: see ``membership/__init__.py`` (LAB_SPEC.md F1-F6).

Input   ids: sequence of ints (unsorted, duplicates and negatives allowed, may be empty).
        queries: sequence of ints (may be empty, may repeat).
Output  New list[bool], one answer per query, in query order (F3).
Inputs  Never modified (F4). ``prepare`` returns either the input itself (linear,
        read-only) or a new object (binary: sorted copy, hash: set).

Method  prepare                      query (per query)             total for q queries
linear  none, returns ids    O(1)    scan, stop at first match O(n)   O(n*q)
binary  sorted(ids) copy O(n log n)  recursive + slicing       O(n)   O(n log n + n*q)
hash    set(ids)       expected O(n) set lookup       expected O(1)   expected O(n + q)

v1 binary search is deliberately naive (decision Q3): every recursive call slices
the list, which copies up to half of it. The copies add up to n/2 + n/4 + ... < n
elements per query, so one query costs O(n) time and O(n) extra memory instead of
O(log n). The comparisons are still only O(log n). This is revised in v2.

Edge cases: empty ids -> every answer False; empty queries -> []; duplicates in ids
do not matter (membership only); duplicate queries are answered independently.
"""

from __future__ import annotations

from collections.abc import Sequence

# --- Linear search -------------------------------------------------------------


def linear_prepare(ids: Sequence[int]) -> Sequence[int]:
    """Return the input itself as the state: no copy, no preparation cost.

    The state is only read by ``linear_query``, so the caller's array stays unchanged.
    """
    return ids


def linear_query(state: Sequence[int], queries: Sequence[int]) -> list[bool]:
    """For each query, scan ``state`` from the left and stop at the first match.

    Loop invariant (inner loop): ``x`` is not among the elements already scanned.
    Complexity: O(n) per query in the worst case (absent query, full scan),
    O(n*q) in total. Extra space: O(q) for the result.
    """
    result: list[bool] = []
    for x in queries:
        found = False
        for value in state:
            if value == x:
                found = True
                break
        result.append(found)
    return result


# --- Binary search (recursive, slicing) ---------------------------------------


def binary_prepare(ids: Sequence[int]) -> list[int]:
    """Return a new sorted list. ``sorted`` copies, so the caller's array is not sorted
    in place (F4). Complexity: O(n log n) time, O(n) extra space."""
    return sorted(ids)


def binary_contains_recursive(arr: list[int], x: int) -> bool:
    """Return True if ``x`` occurs in the sorted list ``arr`` (recursive, slicing).

    Invariant: if ``x`` occurs in the full sorted array, it occurs in ``arr``.
        All elements cut away to the left are <= arr[mid] < x, and all elements cut
        away to the right are >= arr[mid] > x, so no copy of ``x`` is lost.
    Termination: ``arr[mid]`` is never part of the next slice, so the length shrinks
        by at least 1 per call; the base case is the empty list.
    Complexity: O(log n) calls and comparisons, but each slice copies up to half of
        ``arr``: O(n) time and O(n) extra memory per query in total. Recursion depth
        is about log2(n) + 1 (18 for n = 100,000), far below Python's limit of 1000.
    """
    if not arr:
        return False
    mid = len(arr) // 2
    value = arr[mid]
    if value == x:
        return True
    if x < value:
        return binary_contains_recursive(arr[:mid], x)  # copy of the left half
    return binary_contains_recursive(arr[mid + 1 :], x)  # copy of the right half


def binary_query(state: list[int], queries: Sequence[int]) -> list[bool]:
    """For each query, run the recursive, slicing binary search on the sorted ``state``.

    ``state`` must come from ``binary_prepare``. It is not modified (slicing creates new
    lists). Complexity: O(n) per query because of the slices, O(n*q) in total.
    """
    result: list[bool] = []
    for x in queries:
        result.append(binary_contains_recursive(state, x))
    return result


# --- Hash set -----------------------------------------------------------------


def hash_prepare(ids: Sequence[int]) -> set[int]:
    """Return a new ``set`` of the IDs. Duplicates collapse into one entry.

    Complexity: expected O(n) time, O(n) extra space.
    """
    return set(ids)


def hash_query(state: set[int], queries: Sequence[int]) -> list[bool]:
    """For each query, check membership in the set ``state`` (allowed by F6).

    Complexity: expected O(1) per query, expected O(q) in total. (Worst case O(n) per
    lookup if many keys collide; this does not happen for small Python ints, whose
    hash is the value itself.)
    """
    return [x in state for x in queries]
