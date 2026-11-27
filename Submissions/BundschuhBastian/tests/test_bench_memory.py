"""Tests for the memory script: structure, fresh traces, and byte counts that scale as expected.

Exact byte counts depend on the Python version (tracemalloc and the interpreter add a small
constant overhead, e.g. about 400 bytes more on 3.10, and it can differ between phases).
So no test compares absolute bytes across n or phases. The tests check how the numbers GROW:
growth is compared with the growth of the sorted copy between SMALL and LARGE
(about 8 bytes x 99,000 = 792 kB); anything that should not grow with n must change by less
than 1 % of that. Differences between q values at the same n (the overhead cancels) are
compared with the expected 8 bytes per query.
"""
import sys
import tracemalloc
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bench_memory  # noqa: E402
from datagen import generate  # noqa: E402
from membership import METHODS  # noqa: E402

SMALL, LARGE = 1000, 100_000   # two sizes to measure growth
SHARE = 0.01                   # "does not grow": < 1 % of the sorted-copy growth


def cell(rows, method, phase, n, q, field="median_current_bytes"):
    (row,) = [r for r in rows if r["method"] == method and r["phase"] == phase
              and r["n"] == n and r["q"] == q]
    return row[field]


def sorted_growth(summary):
    """Growth of the sorted copy from SMALL to LARGE ids: the reference for 'tiny'."""
    return (cell(summary, "binary_v1", "prepare", LARGE, 1)
            - cell(summary, "binary_v1", "prepare", SMALL, 1))


@pytest.fixture(scope="module")
def summary():
    _, rows = bench_memory.run_benchmark([SMALL, LARGE], [1, 100], ["mixed"],
                                         repeats=2, seed=3)
    return rows


def test_rows_cover_all(summary):
    assert len(summary) == 2 * 2 * 1 * len(METHODS) * 3


def test_tracing_is_off_afterwards(summary):
    assert not tracemalloc.is_tracing()


def test_reference_growth_is_about_8_bytes_per_id(summary):
    assert 7.5 * (LARGE - SMALL) <= sorted_growth(summary) <= 8.5 * (LARGE - SMALL)


def test_linear_prepare_builds_no_structure(summary):
    small = cell(summary, "linear_v1", "prepare", SMALL, 1)
    large = cell(summary, "linear_v1", "prepare", LARGE, 1)
    assert abs(large - small) < SHARE * sorted_growth(summary)   # 100x more ids add ~nothing
    assert large < SHARE * sorted_growth(summary)                # and it is nowhere near n


@pytest.mark.parametrize("method", ["binary_v1", "binary_v2"])
def test_sorted_copy_grows_about_8_bytes_per_id(summary, method):
    small = cell(summary, method, "prepare", SMALL, 1)
    large = cell(summary, method, "prepare", LARGE, 1)
    per_id = (large - small) / (LARGE - SMALL)          # one pointer per id
    assert 7.5 <= per_id <= 8.5
    assert small >= 8 * SMALL                           # at least the pointer array


def test_both_binary_versions_prepare_the_same_amount(summary):
    for n in (SMALL, LARGE):
        v1 = cell(summary, "binary_v1", "prepare", n, 1)
        v2 = cell(summary, "binary_v2", "prepare", n, 1)
        assert abs(v1 - v2) < SHARE * sorted_growth(summary)


def test_set_grows_faster_than_sorted_copy(summary):
    set_growth = (cell(summary, "hash_v1", "prepare", LARGE, 1)
                  - cell(summary, "hash_v1", "prepare", SMALL, 1)) / (LARGE - SMALL)
    sorted_growth = (cell(summary, "binary_v1", "prepare", LARGE, 1)
                     - cell(summary, "binary_v1", "prepare", SMALL, 1)) / (LARGE - SMALL)
    assert set_growth > 2 * sorted_growth               # hash table is larger than n pointers
    assert cell(summary, "hash_v1", "prepare", LARGE, 1) > \
        cell(summary, "binary_v1", "prepare", LARGE, 1)


def test_total_peak_contains_structure_and_output(summary):
    tolerance = SHARE * sorted_growth(summary)          # covers per-phase overhead
    for method in METHODS:
        prepared = cell(summary, method, "prepare", LARGE, 100)
        output = cell(summary, method, "query", LARGE, 100)
        peak = cell(summary, method, "total", LARGE, 100, "median_peak_bytes")
        assert peak + tolerance >= prepared + output
        for n in (SMALL, LARGE):
            assert cell(summary, method, "total", n, 100, "median_peak_bytes") >= \
                cell(summary, method, "total", n, 100)               # peak >= current
            assert cell(summary, method, "query", n, 100, "median_peak_bytes") >= \
                cell(summary, method, "query", n, 100)


def test_output_grows_with_q(summary):
    for method in METHODS:
        small = cell(summary, method, "total", LARGE, 1)
        large = cell(summary, method, "total", LARGE, 100)
        assert large - small > 400                      # about 8 bytes x 99 more queries


def test_output_does_not_grow_with_n(summary):
    for method in METHODS:
        small = cell(summary, method, "total", SMALL, 100)
        large = cell(summary, method, "total", LARGE, 100)
        assert abs(large - small) < SHARE * sorted_growth(summary)   # 100x more ids: ~same


def test_input_is_not_traced():
    data = generate(20_000, 3, "mixed", "none", 1)
    ids_bytes = sys.getsizeof(data.ids)                 # about 160 kB
    rows = bench_memory.measure_method("linear_v1", data, repeats=1)
    total = [r for r in rows if r["phase"] == "total"][0]
    assert total["peak_bytes"] < ids_bytes / 10         # far below the size of the input
