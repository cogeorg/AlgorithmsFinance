"""One specification, every method and version: all must pass the same tests.

The reference ``oracle`` uses Python's built-in list membership, which is
independent of all three implementations under test.
"""
import ast
import inspect
import math
import random

import pytest

from search_algos import CURRENT, METHODS, binary, get_method, linear

T, F = True, False

# (case id, ids, queries, expected)
CASES = [
    ("slide_example", [7, 11, 7], [11, 9, 7], [T, F, T]),
    ("empty_array_empty_queries", [], [], []),
    ("empty_array_with_queries", [], [0, 1, -1], [F, F, F]),
    ("empty_queries", [3, 1, 2], [], []),
    ("one_entry_present", [5], [5], [T]),
    ("one_entry_absent_below", [5], [4], [F]),
    ("one_entry_absent_above", [5], [6], [F]),
    ("one_entry_mixed", [5], [4, 5, 6], [F, T, F]),
    ("all_duplicates", [2, 2, 2, 2], [2, 3, 1], [T, F, F]),
    ("duplicates_mixed", [4, 1, 4, 9, 1, 4], [1, 4, 9, 5, 0], [T, T, T, F, F]),
    ("unsorted", [9, 1, 8, 2, 7, 3], [1, 7, 4, 9, 10, 0], [T, T, F, T, F, F]),
    ("descending", [5, 4, 3, 2, 1], [1, 5, 6, 0, 3], [T, T, F, F, T]),
    ("all_present", [10, 30, 20], [20, 10, 30], [T, T, T]),
    ("all_absent", [10, 30, 20], [15, 0, 40], [F, F, F]),
    ("repeated_queries", [4, 8], [8, 8, 4, 5, 8, 5], [T, T, T, F, T, F]),
    ("negative_and_zero", [-3, 0, 4, -10], [-10, -3, 0, 1, -4], [T, T, T, F, F]),
    ("large_ints", [2**63, -(2**63), 10**30], [10**30, 2**63 - 1, -(2**63)], [T, F, T]),
    ("boundaries", [10, 20, 30, 40], [5, 10, 25, 40, 45], [F, T, F, T, F]),
    ("odd_length", [1, 3, 5, 7, 9], [1, 5, 9, 2, 8, 10], [T, T, T, F, F, F]),
    ("two_entries", [7, 11], [7, 11, 9], [T, T, F]),
]


def oracle(ids, queries):
    reference = list(ids)
    return [q in reference for q in queries]


@pytest.fixture(params=METHODS, ids=[m.key for m in METHODS])
def method(request):
    return request.param


# --- Registry --------------------------------------------------------------

def test_registry_has_all_methods_and_versions():
    keys = {m.key for m in METHODS}
    assert {"linear_v1", "linear_v2", "binary_v1", "binary_v2", "hash_v1"} <= keys
    assert len(keys) == len(METHODS), "duplicate method keys"
    for name, version in CURRENT.items():
        assert get_method(name).version == version


def test_cases_match_oracle():
    # Guards the hand-written expectations themselves.
    for _, ids, queries, expected in CASES:
        assert oracle(ids, queries) == expected


# --- Specification ------------------------------------------------------------

@pytest.mark.parametrize("ids, queries, expected",
                         [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_expected_results(method, ids, queries, expected):
    assert method(ids, queries) == expected


@pytest.mark.parametrize("ids, queries, expected",
                         [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_output_is_list_of_bools_in_query_order(method, ids, queries, expected):
    result = method(ids, queries)
    assert type(result) is list
    assert len(result) == len(queries)
    assert all(type(r) is bool for r in result)
    assert result == expected  # same order as the queries


@pytest.mark.parametrize("ids, queries, expected",
                         [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_input_unchanged(method, ids, queries, expected):
    ids_before, queries_before = list(ids), list(queries)
    method(ids, queries)
    assert ids == ids_before
    assert queries == queries_before


def test_tuple_and_range_inputs(method):
    assert method((3, 1, 2), (2, 4)) == [T, F]
    assert method(range(0, 10, 2), [4, 5]) == [T, F]


def test_prepare_does_not_mutate_and_state_is_reusable(method):
    ids = [9, 1, 8, 2, 8]
    before = list(ids)
    state = method.prepare(ids)
    assert ids == before
    first = method.query(state, [8, 3, 1])
    second = method.query(state, [8, 3, 1])
    assert first == second == [T, F, T]
    assert ids == before


def test_split_api_matches_call(method):
    ids, queries = [5, 3, 5, 1], [1, 2, 5]
    assert method.query(method.prepare(ids), queries) == method(ids, queries)


def test_result_is_a_new_list(method):
    ids = [1, 2, 3]
    queries = [1, 2, 3]
    result = method(ids, queries)
    assert result is not ids and result is not queries
    result[0] = "changed"
    assert ids == [1, 2, 3] and queries == [1, 2, 3]


# --- Randomized and large inputs ------------------------------------------------

@pytest.mark.parametrize("seed", range(40))
def test_random_inputs_agree_with_oracle(method, seed):
    rng = random.Random(seed)
    n = rng.randrange(0, 60)
    ids = [rng.randint(-20, 20) for _ in range(n)]
    queries = [rng.randint(-25, 25) for _ in range(rng.randrange(0, 30))]
    before = list(ids)
    assert method(ids, queries) == oracle(ids, queries)
    assert ids == before


@pytest.mark.parametrize("order", ["ascending", "descending", "shuffled"])
def test_large_input(method, order):
    n = 100_000
    ids = list(range(0, 2 * n, 2))  # even numbers 0 .. 2n-2
    if order == "descending":
        ids.reverse()
    elif order == "shuffled":
        random.Random(7).shuffle(ids)
    before = list(ids)
    queries = [0, 2 * n - 2, n, n + 1, -2, 2 * n, 2 * n - 3]
    assert method(ids, queries) == [T, T, T, F, F, F, F]
    assert ids == before


def test_all_methods_agree_on_same_input():
    rng = random.Random(123)
    ids = [rng.randrange(500) for _ in range(1000)]
    queries = [rng.randrange(-50, 550) for _ in range(300)]
    results = {m.key: m(ids, queries) for m in METHODS}
    expected = oracle(ids, queries)
    for key, result in results.items():
        assert result == expected, key


# --- Invalid input: identical behaviour for every method -------------------------

@pytest.mark.parametrize("ids, queries", [
    ([1, None], [1]),
    ([1, "2"], [1]),
    ([1, 2.5], [1]),
    ([1, 2.0], [1]),
    ([True, 2], [1]),
    ([1, 2], [None]),
    ([1, 2], [1.0]),
    ([1, 2], [False]),
    ("123", [1]),
    ([1, 2], "1"),
    (None, [1]),
    ([1, 2], None),
    ({1, 2}, [1]),
    (iter([1, 2]), [1]),
    ([1, 2], (q for q in [1])),
], ids=["None_id", "str_id", "float_id", "integral_float_id", "bool_id",
        "None_query", "float_query", "bool_query", "str_ids", "str_queries",
        "ids_None", "queries_None", "set_ids", "iterator_ids", "generator_queries"])
def test_invalid_input_raises_type_error(method, ids, queries):
    with pytest.raises(TypeError):
        method(ids, queries)


def test_numpy_integers_rejected(method):
    # NumPy comparisons return numpy.bool_, which would leak into some outputs.
    np = pytest.importorskip("numpy")
    with pytest.raises(TypeError):
        method([np.int64(7)], [7])
    with pytest.raises(TypeError):
        method([7], [np.int64(7)])
    with pytest.raises(TypeError):
        method(np.array([7, 11]), [7])


# --- "Implemented by hand": structure and cost, not just answers -----------------

@pytest.mark.parametrize("module", [linear, binary], ids=["linear", "binary"])
def test_search_procedures_do_not_use_library_search(module):
    """No `in`/`not in` tests, bisect, .index() or .count() in the hand-written searches."""
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            assert not any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops), \
                f"membership test at line {node.lineno}"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            assert not any("bisect" in name for name in names), f"bisect at line {node.lineno}"
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"index", "count", "__contains__"}, \
                f".{node.attr} at line {node.lineno}"


class CountingInt(int):
    """int that counts every comparison made on it (class-wide counter)."""
    comparisons = 0
    __hash__ = int.__hash__

    def _count(op):
        def compare(self, other):
            CountingInt.comparisons += 1
            return op(self, other)
        return compare

    __eq__, __ne__ = _count(int.__eq__), _count(int.__ne__)
    __lt__, __le__ = _count(int.__lt__), _count(int.__le__)
    __gt__, __ge__ = _count(int.__gt__), _count(int.__ge__)


def count_query_comparisons(method, ids, queries):
    state = method.prepare([CountingInt(x) for x in ids])
    counted = [CountingInt(x) for x in queries]
    CountingInt.comparisons = 0
    result = method.query(state, counted)
    return CountingInt.comparisons, result


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_binary_search_uses_logarithmic_comparisons(version):
    n = 4096
    ids = list(range(0, 2 * n, 2))
    queries = [0, 2 * n - 2, 2 * n, -1, 4097, 4096, 3001, 3000]
    comparisons, result = count_query_comparisons(get_method("binary", version), ids, queries)
    assert result == oracle(ids, queries)
    bound = 2 * math.ceil(math.log2(n + 1)) + 2  # 2 comparisons per level + final check
    assert comparisons <= bound * len(queries), f"{comparisons} comparisons for {len(queries)} queries"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_linear_search_scans_until_first_match(version):
    n = 500
    ids = list(range(n))
    m = get_method("linear", version)
    assert count_query_comparisons(m, ids, [-1, n])[0] == 2 * n  # a miss scans everything
    assert count_query_comparisons(m, ids, [0])[0] == 1          # a hit at index 0 stops
    assert count_query_comparisons(m, ids, [249])[0] == 250      # ... at index 249


def test_hash_lookup_does_not_scan():
    ids = list(range(2000))
    comparisons, result = count_query_comparisons(get_method("hash"), ids, [5, 1999, -3, 4000])
    assert result == [True, True, False, False]
    assert comparisons <= 2 * 4  # a scan would need thousands


def test_prepared_states():
    ids = [3, 1, 2, 3]
    for version in ("v1", "v2"):
        state = get_method("binary", version).prepare(ids)
        assert state == [1, 2, 3, 3] and state is not ids  # a sorted copy
    assert type(get_method("hash").prepare(ids)) in (set, frozenset)
    assert get_method("linear", "v1").prepare(ids) is not ids  # v1: defensive copy
    assert get_method("linear", "v2").prepare(ids) is ids      # v2: no copy (revision)
    assert ids == [3, 1, 2, 3]
