"""Fast checks for the benchmark's method interfaces and case matrix."""

import pytest

from benchmark import METHODS, benchmark_cases, measure_timing, measure_traced_memory


@pytest.mark.parametrize("method", METHODS, ids=lambda method: method.label)
def test_preparation_and_query_interfaces(method) -> None:
    ids = [7, 11, 7]
    queries = [11, 9, 7]

    prepared = method.prepare(ids)
    result = method.query(prepared, queries)

    assert result == [True, False, True]
    assert ids == [7, 11, 7]


def test_case_matrix_omits_impossible_one_query_mixture() -> None:
    cases = benchmark_cases([1_000], [1, 100])

    assert (1_000, 1, "all_absent", 0.0) in cases
    assert (1_000, 1, "all_present", 1.0) in cases
    assert (1_000, 1, "mixed", 0.5) not in cases
    assert (1_000, 100, "mixed", 0.5) in cases


def test_small_timing_and_memory_smoke_run() -> None:
    method = METHODS[2]
    ids = [4, 1, 9, 2]
    queries = [2, 8]
    expected = [True, False]

    timing = measure_timing(method, ids, queries, expected, repeats=2, target_seconds=0)
    memory = measure_traced_memory(method, ids, queries, expected)

    assert len(timing["raw_seconds"]["total"]) == 2
    assert timing["median_seconds"]["total"] >= 0
    assert memory["peak_bytes"] >= memory["current_bytes"] >= 0
