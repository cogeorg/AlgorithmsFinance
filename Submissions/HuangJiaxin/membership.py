"""Membership queries on an integer ID array: three methods, one specification.

Specification (Class 2 lab, Phase 1)
    Input:  ids      -- list of integer trade IDs (any order, duplicates allowed, may be empty)
            queries  -- list of integer IDs, in a fixed order (may be empty)
    Output: list of Booleans, one per query, in the same order as `queries`;
            answer j is True exactly when queries[j] occurs in ids.
    The given `ids` list is never modified.

Each method is split into a preparation step and a query step so that the
benchmark can time them separately:
    linear : no preparation (uses the given list directly)
    binary : preparation = sorted copy (library sort), query = our binary search
    hash   : preparation = built-in set,               query = set membership

Revisions (original and revised versions are both kept for comparison):
    Revision 1, BinarySearch
        binary_v1 : ORIGINAL - recursive, passes list slices (each slice is a copy,
                    so one query costs Theta(n) copying instead of Theta(log n))
        binary_v2 : REVISED  - iterative, works with index bounds only, no copies
    Revision 2, LinearSearch
        linear_v1 : ORIGINAL - while loop with an explicit index, as on the slides
        linear_v2 : REVISED  - for loop over the values; same Theta(n) worst case,
                    fewer Python-level operations per entry (constant-factor change)

Reference only (NOT my implementation, not one of the three required methods):
    bisect_ref : sorted copy + the standard library's bisect_left, used to check how
                 far my own binary search is from a library baseline.
"""
from bisect import bisect_left


# ---------------------------------------------------------------- LinearSearch
def linear_contains_v1(ids, x):
    """ORIGINAL version: explicit index i, as in the slides' pseudocode.

    Invariant before each loop check: ids[0..i-1] contain no match.
    """
    i = 0
    n = len(ids)
    while i < n:
        if ids[i] == x:
            return True
        i += 1
    return False


def linear_contains_v2(ids, x):
    """REVISED version: iterate over the values directly (no index bookkeeping)."""
    for v in ids:
        if v == x:
            return True
    return False


def prepare_linear(ids):
    return ids  # nothing to build; no copy


def query_linear_v1(prepared, queries):
    return [linear_contains_v1(prepared, x) for x in queries]


def query_linear_v2(prepared, queries):
    return [linear_contains_v2(prepared, x) for x in queries]


# ---------------------------------------------------------------- BinarySearch
def prepare_binary(ids):
    return sorted(ids)  # new sorted copy; `ids` itself stays unchanged


def binary_contains_v1(sorted_ids, x):
    """ORIGINAL version: recursive, slices the list (each slice is a copy)."""
    if not sorted_ids:
        return False
    m = len(sorted_ids) // 2
    if sorted_ids[m] == x:
        return True
    if sorted_ids[m] < x:
        return binary_contains_v1(sorted_ids[m + 1:], x)
    return binary_contains_v1(sorted_ids[:m], x)


def binary_contains_v2(sorted_ids, x):
    """REVISED version: iterative, keeps index bounds lo..hi, no copies.

    Invariant before each loop check: if x occurs, it occurs in sorted_ids[lo..hi].
    """
    lo, hi = 0, len(sorted_ids) - 1
    while lo <= hi:
        mid = lo + (hi - lo) // 2
        v = sorted_ids[mid]
        if v == x:
            return True
        if v < x:
            lo = mid + 1
        else:
            hi = mid - 1
    return False


def query_binary_v1(prepared, queries):
    return [binary_contains_v1(prepared, x) for x in queries]


def query_binary_v2(prepared, queries):
    return [binary_contains_v2(prepared, x) for x in queries]


# ---------------------------------------------------------------- Hash set
def prepare_hash(ids):
    return set(ids)


def query_hash(prepared, queries):
    return [x in prepared for x in queries]


# ---------------------------------------------------------------- library reference
def query_bisect_ref(prepared, queries):
    n = len(prepared)
    out = []
    for x in queries:
        i = bisect_left(prepared, x)
        out.append(i < n and prepared[i] == x)
    return out


# ---------------------------------------------------------------- registry
METHODS = {
    # name: (prepare, query, version label)
    "linear_v1": (prepare_linear, query_linear_v1, "original"),
    "linear_v2": (prepare_linear, query_linear_v2, "revised"),
    "binary_v1": (prepare_binary, query_binary_v1, "original"),
    "binary_v2": (prepare_binary, query_binary_v2, "revised"),
    "hash": (prepare_hash, query_hash, "single"),
    "bisect_ref": (prepare_binary, query_bisect_ref, "library reference"),
}


def run(method, ids, queries):
    """Full method = preparation followed by the complete query batch."""
    prepare, query, _ = METHODS[method]
    return query(prepare(ids), queries)
