"""Tests for the memory measurement: does it count what it claims to count?"""

import csv
import json
import tracemalloc

import pytest
from benchmark import BenchConfig
from interface import Method
from memory import COLUMNS, measure_method, run_memory
from registry import VERSIONS
from search_v1 import METHODS as V1

TINY = BenchConfig(sizes=(10, 50), query_counts=(1, 5), hit_rates=(1.0, 0.0, 0.6))
POINTER = 8  # bytes per list slot on a 64-bit build


def _silent(*args, **kwargs):
    pass


def test_input_is_not_counted():
    ids = list(range(100_000))
    keeps_input = Method("keeps_input", lambda ids: ids, lambda state, queries: [q in state for q in queries])
    res = measure_method(keeps_input, ids, [5])
    assert res["prepare_current_B"] < 1_000  # the state is the input itself: nothing new


def test_linear_tuple_copy_is_counted():
    n = 100_000
    res = measure_method(V1["linear"], list(range(n)), [5])
    assert n * POINTER <= res["prepare_current_B"] <= n * POINTER + 1_024


def test_sorted_copy_is_counted_once():
    n = 10_000
    ids = list(range(n, 0, -1))
    res = measure_method(V1["binary"], ids, [5])
    assert n * POINTER <= res["prepare_current_B"] <= n * POINTER + 1_024
    assert res["prepare_peak_B"] >= res["prepare_current_B"]


def test_known_allocation_is_measured():
    size = 200_000
    method = Method("bytes", lambda ids: bytearray(size), lambda state, queries: [False] * len(queries))
    res = measure_method(method, [1], [1, 2, 3])
    assert size <= res["prepare_current_B"] <= size + 1_024


def test_output_is_counted_in_query_and_total():
    q = 1_000
    res = measure_method(V1["hash"], [1, 2, 3], list(range(q)))
    assert res["query_current_B"] >= q * POINTER
    assert res["query_current_B"] == pytest.approx(res["output_getsizeof_B"], abs=1_024)
    assert res["total_current_B"] >= res["prepare_current_B"] + q * POINTER - 1_024


def test_tracing_is_stopped_afterwards():
    measure_method(V1["hash"], [1, 2, 3], [1])
    assert not tracemalloc.is_tracing()


def test_run_writes_rows_and_metadata(tmp_path):
    rows, _ = run_memory(TINY, tmp_path, repeats=2, log=_silent)
    with open(tmp_path / "memory_raw.csv", newline="") as f:
        saved = list(csv.DictReader(f))
    n_pairs = sum(len(methods) for methods in VERSIONS.values())
    assert len(saved) == len(rows) == 10 * n_pairs * 2  # scenarios x pairs x repeats
    assert list(saved[0]) == COLUMNS
    assert all(int(r["prepare_peak_B"]) >= int(r["prepare_current_B"]) for r in saved)
    with open(tmp_path / "memory_metadata.json") as f:
        meta = json.load(f)
    assert meta["measurement"]["input_included"] is False
    assert meta["units"]["total_peak_B"] == "bytes"


def test_wrong_result_stops_the_run(tmp_path):
    wrong = Method("always_true", set, lambda s, queries: [True] * len(queries))
    with pytest.raises(RuntimeError, match="wrong result"):
        run_memory(TINY, tmp_path, versions={"bad": {"always_true": wrong}}, log=_silent)
