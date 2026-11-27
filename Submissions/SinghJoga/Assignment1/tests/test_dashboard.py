from pathlib import Path

from streamlit.testing.v1 import AppTest

from dashboard.app import compatible_pair, median_seconds
from dashboard.data import ROOT, load_saved_rows


def test_median_requires_five_completed_raw_repeats():
    five = [
        {"record_status": "completed", "repeat": index, "elapsed_seconds": value}
        for index, value in enumerate((1.0, 2.0, 3.0, 4.0, 5.0), 1)
    ]
    assert median_seconds(five) == 3.0
    assert median_seconds(five[:4]) is None
    assert median_seconds(five[:4] + [dict(five[3])]) is None


def test_dashboard_renders_and_filters_saved_rows():
    app = AppTest.from_file(str(ROOT / "dashboard" / "app.py")).run(timeout=30)
    assert not app.exception
    assert any("seconds per repeat" in item.value for item in app.caption)
    original_count = next(
        item.value for item in app.caption if item.value.startswith("Selected saved measurement rows:")
    )
    coverage_gaps = app.dataframe[0].value
    assert "never_attempted" in set(coverage_gaps["status"])

    selector = app.selectbox(key="version_filter")
    assert len(selector.options) > 1
    selector.select("revised").run(timeout=30)
    assert not app.exception
    filtered_count = next(
        item.value for item in app.caption if item.value.startswith("Selected saved measurement rows:")
    )
    assert filtered_count != original_count


def test_dashboard_medians_match_raw_records_and_missing_stays_missing():
    rows = load_saved_rows()
    group = [
        row for row in rows
        if row.get("phase") == "engine_replay"
        and row.get("record_status") == "completed"
        and row.get("repeat") is not None
        and row.get("elapsed_seconds") is not None
    ]
    assert group
    from collections import defaultdict
    grouped = defaultdict(list)
    for row in group:
        grouped[(row["run_id"], row["config_id"], row["policy"])].append(row)
    complete = next(values for values in grouped.values() if len(values) == 5)
    expected = sorted(row["elapsed_seconds"] for row in complete)[2]
    assert median_seconds(complete) == expected
    assert median_seconds([]) is None
    assert Path(ROOT / "results" / "coverage.csv").is_file()

    app = AppTest.from_file(str(ROOT / "dashboard" / "app.py")).run(timeout=30)
    displayed = app.dataframe[1].value
    assert "median_seconds" in displayed.columns
    shown = displayed.iloc[0]
    raw = [
        row for row in rows
        if row.get("run_id") == "full_20261125"
        and row.get("scenario") == shown["scenario"]
        and row.get("seed") == shown["seed"]
        and row.get("event_count") == shown["event_count"]
        and row.get("version") == shown["version"]
        and row.get("phase") == shown["phase"]
        and row.get("record_status") == "completed"
        and row.get("repeat") is not None
        and row.get("elapsed_seconds") is not None
    ]
    assert len(raw) == 5
    assert shown["median_seconds"] == sorted(row["elapsed_seconds"] for row in raw)[2]


def test_dashboard_speedups_use_compatible_complete_pairs():
    app = AppTest.from_file(str(ROOT / "dashboard" / "app.py")).run(timeout=45)
    paired = next(
        frame.value for frame in app.dataframe
        if "speedup (baseline/revised)" in frame.value.columns
    )
    assert not paired.empty
    shown = paired.iloc[0]
    rows = load_saved_rows()
    config = shown["config_id"]
    phase = shown["phase"]
    baseline = [
        row for row in rows
        if row.get("run_id") == "full_20261125"
        and row.get("config_id") == f"{config}__baseline"
        and row.get("phase") == phase
        and row.get("policy") == shown["policy"]
        and row.get("repeat") is not None
        and row.get("record_status") == "completed"
    ]
    revised = [
        row for row in rows
        if row.get("run_id") == "full_20261125"
        and row.get("config_id") == f"{config}__revised"
        and row.get("phase") == phase
        and row.get("policy") == shown["policy"]
        and row.get("repeat") is not None
        and row.get("record_status") == "completed"
    ]
    assert len(baseline) == len(revised) == 5
    expected = median_seconds(baseline) / median_seconds(revised)
    assert abs(shown["speedup (baseline/revised)"] - expected) < 1e-10
    bad_pair = {**baseline[0], "rows": baseline, "policy": "different-policy"}
    good_pair = {**revised[0], "rows": revised}
    assert not compatible_pair(bad_pair, good_pair)

    legacy_rows = [
        row for row in rows
        if row.get("run_id") == "full_20261125"
        and row.get("config_id").startswith("workload_buildup_M10000_seed42")
        and row.get("phase") == "engine_replay"
        and row.get("policy") == "aggregate-300s"
        and row.get("repeat") is not None
        and row.get("record_status") == "completed"
    ]
    legacy_baseline = [row for row in legacy_rows if row["version"] == "baseline"]
    legacy_revised = [row for row in legacy_rows if row["version"] == "revised"]
    assert compatible_pair(
        {**legacy_baseline[0], "rows": legacy_baseline},
        {**legacy_revised[0], "rows": legacy_revised},
    )
    assert not compatible_pair(
        {
            **legacy_baseline[0], "rows": legacy_baseline,
            "continuation_status": "incompatible",
        },
        {**legacy_revised[0], "rows": legacy_revised},
    )


def test_dashboard_shows_price_concentration_scenarios_without_zero_filling():
    app = AppTest.from_file(str(ROOT / "dashboard" / "app.py")).run(timeout=45)
    comparison = next(
        frame.value for frame in app.dataframe
        if {"scenario", "complete_five_repeat_median_seconds"}.issubset(frame.value.columns)
    )
    assert {"queue_4_prices", "queue_1000_prices"}.issubset(
        set(comparison["scenario"])
    )
    medians = comparison["complete_five_repeat_median_seconds"].dropna()
    assert all(value > 0 for value in medians)
    assert any(value is None or value != value for value in comparison[
        "complete_five_repeat_median_seconds"
    ])
