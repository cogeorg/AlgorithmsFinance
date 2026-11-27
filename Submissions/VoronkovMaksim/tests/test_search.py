"""The same contract tests for all four search implementations."""

import pytest


from Submissions.VoronkovMaksim import search


@pytest.fixture(params=["linear_search_v1", "binary_search_v1",
                        "binary_search_v2", "hash_search_v1"])
def search_function(request):
    return getattr(search, request.param)


@pytest.mark.parametrize("ids,queries,expected", [
    ([], [3, 5], [False, False]),
    ([1, 2, 3], [], []),
    ([], [], []),
    ([7], [7], [True]),
    ([7], [9], [False]),
    ([8, 2, 5, 1], [2, 8], [True, True]),
    ([7, 11, 7], [11, 9, 7], [True, False, True]),
    ([4, 4, 4], [4, 5], [True, False]),
    ([-8, -2, 0, 5], [-2, -1, 0], [True, False, True]),
    ([10, 20, 30], [5, 35], [False, False]),
    ([3, 6, 9], [6, 6, 4, 6], [True, True, False, True]),
    ([2, 5, 8, 11, 14], [2, 14], [True, True]),
    ([2, 5, 8, 11], [6], [False]),
    ([10**100, -(10**100), 0], [10**100, 1], [True, False]),
])
def test_membership_contract(search_function, ids, queries, expected):
    original_ids = ids.copy()
    original_queries = queries.copy()
    result = search_function(ids, queries)
    assert result == expected
    assert len(result) == len(queries)
    assert all(type(value) is bool for value in result)
    assert ids == original_ids
    assert queries == original_queries


@pytest.mark.parametrize("ids,queries", [
    ([1, [2, 3], 4], [2]),
    ([1, "2", 3], [2]),
    ([1, 2, 3], ["2"]),
    ([1, 2.5, 3], [2]),
    ([1, 2, 3], [2.0]),
    ([1, True, 3], [2]),
    ([1, 2, 3], [True]),
    ([1, None, 3], [2]),
    ([1, 2, 3], [[2]]),
    ([1, {"id": 2}, 3], [2]),
    ([[], 1, 2], [2]),
    (None, [2]),
    ([1, 2, 3], "123"),
])
def test_invalid_inputs_raise_type_error(search_function, ids, queries):
    with pytest.raises(TypeError):
        search_function(ids, queries)
