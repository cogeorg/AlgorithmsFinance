"""Tests for the dashboard: data loading (dashboard/data.py) and a headless app run.

The app test uses Streamlit's ``AppTest``: it executes ``dashboard/app.py`` without a
browser on the saved results in ``results/`` and fails on any exception.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.data import RunInfo, default_run, list_runs, load_run, speedup_table

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def make_run(stamp: str, dirty: bool | None) -> RunInfo:
    p = Path(stamp)
    return RunInfo("timing", stamp, p, p, p, "abc1234", dirty)


def test_default_run_prefers_newest_clean_run() -> None:
    runs = [make_run("3", True), make_run("2", False), make_run("1", False)]
    assert default_run(runs).stamp == "2"
    assert default_run([make_run("1", True)]).stamp == "1"
    assert default_run([]) is None


def test_list_runs_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        list_runs("profiling")


def test_saved_runs_are_found_and_complete() -> None:
    timing_runs = list_runs("timing")
    assert timing_runs, "no timing run in results/raw/"
    summary, raw, env_file = load_run(default_run(timing_runs))
    assert {"prep_s_median", "query_batch_s_median", "total_s_median"} <= set(summary.columns)
    assert len(raw) == len(summary) * env_file["settings"]["repeats"]
    assert "binary_variants" not in str(timing_runs[0].env_path)


def test_dashboard_medians_agree_with_raw_repeats() -> None:
    """The summary the dashboard plots must equal the median of the raw repeats (A3)."""
    summary, raw, _ = load_run(default_run(list_runs("timing")))
    keys = ["n", "q", "hit_rate", "method", "version"]
    recomputed = raw.groupby(keys)[["prep_s", "query_batch_s", "total_s"]].median()
    merged = summary.set_index(keys).join(recomputed)
    for metric in ("prep_s", "query_batch_s", "total_s"):
        assert (merged[f"{metric}_median"] - merged[metric]).abs().max() < 1e-15


def test_speedup_table_ratio() -> None:
    summary = pd.DataFrame(
        {
            "method": ["binary", "binary"],
            "version": ["original", "revised"],
            "n": [10, 10],
            "q": [1, 1],
            "hit_rate": [0.5, 0.5],
            "total_s_median": [4.0, 2.0],
        }
    )
    table = speedup_table(summary, "total_s")
    assert table["speedup_original_over_revised"].tolist() == [2.0]


def test_app_runs_without_errors() -> None:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value.startswith("Membership search")
    assert len(at.dataframe) >= 2  # time table(s), speed-up table, memory table


@pytest.mark.parametrize("q", [1, 100])
@pytest.mark.parametrize("hit_rate", [1.0, 0.0, 0.5])
def test_app_filters_do_not_crash(q: int, hit_rate: float) -> None:
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio(key="q").set_value(q)
    at.sidebar.radio(key="hit_rate").set_value(hit_rate)
    at.run()
    assert not at.exception
    assert at.metric[0].value == str(q)


def test_app_with_nothing_selected_does_not_crash() -> None:
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.multiselect(key="methods").set_value([])
    at.run()
    assert not at.exception
