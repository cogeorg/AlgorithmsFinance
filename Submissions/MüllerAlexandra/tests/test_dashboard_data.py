"""Tests for dashboard transformations that do not require Streamlit."""

import json

import pytest

from dashboard_data import (
    filter_records,
    load_results,
    memory_rows,
    raw_repeat_rows,
    timing_rows,
)


@pytest.fixture
def record() -> dict:
    return {
        "label": "binary_search (revised_iterative)",
        "n": 1_000,
        "q": 100,
        "scenario": "mixed",
        "duplicate_policy": "allow",
        "seed": 7,
        "median_seconds": {
            "preparation": 0.001,
            "query_batch": 0.002,
            "total": 0.003,
        },
        "raw_seconds": {
            "preparation": [0.001, 0.0011],
            "query_batch": [0.002, 0.0021],
            "total": [0.003, 0.0031],
        },
        "batching_loops": {"preparation": 2, "query_batch": 3, "total": 1},
        "tracemalloc": {"current_bytes": 1_024, "peak_bytes": 2_048},
    }


def test_load_results_validates_required_sections(tmp_path) -> None:
    path = tmp_path / "raw.json"
    payload = {
        "environment": {},
        "settings": {},
        "definitions": {},
        "records": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_results(path) == payload


def test_filter_records_keeps_requested_configuration(record) -> None:
    other = {**record, "q": 1}

    selected = filter_records(
        [record, other], q=100, scenario="mixed", duplicate_policy="allow"
    )

    assert selected == [record]


def test_dashboard_rows_have_explicit_units(record) -> None:
    assert timing_rows([record], "total")[0]["elapsed (ms)"] == pytest.approx(3.0)
    assert memory_rows([record])[0]["peak traced (KiB)"] == pytest.approx(2.0)

    repeats = raw_repeat_rows([record])
    assert len(repeats) == 2
    assert repeats[1]["query batch (ms)"] == pytest.approx(2.1)


def test_unknown_timing_metric_is_rejected(record) -> None:
    with pytest.raises(ValueError):
        timing_rows([record], "unknown")
