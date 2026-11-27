"""Smoke test: the dashboard renders a tiny saved run without exceptions.

streamlit, pandas and altair are imported inside the tests, not at collection
time: a big interpreter heap makes every gc.collect() in the timing tests slow.
"""
import dataclasses
import json
import subprocess
import sys

import pytest

from benchmarks.config import PROJECT_DIR, Grid, write_run_config
from benchmarks.environment import collect_environment
from search_algos import METHODS, get_method

APP = PROJECT_DIR / "dashboard" / "app.py"
TINY = Grid(sizes=(10, 100), query_counts=(1, 4), scenarios=("all_absent", "mixed"),
            repeats=2, min_measure_seconds=0.0002)
RUN_ID = "20990101-000000_test"
PARTIAL_ID = "20980101-000000_partial_quick"
JUNIT = """<?xml version='1.0' encoding='utf-8'?>
<testsuites><testsuite name="pytest" tests="3" failures="1" skipped="1" errors="0">
<testcase classname="tests.test_search" name="test_expected_results[linear_v1-slide_example]"
  time="0.001" />
<testcase classname="tests.test_search" name="test_expected_results[hash_v1-slide_example]"
  time="0.002"><failure message="assert [1, 0, 1] == [True, False, True]">trace</failure></testcase>
<testcase classname="tests.test_other" name="test_skipped" time="0.000">
  <skipped message="not available" /></testcase>
</testsuite></testsuites>
"""


@pytest.fixture(scope="module")
def results_dir(tmp_path_factory):
    """results/ with one tiny complete run and one interrupted run (run.json only)."""
    pytest.importorskip("streamlit")
    root = tmp_path_factory.mktemp("results")
    run_dir = root / RUN_ID
    write_run_config(run_dir, TINY, run_id=RUN_ID, quick=False, status="complete",
                     source_unchanged=True, command="python -m benchmarks.run")
    # timing.run and memory.run in their own processes, as benchmarks.run does (keeps the
    # pytest heap out of their gc.collect() calls).
    for phase in ("timing", "memory"):
        subprocess.run([sys.executable, "-m", f"benchmarks.{phase}", str(run_dir)],
                       cwd=PROJECT_DIR, check=True, capture_output=True)
    (run_dir / "environment.json").write_text(json.dumps(collect_environment(PROJECT_DIR)))
    (run_dir / "tests.xml").write_text(JUNIT)
    write_run_config(root / PARTIAL_ID, TINY, run_id=PARTIAL_ID, quick=True, status="running")
    return root


def check(at):
    assert not at.exception, [e.message for e in at.exception]


def test_dashboard_renders_filters_and_spot_check(results_dir, monkeypatch):
    """One app session (each rerun renders every chart, so widget changes are batched)."""
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    check(at)
    assert at.selectbox(key="run").value.endswith(RUN_ID)  # newest non-quick run
    assert [t.label for t in at.tabs] == ["Overview", "Runtime", "Spot check",
                                          "Details for auditors"]
    assert any("1 failed" in e.value for e in at.error)    # parsed from tests.xml
    values = next(d.value for d in at.dataframe if "measure" in d.value.columns)  # Runtime table
    assert {"n = 10", "n = 100"} <= set(values.columns)
    assert "Per query (derived = batch / q)" in set(values["measure"])
    assert any(f"All {len(METHODS)} method/versions" in s.value for s in at.success)  # slide example

    # Every Details section renders, with the v1 vs v2 charts switched on.
    at.toggle(key="compare").set_value(True)
    for section in at.radio(key="details").options:
        at.radio(key="details").set_value(section).run()
        check(at)
    at.radio(key="details").set_value("Memory").run()
    at.toggle(key="memory_bytes").set_value(True)
    at.selectbox(key="q").set_value(1)
    at.selectbox(key="scenario").set_value("all_absent")
    at.text_area(key="spot_ids").set_value("1, 2.5, 3")
    at.button(key="spot_run").click()
    at.run()
    check(at)
    assert any("rejected it with TypeError" in s.value for s in at.success)
    assert at.selectbox(key="scenario").options == ["all_absent"]  # q=1 "mixed" is not measured

    at.text_area(key="spot_ids").set_value(" ".join(["1"] * 10_001))
    at.button(key="spot_run").click()
    at.run()
    assert any("limit is 10,000" in e.value for e in at.error)

    # Switching to an interrupted run (run.json only) must not break anything.
    at.selectbox(key="run").set_value(str(results_dir / PARTIAL_ID)).run()
    check(at)
    assert any("Missing from this run" in w.value for w in at.warning)
    assert any("Run status: running" in e.value for e in at.error)


def test_dashboard_helpers(results_dir):
    from dashboard import data
    assert data.parse_values("[7, 11,7]") == [7, 11, 7]
    assert data.parse_values("1 2.5 True x") == [1, 2.5, True, "x"]
    with pytest.raises(ValueError):
        data.parse_values(" ".join(["1"] * (data.MAX_SPOT_ELEMENTS + 1)))
    assert data.loglog_slope([10, 100, 1000], [1e-6, 1e-5, 1e-4]) == pytest.approx(1)
    assert data.expected_slope("binary", "v1", "prepare")[0] == "≈ 1.0–1.2"
    assert data.expected_slope("linear", "v2", "prepare")[0].startswith("≈ 0")
    assert data.format_seconds(2.5e-8) == "25 ns"
    assert data.default_run_index([{"quick": True}, {"quick": False}]) == 1
    assert data.parse_junit(results_dir / RUN_ID / "tests.xml")["counts"] == {
        "passed": 1, "failed": 1, "skipped": 1, "error": 0, "total": 3}

    # The spot check flags a method that answers 1/0 instead of True/False.
    buggy = dataclasses.replace(get_method("hash"), query=lambda s, qs: [int(q in s) for q in qs])
    result = data.run_spot_check([get_method("binary"), buggy], [7, 11, 7], [11, 9, 7])
    assert result["reference"] == [True, False, True]
    assert [row["ok"] for row in result["rows"]] == [True, False]

    # Overhead floor: partial wrapper for prepare/query, lambda for total.
    import pandas as pd
    cfg = {"noop_call_s": 1e-8, "noop_lambda_call_s": 2e-8}
    df = pd.DataFrame({"segment": ["prepare", "total", "total"], "median_s": [5e-8, 1.5e-7, 5e-7]})
    assert data.near_overhead(df, cfg).tolist() == [True, True, False]
