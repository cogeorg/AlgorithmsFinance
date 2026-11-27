"""Tests of the tests: deliberately broken methods that the suite must reject.

These mutants do not depend on search_v1 or search_v2. A reference method that
is correct must pass every check, and every mutant must fail at least one.
"""

import pytest
from contract import ALL_CHECKS
from interface import Method


def _binary_found(s, q):
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


def _linear_query(ids, queries):
    return [any(x == q for x in ids) for q in queries]


def _binary_misses_last(s, queries):
    out = []
    for q in queries:
        lo, hi = 0, len(s) - 1  # bug: upper bound should be len(s)
        found = False
        while lo < hi:
            mid = (lo + hi) // 2
            if s[mid] == q:
                found = True
                break
            if s[mid] < q:
                lo = mid + 1
            else:
                hi = mid
        out.append(found)
    return out


def _consuming_query(s, queries):
    out = []
    for q in queries:
        out.append(q in s)
        s.discard(q)  # bug: removes the hit from the prepared state
    return out


REFERENCE = Method("reference", set, lambda s, queries: [q in s for q in queries])

MUTANTS = [
    Method("sorts_input_in_place", lambda ids: (ids.sort(), ids)[1], _linear_query),
    Method("returns_ints", set, lambda s, queries: [int(q in s) for q in queries]),
    Method("binary_misses_last_element", sorted, _binary_misses_last),
    Method("ignores_query_order", set, lambda s, queries: [q in s for q in sorted(queries)]),
    Method("binary_without_sorting", list, lambda s, queries: [_binary_found(s, q) for q in queries]),
    Method("consumes_hits", set, _consuming_query),
    Method("crashes_on_empty_ids", lambda ids: (ids[0], set(ids))[1], REFERENCE.query),
    Method("state_aliases_input", lambda ids: ids, _linear_query),
    Method(
        "duplicates_count_as_absent",
        lambda ids: {x for x in ids if ids.count(x) == 1},
        REFERENCE.query,
    ),
]


def failing_checks(method):
    failed = []
    for check in ALL_CHECKS:
        try:
            check(method)
        except Exception:
            failed.append(check.__name__)
    return failed


def test_reference_passes_every_check():
    assert failing_checks(REFERENCE) == []


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda m: m.name)
def test_suite_detects_mutant(mutant):
    assert failing_checks(mutant), f"no check detected the bug in {mutant.name}"
