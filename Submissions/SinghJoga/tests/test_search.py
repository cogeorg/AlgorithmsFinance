import pytest

from algorithms.search import binary_search, hash_membership, linear_search


SEARCH_FUNCTIONS = [
    pytest.param(linear_search, id="linear_search"),
    pytest.param(binary_search, id="binary_search"),
    pytest.param(hash_membership, id="hash_membership"),
]


@pytest.mark.parametrize("search", SEARCH_FUNCTIONS)
@pytest.mark.parametrize(
    "ids, queries, expected",
    [
        pytest.param([], [], [], id="both-empty"),
        pytest.param([], [1, 0, -1], [False, False, False], id="empty-ids"),
        pytest.param([3, 1], [], [], id="empty-queries"),
        pytest.param([8], [8, 7, 9], [True, False, False], id="one-entry"),
        pytest.param(
            [7, 11, 7],
            [11, 9, 7],
            [True, False, True],
            id="duplicates",
        ),
        pytest.param(
            [6, 2, 9, 4],
            [9, 2, 5, 6],
            [True, True, False, True],
            id="unsorted-ids",
        ),
        pytest.param(
            [2, 6, 9, 12],
            [2, 12],
            [True, True],
            id="first-and-last-positions",
        ),
        pytest.param(
            [10, 20, 30],
            [9, 15, 31],
            [False, False, False],
            id="absent-below-between-above",
        ),
        pytest.param(
            [0, -3, 8],
            [-3, 0, -1, 8],
            [True, True, False, True],
            id="negative-ids-and-zero",
        ),
        pytest.param(
            [4, 9, 2],
            [9, 2, 9, 1, 4, 9],
            [True, True, True, False, True, True],
            id="repeated-queries-in-order",
        ),
    ],
)
def test_explicit_search_cases(search, ids, queries, expected):
    assert search(ids.copy(), queries.copy()) == expected


@pytest.mark.parametrize("search", SEARCH_FUNCTIONS)
def test_repeated_calls_with_different_inputs(search):
    assert search([1, 4, 8], [8, 2, 1]) == [True, False, True]
    assert search([-2, 0], [0, -2, 3]) == [True, True, False]


@pytest.mark.parametrize("search", SEARCH_FUNCTIONS)
def test_original_inputs_remain_unchanged(search):
    ids = [9, 2, 9]
    queries = [2, -1, 9, 2]
    original_ids = ids.copy()
    original_queries = queries.copy()

    result = search(ids, queries)

    assert result == [True, False, True, True]
    assert ids == original_ids
    assert queries == original_queries


@pytest.mark.parametrize("search", SEARCH_FUNCTIONS)
def test_returns_one_actual_bool_per_query(search):
    queries = [8, 3, 5]
    result = search([5, 8], queries)

    assert isinstance(result, list)
    assert len(result) == len(queries)
    assert all(type(answer) is bool for answer in result)
    assert result == [True, False, True]
