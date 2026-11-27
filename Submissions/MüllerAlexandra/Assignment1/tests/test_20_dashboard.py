"""Dashboard views disclose missing runs and keep both versions visible."""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "dashboard" / "12_app.py"


def selectbox(app: AppTest, label: str):
    """Return the uniquely labelled select box from a rendered application."""
    matches = [box for box in app.selectbox if box.label == label]
    assert len(matches) == 1
    return matches[0]


def chart_specs(app: AppTest) -> list[dict[str, object]]:
    """Decode every emitted Vega-Lite specification."""
    return [json.loads(chart.proto.spec) for chart in app.get("vega_lite_chart")]


def test_default_dashboard_is_paired_status_aware_and_log_scaled() -> None:
    app = AppTest.from_file(str(DASHBOARD_PATH), default_timeout=30).run()

    assert not app.exception
    assert selectbox(app, "Experiment group").value == "formal"
    assert selectbox(app, "Configured price levels per side").value == 1_000
    assert selectbox(app, "Latency seed").value == 43
    assert selectbox(app, "Memory mode").value == "memory_state"
    assert selectbox(app, "Memory scenario").value == "cancel_churn"
    assert selectbox(app, "Memory event count").value == 100_000

    coverage = next(
        table.value
        for table in app.dataframe
        if list(table.value.columns)
        == [
            "version",
            "event_count",
            "seed",
            "outcome",
            "timeout_seconds",
            "median_throughput_events_per_second",
        ]
    )
    assert coverage[["event_count", "seed", "version"]].head(4).values.tolist() == [
        [1_000, 42, "baseline"],
        [1_000, 42, "revised"],
        [1_000, 43, "baseline"],
        [1_000, 43, "revised"],
    ]

    latency_table = next(
        table.value
        for table in app.dataframe
        if {"scope", "median_us", "p95_us", "p99_us"}.issubset(
            table.value.columns
        )
    )
    assert set(latency_table["version"]) == {"baseline", "revised"}

    specs = chart_specs(app)
    assert all("facet" not in spec for spec in specs)
    assert all(spec.get("padding", {}).get("left", 0) >= 55 for spec in specs)

    latency_specs = [
        spec
        for spec in specs
        if spec.get("encoding", {}).get("x", {}).get("field") == "scope_label"
    ]
    assert {spec["title"] for spec in latency_specs} == {"Median", "P95", "P99"}
    assert all(
        spec["encoding"]["y"]["scale"]["type"] == "log"
        and spec["encoding"]["xOffset"]["field"] == "version"
        and spec["encoding"]["x"]["axis"]["labelAngle"] == 0
        and spec["padding"]["left"] == 55
        for spec in latency_specs
    )
    assert len(
        {
            tuple(spec["encoding"]["y"]["scale"]["domain"])
            for spec in latency_specs
        }
    ) == 1

    throughput_spec = next(
        spec
        for spec in specs
        if spec.get("encoding", {}).get("y", {}).get("field")
        == "throughput_events_per_second"
    )
    assert throughput_spec["encoding"]["x"]["scale"]["type"] == "log"
    assert throughput_spec["encoding"]["y"]["scale"]["type"] == "log"
    assert throughput_spec["encoding"]["y"]["title"] == "Events/second (log)"
    assert throughput_spec["padding"]["left"] == 55

    repeat_distribution_specs = [
        spec
        for spec in specs
        if spec.get("mark", {}).get("type") == "boxplot"
        and spec.get("encoding", {}).get("x", {}).get("field") == "event_label"
    ]
    assert {spec["title"] for spec in repeat_distribution_specs} == {
        "Baseline raw repeats",
        "Revised raw repeats",
    }
    assert all(
        spec["encoding"]["y"]["scale"]["type"] == "log"
        and spec["encoding"]["x"]["axis"]["labelAngle"] == 0
        and spec["encoding"]["x"]["scale"]["domain"]
        == ["1,000", "10,000", "100,000"]
        for spec in repeat_distribution_specs
    )
    assert (
        repeat_distribution_specs[0]["encoding"]["y"]["scale"]["domain"]
        == repeat_distribution_specs[1]["encoding"]["y"]["scale"]["domain"]
    )

    phase_specs = [
        spec
        for spec in specs
        if spec.get("title") in {"Empty-book initialization", "Event replay"}
    ]
    assert {spec["title"] for spec in phase_specs} == {
        "Empty-book initialization",
        "Event replay",
    }
    assert all(
        spec["encoding"]["x"]["scale"]["type"] == "log"
        and spec["encoding"]["y"]["scale"]["type"] == "log"
        and spec["padding"]["left"] == 55
        for spec in phase_specs
    )
    assert (
        phase_specs[0]["encoding"]["y"]["scale"]["domain"]
        == phase_specs[1]["encoding"]["y"]["scale"]["domain"]
    )

    liquidation_specs = [
        spec
        for spec in specs
        if spec.get("encoding", {}).get("x", {}).get("field") == "sale_label"
    ]
    assert {spec["title"] for spec in liquidation_specs} == {
        "Fresh-book construction",
        "Market sell",
    }
    assert all(
        spec["encoding"]["y"]["scale"]["type"] == "log"
        and spec["padding"]["left"] == 55
        for spec in liquidation_specs
    )
    assert (
        liquidation_specs[0]["encoding"]["y"]["scale"]["domain"]
        == liquidation_specs[1]["encoding"]["y"]["scale"]["domain"]
    )

    pair_table = next(
        table.value
        for table in app.dataframe
        if "all_recorded_counts_and_final_invariants_equal" in table.value.columns
    )
    assert pair_table["both_versions_present"].all()
    assert pair_table[
        "all_recorded_counts_and_final_invariants_equal"
    ].all()


def test_stopped_extension_runs_remain_visible_without_fabricated_points() -> None:
    app = AppTest.from_file(str(DASHBOARD_PATH), default_timeout=30).run()

    selectbox(app, "Experiment group").select("extension_1m").run()
    selectbox(app, "Throughput scenario").select("buildup").run()

    assert not app.exception
    assert any(
        "No completed throughput measurement exists" in message.value
        for message in app.info
    )
    warning_text = " ".join(message.value for message in app.warning)
    assert "baseline" in warning_text
    assert "revised" in warning_text
    assert "stopped_timeout" in warning_text

    coverage = next(
        table.value
        for table in app.dataframe
        if list(table.value.columns)
        == [
            "version",
            "event_count",
            "seed",
            "outcome",
            "timeout_seconds",
            "median_throughput_events_per_second",
        ]
    )
    assert set(coverage["version"]) == {"baseline", "revised"}
    assert set(coverage["outcome"]) == {"stopped_timeout"}
    assert coverage["median_throughput_events_per_second"].isna().all()
