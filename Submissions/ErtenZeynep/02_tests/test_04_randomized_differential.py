"""Reproducible randomized comparisons with a trusted membership oracle."""

from __future__ import annotations

import random

import pytest

from conftest import SearchFunction


RANDOM_CASE_SEEDS = tuple(314_159 + index for index in range(100))


@pytest.mark.parametrize("case_seed", RANDOM_CASE_SEEDS)
def test_seeded_random_cases_match_membership_oracle(
    algorithm: SearchFunction,
    case_seed: int,
) -> None:
    rng = random.Random(case_seed)
    array = [rng.randint(-20, 20) for _ in range(rng.randint(0, 25))]
    queries = [rng.randint(-25, 25) for _ in range(rng.randint(0, 20))]
    original_array = array.copy()
    original_queries = queries.copy()

    result = algorithm(array, queries)

    assert result == [query in array for query in queries]
    assert len(result) == len(queries)
    assert all(type(value) is bool for value in result)
    assert array == original_array
    assert queries == original_queries
