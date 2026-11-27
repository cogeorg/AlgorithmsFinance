"""Version 1 of the three search methods (contract: see interface.py).

linear  preparation copies ids into a tuple; each query scans it until the first match.
binary  preparation sorts a copy; each query runs a recursive binary search.
hash    preparation builds a built-in set; each query is a set lookup.

Library sorting and sets are allowed; both search procedures are written here
by hand (slide 57). Version 2 replaces the recursive binary search with an
iterative one.
"""

from interface import Method


# --- Linear search -----------------------------------------------------------

def linear_prepare(ids):
    # Linear search needs no ordering, but the state must not follow later
    # changes to ids (see interface.py). An immutable tuple copy guarantees
    # that; it costs O(n) time and 8 bytes per entry.
    return tuple(ids)


def linear_query(ids, queries):
    result = []
    for q in queries:
        found = False
        for x in ids:
            if x == q:
                found = True
                break
        result.append(found)
    return result


# --- Binary search on a sorted copy (recursive) ------------------------------

def binary_prepare(ids):
    # sorted() returns a new list; ids.sort() would sort the caller's array.
    return sorted(ids)


def _binary_search_recursive(s, q, lo, hi):
    """Return True if q occurs in the sorted slice s[lo:hi] (hi exclusive)."""
    if lo >= hi:
        return False
    mid = (lo + hi) // 2
    if s[mid] == q:
        return True
    if s[mid] < q:
        return _binary_search_recursive(s, q, mid + 1, hi)
    return _binary_search_recursive(s, q, lo, mid)


def binary_query(sorted_ids, queries):
    return [_binary_search_recursive(sorted_ids, q, 0, len(sorted_ids)) for q in queries]


# --- Hash-set membership -----------------------------------------------------

def hash_prepare(ids):
    return set(ids)


def hash_query(id_set, queries):
    return [q in id_set for q in queries]


METHODS = {
    "linear": Method("linear", linear_prepare, linear_query),
    "binary": Method("binary", binary_prepare, binary_query),
    "hash": Method("hash", hash_prepare, hash_query),
}
