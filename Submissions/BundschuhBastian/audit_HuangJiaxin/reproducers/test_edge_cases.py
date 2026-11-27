"""Independent edge-case checks of all six methods (cases checked; these PASS).

Expected answers are computed independently with Python's `in` on a list.
Run from Submissions/BundschuhBastian/:
    .venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/test_edge_cases.py
"""
import random

import pytest

import _target  # noqa: F401  (puts the audited folder on sys.path)
from membership import METHODS, run

ALL = list(METHODS)


def ref(ids, queries):
    return [x in ids for x in queries]


CASES = {
    "empty ids": ([], [0, -1, 5]),
    "empty queries": ([3, 1], []),
    "both empty": ([], []),
    "single present": ([4], [4]),
    "single absent below/above": ([4], [3, 5]),
    "all equal": ([2] * 50, [2, 1, 3]),
    "duplicates at both ends": ([9, 1, 5, 1, 9], [9, 1, 5, 0, 10]),
    "descending input": (list(range(20, 0, -1)), [20, 1, 10, 0, 21]),
    "negative and zero": ([-5, 0, -1, 3], [-5, 0, -2, 3, 4]),
    "very large ints": ([10**18, -(10**18), 2**63], [2**63, 10**18 + 1, -(10**18)]),
    "repeated queries keep order": ([1, 2], [2, 2, 1, 3, 1, 3]),
}


@pytest.mark.parametrize("method", ALL)
@pytest.mark.parametrize("case", list(CASES))
def test_cases(method, case):
    ids, queries = CASES[case]
    ids_copy, queries_copy = list(ids), list(queries)
    assert run(method, ids, queries) == ref(ids_copy, queries_copy)
    assert ids == ids_copy and queries == queries_copy          # input not mutated


@pytest.mark.parametrize("method", ALL)
@pytest.mark.parametrize("n", range(1, 18))
def test_every_position_and_every_gap(method, n):
    ids = [2 * i for i in range(n)]
    random.Random(n).shuffle(ids)
    queries = list(range(-1, 2 * n + 1))                       # every entry and every gap
    assert run(method, ids, queries) == ref(ids, queries)


@pytest.mark.parametrize("method", ALL)
def test_repeated_calls_and_state(method):
    a, b = [5, 3, 8], [1, 2]
    first = run(method, a, [3, 2])
    run(method, b, [1, 5])                                     # another array in between
    assert run(method, a, [3, 2]) == first == [True, False]


@pytest.mark.parametrize("method", ALL)
def test_random_with_duplicates(method):
    rng = random.Random(47)
    for _ in range(500):
        ids = [rng.randint(-20, 20) for _ in range(rng.randint(0, 40))]
        queries = [rng.randint(-25, 25) for _ in range(rng.randint(0, 15))]
        assert run(method, ids, queries) == ref(ids, queries)
