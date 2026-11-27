"""Shared test suite for every membership method and version (LAB_SPEC.md F1-F6, T1-T4).

Every test runs once per entry in ``membership.METHODS`` (3 methods x 2 versions),
so all methods are held to the same specification (F5). Expected answers are
written by hand or come from an independent oracle (``x in set(ids)``).

Passing tests are evidence, not proof of correctness (R7).
"""

from __future__ import annotations

import ast
import copy
import itertools
import random
from collections.abc import Sequence
from pathlib import Path

import pytest

from datagen.generator import make_case
from membership import BINARY_V2_CANDIDATES, METHODS, MethodSpec

MEMBERSHIP_DIR = Path(__file__).resolve().parent.parent / "membership"

# All registered methods/versions plus both v2 binary-search candidates (Step 6).
ALL_SPECS: list[MethodSpec] = list(METHODS.values()) + list(BINARY_V2_CANDIDATES.values())


@pytest.fixture(params=ALL_SPECS, ids=lambda spec: spec.label)
def spec(request: pytest.FixtureRequest) -> MethodSpec:
    return request.param


def check(
    spec: MethodSpec,
    ids: Sequence[int],
    queries: Sequence[int],
    expected: list[bool],
) -> None:
    """Run ``spec`` once and check result, types, length and unchanged inputs (F3, F4, T3)."""
    ids_before = copy.deepcopy(ids)
    queries_before = copy.deepcopy(queries)

    result = spec.run(ids, queries)

    assert result == expected
    assert isinstance(result, list)
    assert len(result) == len(queries)
    assert all(type(r) is bool for r in result), "every answer must be a real bool"
    assert result is not queries
    assert ids == ids_before, "the ID array must stay unchanged (F4)"
    assert queries == queries_before, "the queries must stay unchanged"


# --- Hand-written cases (T2, T4) -----------------------------------------------

CASES: list[tuple[str, list[int], list[int], list[bool]]] = [
    ("lab_example", [7, 11, 7], [11, 9, 7], [True, False, True]),
    ("empty_array", [], [1, 2, 3], [False, False, False]),
    ("empty_queries", [1, 2, 3], [], []),
    ("both_empty", [], [], []),
    ("one_entry_present", [5], [5], [True]),
    ("one_entry_absent", [5], [4, 6], [False, False]),
    ("duplicates_in_array", [3, 3, 3, 1, 1], [3, 1, 2], [True, True, False]),
    ("all_equal_array", [9, 9, 9, 9], [9, 8, 10], [True, False, False]),
    ("duplicate_queries", [1, 2, 3], [2, 2, 4, 2, 4], [True, True, False, True, False]),
    ("unsorted_input", [50, 10, 40, 20, 30], [30, 10, 50, 35], [True, True, True, False]),
    ("descending_input", [9, 7, 5, 3, 1], [1, 9, 4], [True, True, False]),
    ("negative_ids", [-5, 0, -1, 7], [-5, -1, 0, 7, -2, 1], [True, True, True, True, False, False]),
    ("first_and_last_in_input_order", [4, 8, 1, 6], [4, 6], [True, True]),
    ("min_and_max", [4, 8, 1, 6], [1, 8], [True, True]),
    ("absent_below_min", [10, 20, 30], [9, -100], [False, False]),
    ("absent_above_max", [10, 20, 30], [31, 1000], [False, False]),
    ("absent_in_gaps", [10, 20, 30], [15, 25], [False, False]),
    ("two_entries", [2, 1], [1, 2, 0, 3], [True, True, False, False]),
    ("zero_id", [0], [0, 1, -1], [True, False, False]),
    ("large_magnitude", [10**18, -(10**18)], [10**18, -(10**18), 10**18 + 1], [True, True, False]),
]


@pytest.mark.parametrize(
    ("ids", "queries", "expected"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_hand_written_cases(
    spec: MethodSpec, ids: list[int], queries: list[int], expected: list[bool]
) -> None:
    check(spec, ids, queries, expected)


def test_output_order_follows_query_order(spec: MethodSpec) -> None:
    ids = [1, 2, 3, 4, 5]
    queries = [5, 0, 1, 6, 3]
    check(spec, ids, queries, [True, False, True, False, True])
    check(spec, ids, list(reversed(queries)), [True, False, True, False, True][::-1])


def test_input_not_sorted_in_place(spec: MethodSpec) -> None:
    """Binary search must sort a copy, never the caller's list (F4)."""
    ids = [3, 1, 2]
    spec.run(ids, [1, 2, 3])
    assert ids == [3, 1, 2]


def test_tuple_input_is_accepted(spec: MethodSpec) -> None:
    """Any sequence of ints is accepted for reading (decision Q5)."""
    check(spec, (7, 11, 7), (11, 9, 7), [True, False, True])


# --- Repeated calls on one prepared state -------------------------------------


def test_repeated_queries_on_same_state(spec: MethodSpec) -> None:
    ids = [8, 3, 5, 3, 1]
    ids_before = list(ids)
    state = spec.prepare(ids)

    first = spec.query(state, [3, 4, 8])
    second = spec.query(state, [1, 2])
    third = spec.query(state, [3, 4, 8])

    assert first == [True, False, True]
    assert second == [True, False]
    assert third == first, "querying must not change the prepared state"
    assert ids == ids_before


def test_two_independent_states(spec: MethodSpec) -> None:
    state_a = spec.prepare([1, 2, 3])
    state_b = spec.prepare([4, 5, 6])
    assert spec.query(state_a, [1, 4]) == [True, False]
    assert spec.query(state_b, [1, 4]) == [False, True]


# --- Randomized cross-check against a set oracle ------------------------------


@pytest.mark.parametrize("seed", range(25))
def test_random_cross_check_against_set_oracle(spec: MethodSpec, seed: int) -> None:
    """Small random arrays with many duplicates and negatives, fixed seeds."""
    rng = random.Random(seed)
    n = rng.randint(0, 60)
    q = rng.randint(0, 40)
    ids = [rng.randint(-20, 20) for _ in range(n)]
    queries = [rng.randint(-25, 25) for _ in range(q)]
    oracle = set(ids)
    check(spec, ids, queries, [x in oracle for x in queries])


@pytest.mark.parametrize("hit_rate", [1.0, 0.0, 0.5])
@pytest.mark.parametrize("duplicate_policy", ["allow", "unique"])
def test_generated_case_against_set_oracle(
    spec: MethodSpec, hit_rate: float, duplicate_policy: str
) -> None:
    """Benchmark-sized data from the generator (n = 10,000, q = 100)."""
    ids, queries, _ = make_case(
        n=10_000, q=100, hit_rate=hit_rate, seed=7, duplicate_policy=duplicate_policy
    )
    oracle = set(ids)
    check(spec, ids, queries, [x in oracle for x in queries])


def test_large_sorted_array_edges(spec: MethodSpec) -> None:
    """n = 100,000 already sorted: first, last, middle and absent values in every region."""
    ids = list(range(0, 200_000, 2))  # even numbers 0 .. 199,998
    queries = [0, 199_998, 100_000, 2, 199_996, -1, 1, 99_999, 199_999, 200_000]
    expected = [True, True, True, True, True, False, False, False, False, False]
    check(spec, ids, queries, expected)


# --- Added in Step 6 (R4): cases found while writing the v2 candidates ----------
# The lower-bound search ends with ``lo == n`` when x is larger than every element and
# then must not read ``state[n]``. It also lands on the *first* copy of a duplicate run.
# The classic search moves ``hi`` to -1 for x below the minimum.

STEP6_CASES: list[tuple[str, list[int], list[int], list[bool]]] = [
    ("above_max_with_duplicate_max", [5, 9, 9, 9], [9, 10, 100], [True, False, False]),
    ("below_min_with_duplicate_min", [1, 1, 1, 4], [1, 0, -7], [True, False, False]),
    ("query_inside_duplicate_run", [1, 2, 2, 2, 2, 3], [2, 1, 3], [True, True, True]),
    ("absent_next_to_duplicate_run", [1, 2, 2, 2, 2, 5], [3, 4, 0, 6], [False] * 4),
    ("single_element_above_and_below", [3], [2, 3, 4], [False, True, False]),
    ("power_of_two_length", list(range(16)), [0, 15, 7, 8, 16, -1], [True] * 4 + [False] * 2),
    ("power_of_two_minus_one", list(range(15)), [0, 14, 7, 15], [True, True, True, False]),
]


@pytest.mark.parametrize(
    ("ids", "queries", "expected"),
    [case[1:] for case in STEP6_CASES],
    ids=[case[0] for case in STEP6_CASES],
)
def test_step6_boundary_cases(
    spec: MethodSpec, ids: list[int], queries: list[int], expected: list[bool]
) -> None:
    check(spec, ids, queries, expected)


def test_exhaustive_small_arrays(spec: MethodSpec) -> None:
    """Every array of length 0..5 over the values {0, 1, 2} (364 arrays, in every order),
    each queried for -1..3. Covers all patterns of duplicates and boundaries on small n."""
    queries = [-1, 0, 1, 2, 3]
    for length in range(6):
        for ids_tuple in itertools.product(range(3), repeat=length):
            ids = list(ids_tuple)
            oracle = set(ids)
            check(spec, ids, queries, [x in oracle for x in queries])


# --- Registry and hand-written-search rules (F1, F5, F6) ----------------------


def test_registry_has_all_methods_and_versions() -> None:
    assert set(METHODS) == {
        (method, version)
        for method in ("linear", "binary", "hash")
        for version in ("original", "revised")
    }
    for (method, version), spec in METHODS.items():
        assert (spec.method, spec.version) == (method, version)


FORBIDDEN_CALLS = {"index", "count", "__contains__", "bisect", "bisect_left", "bisect_right"}


@pytest.mark.parametrize("module_file", ["original.py", "revised.py"])
def test_searches_are_hand_written(module_file: str) -> None:
    """Static check of F6: no ``bisect``, and inside the linear/binary search functions no
    ``in`` comparison and no ``.index``/``.count`` shortcut. (``for x in ...`` loops are allowed;
    the hash method may use ``in`` on its set.)"""
    tree = ast.parse((MEMBERSHIP_DIR / module_file).read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "bisect" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "bisect"

    search_functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith(("linear_", "binary_"))
    ]
    for func in search_functions:
        for node in ast.walk(func):
            if isinstance(node, ast.Compare):
                assert not any(
                    isinstance(op, (ast.In, ast.NotIn)) for op in node.ops
                ), f"{func.name} uses an 'in' comparison"
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", None))
                assert name not in FORBIDDEN_CALLS, f"{func.name} calls {name}()"
