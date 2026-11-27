"""LinearSearch: scan the array for each query.

Preparation: O(n) copy in v1, O(1) in v2.
Query batch: O(n) per query, O(n * q) per batch in the worst case
(absent queries scan the whole array; present queries stop at the first match).

Both versions are kept for comparison; see 00_docs/REVISIONS.md.
"""


# --- v1 (original) --------------------------------------------------------------

def prepare_v1(ids):
    """Defensive copy so the caller's array cannot change.

    Unnecessary: the scan below only reads. Removed in v2.
    """
    return list(ids)


def query_v1(data, queries):
    """Index-based while-loop scan, one pass per query."""
    results = []
    n = len(data)
    for q in queries:
        found = False
        i = 0
        while i < n:
            if data[i] == q:
                found = True
                break
            i += 1
        results.append(found)
    return results


# --- v2 (revised) ---------------------------------------------------------------

def prepare_v2(ids):
    """No copy: the scan never mutates ``ids``, so the input is used as is."""
    return ids


def _contains(data, q):
    for value in data:  # direct iteration: no index arithmetic or data[i] lookup
        if value == q:
            return True
    return False


def query_v2(data, queries):
    return [_contains(data, q) for q in queries]
