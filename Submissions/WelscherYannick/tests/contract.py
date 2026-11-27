"""Contract checks that every search method must pass (specification, slide 57).

Each check takes a Method (see interface.py) and raises on a violation. The
same checks run against every version and every method, so a revision is held
to exactly the same expectations as the original.

Expected values are written by hand or computed with the built-in list
membership operator, never with code from the methods under test.
"""

from datagen import GenSettings, generate


def oracle(ids, queries):
    """Independent reference answer: built-in membership on the plain list."""
    return [q in ids for q in queries]


def check_spec_example(m):
    assert m.contains_all([7, 11, 7], [11, 9, 7]) == [True, False, True]


def check_empty_ids(m):
    assert m.contains_all([], [1, 2, 3]) == [False, False, False]


def check_empty_queries(m):
    assert m.contains_all([1, 2, 3], []) == []


def check_both_empty(m):
    assert m.contains_all([], []) == []


def check_single_entry(m):
    assert m.contains_all([5], [5]) == [True]
    assert m.contains_all([5], [4, 5, 6]) == [False, True, False]


def check_duplicates(m):
    assert m.contains_all([3, 3, 3, 3], [3, 2, 4]) == [True, False, False]
    ids = [1, 2, 2, 2, 9, 9]
    assert m.contains_all(ids, [2, 9, 1, 0, 5]) == [True, True, True, False, False]


def check_unsorted_input(m):
    for ids in (
        [9, 1, 8, 2, 7, 3, 6, 4, 5],  # shuffled
        list(range(20, 0, -1)),  # descending
        [1, 3, 5, 7, 6, 4, 2],  # rises, then falls
    ):
        queries = list(range(-1, 23))
        assert m.contains_all(ids, queries) == oracle(ids, queries)


def check_first_last_and_outside(m):
    ids = [10, 20, 30, 40, 50]
    queries = [10, 50, 5, 55, 25, 30]
    assert m.contains_all(ids, queries) == [True, True, False, False, False, True]
    # First and last entry of an unsorted array are not its min or max.
    ids = [30, 50, 10, 40, 20]
    assert m.contains_all(ids, [30, 20, 10, 50]) == [True, True, True, True]


def check_negative_and_zero(m):
    ids = [-5, 0, 5, -5]
    queries = [-5, 0, 5, -1, 1, -6]
    assert m.contains_all(ids, queries) == [True, True, True, False, False, False]


def check_output_order(m):
    ids = [2, 4, 6, 8]
    queries = [8, 3, 2, 8, 5, 6]  # unsorted, 8 repeated
    assert m.contains_all(ids, queries) == [True, False, True, True, False, True]


def check_return_type(m):
    result = m.contains_all([1, 2, 3], [3, 4, 1])
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(type(x) is bool for x in result)


def check_input_unchanged(m):
    ids = [5, 3, 5, 1, 4]
    queries = [3, 9, 5, 3]
    ids_before, queries_before = list(ids), list(queries)
    m.contains_all(ids, queries)
    assert ids == ids_before, "ids were modified (sorted or emptied in place?)"
    assert queries == queries_before, "queries were modified"

    ids, queries = generate(GenSettings(n=300, q=50, hit_rate=0.5, duplicate_rate=0.2, seed=1))
    ids_before, queries_before = list(ids), list(queries)
    m.contains_all(ids, queries)
    assert ids == ids_before and queries == queries_before


def check_repeated_calls(m):
    ids = [4, 8, 15, 16, 23, 42]
    queries = [15, 99, 4]
    state = m.prepare(ids)
    first = m.query(state, queries)
    assert first == [True, False, True]
    assert m.query(state, queries) == first, "second call on the same state differs"
    assert m.query(state, [42, 8]) == [True, True], "other batch on the same state"
    assert m.query(state, queries) == first, "state changed by an earlier batch"
    assert m.contains_all(ids, queries) == first, "fresh preparation differs"


def check_big_integers(m):
    big = 2 ** 70
    ids = [big, -big, 0, 2 ** 63, 2 ** 63 - 1]
    queries = [big, -big, 2 ** 63, 2 ** 63 + 1, 2 ** 64, -(2 ** 63), big + 1]
    assert m.contains_all(ids, queries) == [True, True, True, False, False, False, False]


def check_tuple_input(m):
    ids, queries = (5, 3, 5, 1), (3, 9, 5)
    result = m.contains_all(ids, queries)
    assert result == [True, False, True]
    assert isinstance(result, list)
    assert ids == (5, 3, 5, 1) and queries == (3, 9, 5)


def check_state_independent_of_later_changes(m):
    ids = [4, 8, 15, 16]
    state = m.prepare(ids)
    ids.append(99)  # changed after preparation
    ids[0] = -1
    assert m.query(state, [99, -1, 4, 8]) == [False, False, True, True], (
        "the prepared state follows later changes to ids"
    )


def check_binary_search_boundaries(m):
    # Sorted arrays of every length 0..8 (odd and even), queried at every
    # element and in every gap, including below the first and above the last.
    for length in range(9):
        ids = [10 * (i + 1) for i in range(length)]
        queries = ids + [10 * i + 5 for i in range(length + 1)]
        assert m.contains_all(ids, queries) == oracle(ids, queries), f"length {length}"


def check_matches_oracle_on_generated(m):
    for n in (0, 1, 2, 10, 200):
        for hit_rate in (0.0, 0.5, 1.0):
            if n == 0 and hit_rate > 0:
                continue
            for duplicate_rate in (0.0, 0.5):
                for seed in (0, 1, 2):
                    ids, queries = generate(GenSettings(n, 40, hit_rate, duplicate_rate, seed))
                    expected = oracle(ids, queries)
                    assert m.contains_all(ids, queries) == expected, (
                        f"n={n} hit_rate={hit_rate} dup={duplicate_rate} seed={seed}"
                    )


ALL_CHECKS = [
    check_spec_example,
    check_empty_ids,
    check_empty_queries,
    check_both_empty,
    check_single_entry,
    check_duplicates,
    check_unsorted_input,
    check_first_last_and_outside,
    check_negative_and_zero,
    check_output_order,
    check_return_type,
    check_input_unchanged,
    check_repeated_calls,
    check_big_integers,
    check_tuple_input,
    check_state_independent_of_later_changes,
    check_binary_search_boundaries,
    check_matches_oracle_on_generated,
]
