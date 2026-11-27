"""Tests for all membership methods. Every test runs once per method.

The oracle for expected answers is written by hand or uses Python's `in` operator.
`in` is used ONLY inside the tests, never inside the methods under test.
"""
import copy
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from membership import METHODS  # noqa: E402


@pytest.fixture(params=sorted(METHODS), ids=sorted(METHODS))
def method(request):
    return METHODS[request.param]


def oracle(ids, queries):
    return [q in ids for q in queries]


# ---- slide example and tiny cases -------------------------------------------------

def test_slide_example(method):
    assert method([7, 11, 7], [11, 9, 7]) == [True, False, True]


def test_empty_array(method):
    assert method([], [1, 2, 3]) == [False, False, False]


def test_empty_queries(method):
    assert method([1, 2, 3], []) == []


def test_both_empty(method):
    assert method([], []) == []


def test_one_entry_present(method):
    assert method([4], [4]) == [True]


def test_one_entry_absent(method):
    assert method([4], [5, 3, 0, -4]) == [False, False, False, False]


# ---- duplicates, order of the array ------------------------------------------------

def test_duplicates(method):
    assert method([5, 5, 5, 5], [5, 6, 4]) == [True, False, False]


def test_duplicates_mixed(method):
    ids = [3, 1, 3, 2, 1, 3]
    assert method(ids, [1, 2, 3, 0, 4]) == [True, True, True, False, False]


def test_unsorted_input(method):
    ids = [90, -5, 42, 7, 1000, 0, 13]
    assert method(ids, [7, 90, 1000, -5, 8, 14]) == [True, True, True, True, False, False]


def test_descending_input(method):
    ids = [9, 7, 5, 3, 1]
    assert method(ids, [9, 1, 5, 2, 10, 0]) == [True, True, True, False, False, False]


# ---- positions: first, last, middle, just outside ----------------------------------

@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 9, 16, 17])
def test_every_position_and_every_gap(method, n):
    ids = [10 * i for i in range(n)]            # 0, 10, ..., 10(n-1)
    present = ids
    absent = [-1] + [10 * i + 5 for i in range(n)]   # below first, gaps, above last
    assert method(ids, present) == [True] * n
    assert method(ids, absent) == [False] * (n + 1)


def test_first_and_last_of_unsorted(method):
    ids = [50, 20, 80, 10, 70]       # first = 50, last = 70, min = 10, max = 80
    assert method(ids, [50, 70, 10, 80]) == [True, True, True, True]


def test_smaller_and_larger_than_all(method):
    ids = [10, 20, 30]
    assert method(ids, [9, 31, -10**9, 10**9]) == [False] * 4


def test_negative_and_large_values(method):
    ids = [-2**63, -1, 0, 2**63 - 1]
    assert method(ids, [-2**63, 2**63 - 1, -2, 1]) == [True, True, False, False]


# ---- output shape and order --------------------------------------------------------

def test_output_order_follows_queries(method):
    ids = [1, 2, 3]
    queries = [3, 9, 1, 8, 2, 7]
    assert method(ids, queries) == [True, False, True, False, True, False]


def test_repeated_queries_in_one_batch(method):
    assert method([1, 2], [2, 2, 3, 3, 2]) == [True, True, False, False, True]


def test_output_is_list_of_bool(method):
    out = method([1, 2, 3], [2, 5])
    assert isinstance(out, list)
    assert all(type(x) is bool for x in out)
    assert len(out) == 2


# ---- input unchanged ---------------------------------------------------------------

def test_input_unchanged(method):
    ids = [9, 3, 7, 3, 1]
    queries = [3, 4, 9]
    ids_before, queries_before = copy.deepcopy(ids), copy.deepcopy(queries)
    ids_object = ids
    method(ids, queries)
    assert ids == ids_before            # same values, same order (not sorted in place)
    assert queries == queries_before
    assert ids is ids_object


def test_input_unchanged_when_empty(method):
    ids, queries = [], []
    method(ids, queries)
    assert ids == [] and queries == []


def test_output_is_not_the_input(method):
    queries = [1]
    out = method([1], queries)
    assert out is not queries


# ---- repeated calls ----------------------------------------------------------------

def test_repeated_calls_same_result(method):
    ids = [8, 2, 6, 4]
    queries = [2, 3, 8, 9]
    first = method(ids, queries)
    second = method(ids, queries)
    third = method(ids, queries)
    assert first == second == third == [True, False, True, False]


def test_no_state_leaks_between_arrays(method):
    assert method([1, 2, 3], [3]) == [True]
    assert method([4, 5, 6], [3]) == [False]     # 3 was in the previous array only
    assert method([1, 2, 3], [3]) == [True]


def test_output_lists_are_independent(method):
    first = method([1], [1])
    first.append(False)
    assert method([1], [1]) == [True]


# ---- cases added in step 4 (v2) ----------------------------------------------------

@pytest.mark.parametrize("kind", [tuple, range])
def test_other_sequence_types(method, kind):
    ids = kind([5, 3, 9]) if kind is tuple else range(0, 20, 5)   # (5,3,9) / 0,5,10,15
    queries = [5, 4, 15, 16]
    assert method(ids, queries) == [q in ids for q in queries]


def test_many_equal_values(method):
    ids = [4] * 1000
    assert method(ids, [4, 3, 5]) == [True, False, False]


def test_queries_not_sorted_and_with_repeats(method):
    ids = [1, 3, 5, 7, 9, 11]
    queries = [11, 1, 11, 6, 6, 3, 0, 12]
    assert method(ids, queries) == [True, True, True, False, False, True, False, False]


class CountingList(list):
    """List that counts how often it is iterated (a sort or a scan iterates it)."""
    iterations = 0

    def __iter__(self):
        type(self).iterations += 1
        return super().__iter__()


def test_binary_v2_does_not_sort_without_queries():
    CountingList.iterations = 0
    ids = CountingList([3, 1, 2])
    assert METHODS["binary_v2"](ids, []) == []
    assert CountingList.iterations == 0       # no copy, no sort when nothing is asked


def max_python_call_depth(function, *args):
    """Run function(*args); return (result, deepest nesting of Python-level calls).

    sys.setprofile reports a 'call' event when a Python function starts and a 'return'
    event when it ends (also when it ends by an exception). Calls of C functions such as
    sorted() are other events ('c_call') and are not counted. Depth 1 = `function` itself.
    The result does not depend on the Python version's recursion limit.
    """
    depth = deepest = 0

    def profiler(frame, event, arg):
        nonlocal depth, deepest
        if event == "call":
            depth += 1
            deepest = max(deepest, depth)
        elif event == "return":
            depth -= 1

    previous = sys.getprofile()
    sys.setprofile(profiler)
    try:
        result = function(*args)
    finally:
        sys.setprofile(previous)
    return result, deepest


def test_binary_v2_call_depth_is_constant():
    ids = list(range(200_000))
    queries = [0, 199_999, 100_000, -1, 200_000]   # present at both ends/middle, absent outside
    result, depth = max_python_call_depth(METHODS["binary_v2"], ids, queries)
    assert result == [True, True, True, False, False]
    assert depth < 3        # method + its answer phase; no per-query helper, no recursion


def test_binary_v1_call_depth_grows_with_log_n():
    ids = list(range(200_000))                      # log2(200000) is about 17.6
    queries = [-1, 200_000]                         # absent: the search runs to an empty range
    result, depth = max_python_call_depth(METHODS["binary_v1"], ids, queries)
    assert result == [False, False]
    assert depth >= 15      # about log2(n) nested recursive calls
    # and the depth grows with n: a 1000 times smaller input is much shallower
    _, small_depth = max_python_call_depth(METHODS["binary_v1"], list(range(200)), queries)
    assert small_depth < depth - 5


# ---- prepare / answer phases (used by the timing script) ---------------------------

from membership import PHASES  # noqa: E402


@pytest.mark.parametrize("name", sorted(PHASES))
def test_phases_match_public_method(name):
    prepare, answer = PHASES[name]
    ids = [9, 3, 7, 3, 1]
    queries = [3, 4, 9, 0]
    assert answer(prepare(ids), queries) == METHODS[name](ids, queries)


@pytest.mark.parametrize("name", sorted(PHASES))
def test_one_state_serves_many_batches_and_inputs_stay_unchanged(name):
    prepare, answer = PHASES[name]
    ids = [9, 3, 7, 3, 1]
    ids_before = list(ids)
    state = prepare(ids)
    assert ids == ids_before
    first = answer(state, [3, 4, 9])
    state_snapshot = list(state) if not isinstance(state, set) else set(state)
    assert answer(state, [3, 4, 9]) == first == [True, False, True]
    assert answer(state, [0, 1]) == [False, True]
    assert (list(state) if not isinstance(state, set) else set(state)) == state_snapshot
    assert ids == ids_before


def test_every_method_has_phases():
    assert set(PHASES) == set(METHODS)


# ---- random tests against the oracle ----------------------------------------------

@pytest.mark.parametrize("seed", range(20))
def test_random_against_oracle(method, seed):
    rng = random.Random(seed)
    n = rng.randint(0, 60)
    q = rng.randint(0, 60)
    ids = [rng.randint(-30, 30) for _ in range(n)]       # small range -> many duplicates
    queries = [rng.randint(-35, 35) for _ in range(q)]   # some present, some absent
    snapshot = list(ids)
    assert method(ids, queries) == oracle(ids, queries)
    assert ids == snapshot


def test_all_methods_agree_on_larger_input():
    rng = random.Random(2024)
    ids = [rng.randrange(10_000) for _ in range(2_000)]
    queries = [rng.randrange(-100, 10_100) for _ in range(500)]
    expected = oracle(ids, queries)
    for name, fn in METHODS.items():
        assert fn(ids, queries) == expected, name
