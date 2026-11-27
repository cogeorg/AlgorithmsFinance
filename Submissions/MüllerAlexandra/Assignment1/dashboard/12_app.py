"""Interactive dashboard over saved Assignment 1 measurements."""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = Path(
    os.environ.get(
        "ASSIGNMENT1_DASHBOARD_DATA",
        PROJECT_ROOT / "results" / "summary" / "13_dashboard_data.json.gz",
    )
)


@st.cache_data
def load_data(path: Path) -> dict[str, object]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def frame(data: dict[str, object], key: str) -> pd.DataFrame:
    return pd.DataFrame(data[key])


def mib(series: pd.Series) -> pd.Series:
    return series / (1024 * 1024)


def timeout_suffix(timeout_seconds: object) -> str:
    """Format a configured limit when the status record supplies one."""
    if pd.isna(timeout_seconds):
        return ""
    return f" ({int(timeout_seconds)} s limit)"


st.set_page_config(page_title="Limit order book measurements", layout="wide")
st.title("Limit order book: baseline versus indexed revision")
st.caption(
    "Saved synthetic measurements only. Timings exclude network and queuing delay; "
    "tracemalloc is Python allocation, not total process memory."
)

if not DATA_PATH.is_file():
    st.error(
        "Dashboard data is missing. Run: python scripts/11_build_dashboard_data.py"
    )
    st.stop()

data = load_data(DATA_PATH)
statuses = frame(data, "statuses")
throughput = frame(data, "throughput_summaries")
comparisons = frame(data, "throughput_comparisons")

completed = int((statuses["outcome"] == "completed").sum())
timeouts = int((statuses["outcome"] == "stopped_timeout").sum())
failures = int((statuses["outcome"] == "failed").sum())
metric_columns = st.columns(4)
metric_columns[0].metric("Recorded tasks", len(statuses))
metric_columns[1].metric("Completed", completed)
metric_columns[2].metric("Stopped at limit", timeouts)
metric_columns[3].metric("Failed", failures)
st.caption(
    "Task counts combine the preregistered formal matrix and the separately "
    "identified optional one-million-event extension."
)

tab_throughput, tab_latency, tab_memory, tab_liquidation, tab_correctness, tab_raw = st.tabs(
    ["Throughput", "Latency", "Memory", "Liquidation", "Correctness", "Raw records"]
)

with tab_throughput:
    st.subheader("Replay throughput and scaling")
    throughput_statuses = statuses[statuses["phase"] == "throughput"]
    groups = sorted(throughput_statuses["experiment_group"].unique())
    default_group_index = groups.index("formal") if "formal" in groups else 0
    selected_group = st.selectbox(
        "Experiment group", groups, index=default_group_index
    )
    grouped_status = throughput_statuses[
        throughput_statuses["experiment_group"] == selected_group
    ]
    selected_scenario = st.selectbox(
        "Throughput scenario", sorted(grouped_status["scenario"].unique())
    )
    scenario_status = grouped_status[
        grouped_status["scenario"] == selected_scenario
    ]
    level_options = sorted(scenario_status["levels"].unique())
    default_level_index = (
        level_options.index(1_000) if 1_000 in level_options else 0
    )
    selected_levels = st.selectbox(
        "Configured price levels per side",
        level_options,
        index=default_level_index,
        help=(
            "The generator's levels parameter per side. For formal buildup, the extra "
            "4-level input holds 10,000 events and seed 42 fixed against the "
            "main 1,000-level input to test queue concentration."
        ),
    )
    selected = throughput[
        (throughput["experiment_group"] == selected_group)
        & (throughput["scenario"] == selected_scenario)
        & (throughput["levels"] == selected_levels)
    ].copy()
    selected["throughput_events_per_second"] = selected[
        "median_throughput_events_per_second"
    ]
    status_view = statuses[
        (statuses["experiment_group"] == selected_group)
        & (statuses["phase"] == "throughput")
        & (statuses["scenario"] == selected_scenario)
        & (statuses["levels"] == selected_levels)
    ].copy()
    status_display = status_view[
        ["version", "event_count", "seed", "outcome", "timeout_seconds"]
    ].merge(
        selected[
            [
                "version",
                "event_count",
                "seed",
                "median_throughput_events_per_second",
            ]
        ],
        on=["version", "event_count", "seed"],
        how="left",
    ).sort_values(["event_count", "seed", "version"])
    stopped_versions = status_display[status_display["outcome"] != "completed"]
    if not stopped_versions.empty:
        stopped_groups = (
            stopped_versions.groupby(
                ["version", "event_count", "outcome", "timeout_seconds"],
                dropna=False,
            )["seed"]
            .apply(lambda seeds: "/".join(str(seed) for seed in sorted(seeds)))
            .reset_index(name="seeds")
        )
        stopped_labels = ", ".join(
            f"{row.version} ({int(row.event_count):,} events, seeds {row.seeds}: "
            f"{row.outcome}"
            + (
                f", {int(row.timeout_seconds)} s limit"
                if pd.notna(row.timeout_seconds)
                else ""
            )
            + ")"
            for row in stopped_groups.itertuples()
        )
        st.warning(
            "No throughput value is plotted for stopped runs: " + stopped_labels
        )
    st.markdown("#### Task coverage (including stopped runs)")
    st.caption(
        "This table establishes which requested tasks produced measurements. A "
        "stopped task remains visible even though it has no throughput value."
    )
    st.dataframe(status_display, width="stretch", hide_index=True)
    chart = (
        selected.groupby(["version", "event_count"], as_index=False)[
            "throughput_events_per_second"
        ]
        .median()
        .sort_values("event_count")
    )
    if chart.empty:
        st.info("No completed throughput measurement exists for this selection.")
    elif chart["event_count"].nunique() == 1:
        single_size_chart = (
            alt.Chart(chart)
            .mark_point(filled=True, size=180)
            .encode(
                x=alt.X(
                    "version:N",
                    title="Version",
                    sort=["baseline", "revised"],
                ),
                y=alt.Y(
                    "throughput_events_per_second:Q",
                    title="Events/second (log)",
                    scale=alt.Scale(type="log"),
                ),
                color=alt.Color(
                    "version:N",
                    title="Version",
                    sort=["baseline", "revised"],
                ),
                tooltip=[
                    alt.Tooltip("version:N", title="Version"),
                    alt.Tooltip(
                        "throughput_events_per_second:Q",
                        title="Events/second",
                        format=",.2f",
                    ),
                ],
            )
            .properties(padding={"left": 55, "right": 10, "top": 10, "bottom": 10})
        )
        st.altair_chart(single_size_chart, width="stretch")
        st.caption(
            f"Single measured size: {int(chart['event_count'].iloc[0]):,} events; "
            "the logarithmic axis keeps both completed versions visible."
        )
    else:
        scaling_chart = (
            alt.Chart(chart)
            .mark_line(point=alt.OverlayMarkDef(filled=True, size=90))
            .encode(
                x=alt.X(
                    "event_count:Q",
                    title="Event count (log scale)",
                    scale=alt.Scale(type="log"),
                ),
                y=alt.Y(
                    "throughput_events_per_second:Q",
                    title="Events/second (log)",
                    scale=alt.Scale(type="log"),
                ),
                color=alt.Color("version:N", title="Version"),
                tooltip=[
                    alt.Tooltip("version:N", title="Version"),
                    alt.Tooltip("event_count:Q", title="Events", format=","),
                    alt.Tooltip(
                        "throughput_events_per_second:Q",
                        title="Events/second",
                        format=",.2f",
                    ),
                ],
            )
            .properties(padding={"left": 55, "right": 10, "top": 10, "bottom": 10})
        )
        st.altair_chart(scaling_chart, width="stretch")
        st.caption(
            "Points are medians across completed seed-level task medians. Both "
            "axes are logarithmic; stopped runs have no plotted value."
        )

    phase_scaling = (
        selected.groupby(["version", "event_count"], as_index=False)[
            ["median_construction_seconds", "median_replay_seconds"]
        ]
        .median()
        .melt(
            id_vars=["version", "event_count"],
            value_vars=[
                "median_construction_seconds",
                "median_replay_seconds",
            ],
            var_name="phase",
            value_name="seconds",
        )
    )
    phase_scaling["phase"] = phase_scaling["phase"].map(
        {
            "median_construction_seconds": "Empty-book initialization",
            "median_replay_seconds": "Event replay",
        }
    )
    if not phase_scaling.empty:
        st.markdown("#### Empty-book initialization and event replay")
        shared_phase_domain = [
            float(phase_scaling["seconds"].min()) * 0.8,
            float(phase_scaling["seconds"].max()) * 1.25,
        ]
        for phase_name in ["Empty-book initialization", "Event replay"]:
            phase_view = phase_scaling[phase_scaling["phase"] == phase_name]
            phase_chart = (
                alt.Chart(phase_view)
                .mark_line(point=alt.OverlayMarkDef(filled=True, size=80))
                .encode(
                    x=alt.X(
                        "event_count:Q",
                        title="Event count (log scale)",
                        scale=alt.Scale(type="log"),
                    ),
                    y=alt.Y(
                        "seconds:Q",
                        title="Seconds (log)",
                        scale=alt.Scale(type="log", domain=shared_phase_domain),
                    ),
                    color=alt.Color(
                        "version:N",
                        title="Version",
                        sort=["baseline", "revised"],
                    ),
                    tooltip=[
                        alt.Tooltip("phase:N", title="Phase"),
                        alt.Tooltip("version:N", title="Version"),
                        alt.Tooltip("event_count:Q", title="Events", format=","),
                        alt.Tooltip("seconds:Q", title="Seconds", format=".6f"),
                    ],
                )
                .properties(
                    title=phase_name,
                    height=260,
                    padding={"left": 55, "right": 10, "top": 10, "bottom": 10},
                )
            )
            st.altair_chart(phase_chart, width="stretch")
        st.caption(
            "Each point is the median across completed seed-level task medians. "
            "Initialization creates a fresh empty engine only. Event replay then "
            "processes the entire preloaded stream, including book growth, matching, "
            "and cancellations; input parsing remains outside both phases. The two "
            "full-width panels share one logarithmic y-domain."
        )

    throughput_repeats = frame(data, "throughput_repeats")
    repeat_view = throughput_repeats[
        (throughput_repeats["experiment_group"] == selected_group)
        & (throughput_repeats["scenario"] == selected_scenario)
        & (throughput_repeats["levels"] == selected_levels)
    ].copy()
    if not repeat_view.empty:
        st.markdown("#### Raw-repeat throughput distribution")
        repeat_view["event_label"] = repeat_view["event_count"].map(
            lambda value: f"{int(value):,}"
        )
        event_order = [
            f"{int(value):,}" for value in sorted(status_view["event_count"].unique())
        ]
        shared_repeat_domain = [
            float(repeat_view["throughput_events_per_second"].min()) * 0.8,
            float(repeat_view["throughput_events_per_second"].max()) * 1.25,
        ]
        for version_name in ["baseline", "revised"]:
            version_repeats = repeat_view[repeat_view["version"] == version_name]
            if version_repeats.empty:
                continue
            repeat_chart = (
                alt.Chart(version_repeats)
                .mark_boxplot(extent="min-max", size=45)
                .encode(
                    x=alt.X(
                        "event_label:N",
                        title="Event count",
                        scale=alt.Scale(domain=event_order),
                        axis=alt.Axis(labelAngle=0),
                    ),
                    y=alt.Y(
                        "throughput_events_per_second:Q",
                        title="Events/second (log)",
                        scale=alt.Scale(type="log", domain=shared_repeat_domain),
                    ),
                    color=alt.Color(
                        "version:N",
                        legend=None,
                        scale=alt.Scale(
                            domain=["baseline", "revised"],
                            range=["#0B57D0", "#5AB7EB"],
                        ),
                    ),
                )
                .properties(
                    title=f"{version_name.capitalize()} raw repeats",
                    height=260,
                    padding={"left": 55, "right": 10, "top": 10, "bottom": 10},
                )
            )
            st.altair_chart(repeat_chart, width="stretch")
        st.caption(
            "Full-width version panels share the same logarithmic y-domain. Boxes "
            "summarize every saved raw repeat across the available seeds; whiskers "
            "show the saved minimum and maximum. Requested event counts remain on "
            "the axis, while stopped tasks appear as honest gaps with no fabricated "
            "samples."
        )

    st.markdown("#### Completed-run timing details")
    st.caption(
        "Unlike task coverage, this table contains only completed runs and exposes "
        "their construction, replay, and throughput measurements."
    )
    st.dataframe(
        selected[
            [
                "version",
                "scenario",
                "event_count",
                "seed",
                "levels",
                "median_construction_seconds",
                "median_replay_seconds",
                "throughput_events_per_second",
            ]
        ].sort_values(["scenario", "event_count", "seed", "version"]),
        width="stretch",
        hide_index=True,
    )
    st.subheader("Matched completed pairs")
    st.caption("Speedup is omitted whenever either version stopped or is missing.")
    comparison_view = comparisons[
        (comparisons["experiment_group"] == selected_group)
        & (comparisons["scenario"] == selected_scenario)
        & (comparisons["levels"] == selected_levels)
    ]
    st.dataframe(comparison_view, width="stretch", hide_index=True)
    st.subheader("Stopped and failed runs")
    st.dataframe(
        status_view[status_view["outcome"] != "completed"],
        width="stretch",
        hide_index=True,
    )

with tab_latency:
    st.subheader("Per-event processing latency")
    st.caption(
        "Formal latency coverage: buildup uses event counts 1,000/10,000/100,000 "
        "and seeds 42/43/44. The other workloads use the preregistered "
        "representative 10,000-event, seed-42 run; their multi-seed scaling is "
        "measured in throughput and memory."
    )
    latency = frame(data, "latency_summaries")
    latency["median_us"] = latency["median_ns"] / 1_000
    latency["p95_us"] = latency["p95_ns"] / 1_000
    latency["p99_us"] = latency["p99_ns"] / 1_000
    latency_statuses = statuses[statuses["phase"] == "latency"]
    scenario = st.selectbox(
        "Latency scenario", sorted(latency_statuses["scenario"].unique())
    )
    latency_status_view = latency_statuses[
        latency_statuses["scenario"] == scenario
    ]
    latency_counts = sorted(latency_status_view["event_count"].unique())
    default_latency_count = (
        latency_counts.index(10_000) if 10_000 in latency_counts else 0
    )
    latency_count = st.selectbox(
        "Latency event count", latency_counts, index=default_latency_count
    )
    latency_status_view = latency_status_view[
        latency_status_view["event_count"] == latency_count
    ]
    latency_levels = sorted(latency_status_view["levels"].unique())
    default_latency_levels = (
        latency_levels.index(1_000) if 1_000 in latency_levels else 0
    )
    latency_level = st.selectbox(
        "Latency configured price levels per side",
        latency_levels,
        index=default_latency_levels,
    )
    latency_status_view = latency_status_view[
        latency_status_view["levels"] == latency_level
    ]
    latency_seeds = sorted(latency_status_view["seed"].unique())
    completed_versions_by_seed = (
        latency_status_view[latency_status_view["outcome"] == "completed"]
        .groupby("seed")["version"]
        .nunique()
    )
    matched_seeds = sorted(
        int(seed)
        for seed, version_count in completed_versions_by_seed.items()
        if version_count == 2
    )
    default_latency_seed = (
        latency_seeds.index(matched_seeds[0]) if matched_seeds else 0
    )
    latency_seed = st.selectbox(
        "Latency seed", latency_seeds, index=default_latency_seed
    )
    latency_status_view = latency_status_view[
        latency_status_view["seed"] == latency_seed
    ]
    latency_view = latency[
        (latency["scenario"] == scenario)
        & (latency["event_count"] == latency_count)
        & (latency["levels"] == latency_level)
        & (latency["seed"] == latency_seed)
    ].copy()
    stopped_latency = latency_status_view[
        latency_status_view["outcome"] != "completed"
    ]
    if not stopped_latency.empty:
        stopped_text = ", ".join(
            f"{row.version}: {row.outcome}{timeout_suffix(row.timeout_seconds)}"
            for row in stopped_latency.itertuples()
        )
        st.warning(
            "No latency distribution exists for stopped runs: " + stopped_text
        )
    st.dataframe(
        latency_status_view[
            ["version", "event_count", "seed", "outcome", "timeout_seconds"]
        ],
        width="stretch",
        hide_index=True,
    )
    latency_long = latency_view.melt(
        id_vars=["version", "scope"],
        value_vars=["median_us", "p95_us", "p99_us"],
        var_name="percentile",
        value_name="latency_us",
    )
    latency_long["percentile"] = latency_long["percentile"].map(
        {"median_us": "Median", "p95_us": "P95", "p99_us": "P99"}
    )
    latency_long["scope_label"] = latency_long["scope"].map(
        {
            "overall": "Overall",
            "early_10_percent": "Early 10%",
            "late_10_percent": "Late 10%",
            "event_type:LIMIT": "LIMIT events",
            "event_type:CANCEL": "CANCEL events",
            "event_type:MARKET_SELL": "MARKET_SELL events",
        }
    ).fillna(latency_long["scope"])
    scope_order = [
        scope
        for scope in ["Overall", "Early 10%", "Late 10%"]
        if scope in set(latency_long["scope_label"])
    ] + sorted(
        scope
        for scope in set(latency_long["scope_label"])
        if scope not in {"Overall", "Early 10%", "Late 10%"}
    )
    if latency_long.empty:
        st.info("No completed latency measurement exists for this selection.")
    else:
        shared_latency_domain = [
            float(latency_long["latency_us"].min()) * 0.8,
            float(latency_long["latency_us"].max()) * 1.25,
        ]
        for percentile_name in ["Median", "P95", "P99"]:
            percentile_view = latency_long[
                latency_long["percentile"] == percentile_name
            ]
            latency_chart = (
                alt.Chart(percentile_view)
                .mark_point(filled=True, size=100)
                .encode(
                    x=alt.X(
                        "scope_label:N",
                        title="Scope",
                        sort=scope_order,
                        axis=alt.Axis(labelAngle=0, labelLimit=180),
                    ),
                    xOffset=alt.XOffset(
                        "version:N", sort=["baseline", "revised"]
                    ),
                    y=alt.Y(
                        "latency_us:Q",
                        title="Microseconds (log)",
                        scale=alt.Scale(type="log", domain=shared_latency_domain),
                    ),
                    color=alt.Color(
                        "version:N",
                        title="Version",
                        sort=["baseline", "revised"],
                    ),
                    tooltip=[
                        alt.Tooltip("percentile:N", title="Percentile"),
                        alt.Tooltip("version:N", title="Version"),
                        alt.Tooltip("scope_label:N", title="Scope"),
                        alt.Tooltip(
                            "latency_us:Q", title="Microseconds", format=",.3f"
                        ),
                    ],
                )
                .properties(
                    title=percentile_name,
                    height=240,
                    padding={"left": 55, "right": 10, "top": 10, "bottom": 10},
                )
            )
            st.altair_chart(latency_chart, width="stretch")
        st.caption(
            "Median, p95, and p99 use the saved nearest-rank convention. The "
            "three full-width panels share one logarithmic y-domain and keep both "
            "versions visible; these are processing times, not network or queuing "
            "latency."
        )
    st.dataframe(latency_view, width="stretch", hide_index=True)

with tab_memory:
    st.subheader("Traced Python allocation")
    memory = frame(data, "memory_finals")
    memory["current_mib"] = mib(memory["current_bytes"])
    memory["peak_mib"] = mib(memory["peak_bytes"])
    checkpoints = frame(data, "memory_checkpoints")
    checkpoints["current_mib"] = mib(checkpoints["current_bytes"])
    checkpoints["peak_mib"] = mib(checkpoints["peak_bytes"])
    memory_modes = sorted(memory["mode"].unique())
    default_memory_mode = (
        memory_modes.index("memory_state") if "memory_state" in memory_modes else 0
    )
    memory_mode = st.selectbox(
        "Memory mode", memory_modes, index=default_memory_mode
    )
    memory_statuses = statuses[statuses["phase"] == memory_mode]
    memory_scenarios = sorted(memory_statuses["scenario"].unique())
    default_memory_scenario = (
        memory_scenarios.index("cancel_churn")
        if "cancel_churn" in memory_scenarios
        else 0
    )
    memory_scenario = st.selectbox(
        "Memory scenario", memory_scenarios, index=default_memory_scenario
    )
    memory_status_view = memory_statuses[
        memory_statuses["scenario"] == memory_scenario
    ]
    memory_counts = sorted(memory_status_view["event_count"].unique())
    memory_count = st.selectbox(
        "Memory event count", memory_counts, index=len(memory_counts) - 1
    )
    memory_status_view = memory_status_view[
        memory_status_view["event_count"] == memory_count
    ]
    memory_levels = sorted(memory_status_view["levels"].unique())
    default_memory_levels = (
        memory_levels.index(1_000) if 1_000 in memory_levels else 0
    )
    memory_level = st.selectbox(
        "Memory configured price levels per side",
        memory_levels,
        index=default_memory_levels,
    )
    memory_status_view = memory_status_view[
        memory_status_view["levels"] == memory_level
    ]
    memory_seeds = sorted(memory_status_view["seed"].unique())
    default_memory_seed = memory_seeds.index(42) if 42 in memory_seeds else 0
    memory_seed = st.selectbox(
        "Memory seed", memory_seeds, index=default_memory_seed
    )
    memory_status_view = memory_status_view[
        memory_status_view["seed"] == memory_seed
    ]
    memory_view = memory[
        (memory["mode"] == memory_mode)
        & (memory["scenario"] == memory_scenario)
        & (memory["event_count"] == memory_count)
        & (memory["levels"] == memory_level)
        & (memory["seed"] == memory_seed)
    ].copy()
    trajectory = checkpoints[
        (checkpoints["mode"] == memory_mode)
        & (checkpoints["scenario"] == memory_scenario)
        & (checkpoints["event_count"] == memory_count)
        & (checkpoints["levels"] == memory_level)
        & (checkpoints["seed"] == memory_seed)
    ].copy()
    stopped_memory = memory_status_view[
        memory_status_view["outcome"] != "completed"
    ]
    if not stopped_memory.empty:
        stopped_text = ", ".join(
            f"{row.version}: {row.outcome}{timeout_suffix(row.timeout_seconds)}"
            for row in stopped_memory.itertuples()
        )
        st.warning("No memory value exists for stopped runs: " + stopped_text)
    st.dataframe(
        memory_status_view[
            ["version", "event_count", "seed", "outcome", "timeout_seconds"]
        ],
        width="stretch",
        hide_index=True,
    )
    if memory_view.empty:
        st.info("No completed memory measurement exists for this selection.")
    else:
        final_memory_long = memory_view.melt(
            id_vars=["version"],
            value_vars=["current_mib", "peak_mib"],
            var_name="allocation",
            value_name="mib",
        )
        final_memory_long["allocation"] = final_memory_long["allocation"].map(
            {"current_mib": "Final current", "peak_mib": "Peak"}
        )
        final_memory_chart = (
            alt.Chart(final_memory_long)
            .mark_point(filled=True, size=140)
            .encode(
                x=alt.X(
                    "allocation:N",
                    title="Allocation measurement",
                    sort=["Final current", "Peak"],
                ),
                xOffset=alt.XOffset(
                    "version:N", sort=["baseline", "revised"]
                ),
                y=alt.Y(
                    "mib:Q",
                    title="MiB (log)",
                    scale=alt.Scale(type="log"),
                ),
                color=alt.Color(
                    "version:N",
                    title="Version",
                    sort=["baseline", "revised"],
                ),
                tooltip=[
                    alt.Tooltip("allocation:N", title="Measurement"),
                    alt.Tooltip("version:N", title="Version"),
                    alt.Tooltip("mib:Q", title="MiB", format=".6f"),
                ],
            )
            .properties(padding={"left": 55, "right": 10, "top": 10, "bottom": 10})
        )
        st.altair_chart(final_memory_chart, width="stretch")
        st.dataframe(memory_view, width="stretch", hide_index=True)
    if not trajectory.empty:
        trajectory_chart = (
            alt.Chart(trajectory)
            .mark_line(point=alt.OverlayMarkDef(filled=True, size=45))
            .encode(
                x=alt.X("event_index:Q", title="Processed events"),
                y=alt.Y(
                    "current_mib:Q",
                    title="Current MiB (log)",
                    scale=alt.Scale(type="log"),
                ),
                color=alt.Color(
                    "version:N",
                    title="Version",
                    sort=["baseline", "revised"],
                ),
                tooltip=[
                    alt.Tooltip("version:N", title="Version"),
                    alt.Tooltip("event_index:Q", title="Events", format=","),
                    alt.Tooltip("current_mib:Q", title="Current MiB", format=".6f"),
                    alt.Tooltip("peak_mib:Q", title="Peak MiB", format=".6f"),
                ],
            )
            .properties(padding={"left": 55, "right": 10, "top": 10, "bottom": 10})
        )
        st.altair_chart(trajectory_chart, width="stretch")
    st.caption(
        "State-only and retained-output modes are separate. Post-cancellation state "
        "must not be confused with retained result history. The default view is "
        "the largest saved state-only cancellation-churn run. `tracemalloc` does "
        "not measure total process or native memory."
    )

with tab_liquidation:
    st.subheader("Fresh-book 10%, 100%, and 200% market sells")
    liquidation = frame(data, "liquidation_summaries")
    liquidation_long = liquidation.melt(
        id_vars=["version", "sale_size"],
        value_vars=["median_construction_seconds", "median_sale_seconds"],
        var_name="phase",
        value_name="seconds",
    )
    liquidation_long["phase"] = liquidation_long["phase"].map(
        {
            "median_construction_seconds": "Fresh-book construction",
            "median_sale_seconds": "Market sell",
        }
    )
    liquidation_long["sale_label"] = liquidation_long["sale_size"].map(
        {"10_percent": "10%", "100_percent": "100%", "200_percent": "200%"}
    )
    sale_order = ["10%", "100%", "200%"]
    shared_domain = [
        float(liquidation_long["seconds"].min()) * 0.8,
        float(liquidation_long["seconds"].max()) * 1.25,
    ]
    for phase_name in ["Fresh-book construction", "Market sell"]:
        phase_view = liquidation_long[liquidation_long["phase"] == phase_name]
        liquidation_chart = (
            alt.Chart(phase_view)
            .mark_line(point=alt.OverlayMarkDef(filled=True, size=90))
            .encode(
                x=alt.X(
                    "sale_label:N",
                    title="Requested sale size",
                    sort=sale_order,
                ),
                y=alt.Y(
                    "seconds:Q",
                    title="Seconds (log)",
                    scale=alt.Scale(type="log", domain=shared_domain),
                ),
                color=alt.Color(
                    "version:N",
                    title="Version",
                    sort=["baseline", "revised"],
                ),
                tooltip=[
                    alt.Tooltip("version:N", title="Version"),
                    alt.Tooltip("sale_label:N", title="Requested size"),
                    alt.Tooltip("seconds:Q", title="Seconds", format=".6f"),
                ],
            )
            .properties(
                title=phase_name,
                height=260,
                padding={"left": 55, "right": 10, "top": 10, "bottom": 10},
            )
        )
        st.altair_chart(liquidation_chart, width="stretch")
    st.caption(
        "Each sale starts from an independently rebuilt identical bid book. The "
        "two full-width charts use the same logarithmic y-domain, keeping both "
        "versions visible while preserving comparison across phases. Construction/"
        "reset time is separate from matching and fill-list construction."
    )
    st.dataframe(liquidation, width="stretch", hide_index=True)
    st.subheader("Raw timing repeats")
    st.dataframe(
        frame(data, "liquidation_repeats"), width="stretch", hide_index=True
    )
    st.subheader("Sale memory and operation counts")
    st.dataframe(
        frame(data, "liquidation_memory"), width="stretch", hide_index=True
    )

with tab_correctness:
    st.subheader("Diagnostic replay outcomes")
    diagnostics = frame(data, "diagnostics")
    st.dataframe(diagnostics, width="stretch", hide_index=True)
    invariant_columns = [
        "final_unique_order_ids",
        "final_positive_quantities",
        "final_uncrossed",
    ]
    all_invariants = bool(
        not diagnostics.empty and diagnostics[invariant_columns].all(axis=None)
    )
    no_rejections = bool(
        not diagnostics.empty and (diagnostics["rejected_events"] == 0).all()
    )
    comparison_columns = [
        column
        for column in diagnostics.columns
        if column not in {"version", "parse_seconds"}
    ]
    diagnostic_pairs = []
    for (diagnostic_scenario, diagnostic_seed), pair in diagnostics.groupby(
        ["scenario", "seed"]
    ):
        versions = set(pair["version"])
        diagnostic_pairs.append(
            {
                "scenario": diagnostic_scenario,
                "seed": diagnostic_seed,
                "both_versions_present": versions == {"baseline", "revised"},
                "all_recorded_counts_and_final_invariants_equal": bool(
                    versions == {"baseline", "revised"}
                    and all(
                        pair[column].nunique(dropna=False) == 1
                        for column in comparison_columns
                    )
                ),
            }
        )
    diagnostic_pair_frame = pd.DataFrame(diagnostic_pairs)
    pairwise_agreement = bool(
        not diagnostic_pair_frame.empty
        and diagnostic_pair_frame[
            "all_recorded_counts_and_final_invariants_equal"
        ].all()
    )
    st.markdown("#### Cross-version diagnostic agreement")
    st.dataframe(diagnostic_pair_frame, width="stretch", hide_index=True)
    if all_invariants and no_rejections and pairwise_agreement:
        st.success(
            "All saved diagnostic final invariants hold, no diagnostic event was "
            "rejected, and both versions have identical recorded counts and final "
            "invariant outcomes for every paired stream."
        )
    else:
        st.error(
            "At least one saved diagnostic invariant, acceptance check, or paired "
            "cross-version comparison failed."
        )
    st.caption(
        "These diagnostic replays support the independent hand-calculated and "
        "event-by-event tests; implementation agreement alone is not a correctness proof."
    )

with tab_raw:
    st.subheader("Saved dashboard tables")
    st.caption(
        "These tables are loaded from saved results; opening this dashboard never "
        "reruns an experiment."
    )
    raw_tables = [
        ("Task statuses and settings", statuses),
        ("Raw throughput repeats", frame(data, "throughput_repeats")),
        ("Matched throughput comparisons", comparisons),
        ("Latency summaries", frame(data, "latency_summaries")),
        ("Memory final states", frame(data, "memory_finals")),
        ("Memory checkpoints", frame(data, "memory_checkpoints")),
        ("Liquidation timing repeats", frame(data, "liquidation_repeats")),
        ("Liquidation memory and counts", frame(data, "liquidation_memory")),
        ("Stress settings", frame(data, "stress_settings")),
    ]
    for table_name, table in raw_tables:
        with st.expander(f"{table_name} ({len(table):,} rows)"):
            st.dataframe(table, width="stretch", hide_index=True)

st.divider()
st.subheader("Measured bottleneck")
st.markdown(
    """
Version A rebuilds an active-ID set and scans the active list for every event;
matching also sorts candidates and shifts the list when makers are removed.
Its work therefore grows with active book depth `B`. Version B indexes active
IDs and groups FIFO makers by price, removing those repeated `B` scans. The
saved buildup early/late latency and timeout records expose this difference,
while cancellation churn shows that a large event count `M` alone is not the
bottleneck when active depth remains near zero. Version B pays higher live-state
memory and `O(P)` sorted-list shifts when price levels appear or disappear.
"""
)
