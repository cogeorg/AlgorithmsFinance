"""Read-only Streamlit view over saved Assignment 1 benchmark evidence."""

from __future__ import annotations

import json
import statistics
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.data import ROOT, load_latency_samples, load_saved_rows


PRIMARY_PHASES = {
    "input_read_parse",
    "empty_engine_construction",
    "initial_book_construction",
    "engine_replay",
    "total_application",
    "sell_operation_10pct",
    "sell_operation_100pct",
    "sell_operation_200pct",
    "total_application_sell_10pct",
    "total_application_sell_100pct",
    "total_application_sell_200pct",
}


def median_seconds(rows: list[dict[str, Any]]) -> float | None:
    valid = [
        row for row in rows
        if row.get("record_status") == "completed"
        and isinstance(row.get("elapsed_seconds"), (int, float))
        and row.get("repeat") is not None
    ]
    if {row["repeat"] for row in valid} != {1, 2, 3, 4, 5} or len(valid) != 5:
        return None
    return statistics.median(row["elapsed_seconds"] for row in valid)


def compatible_pair(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Require matching boundaries, inputs and complete five-repeat sets."""
    for key in ("run_id", "phase", "event_count", "policy", "input_checksums",
                "measurement_definition_id", "measurement_definition_hash"):
        left_value, right_value = left.get(key), right.get(key)
        if key in ("measurement_definition_id", "measurement_definition_hash"):
            left_missing, right_missing = pd.isna(left_value), pd.isna(right_value)
            if left_missing and right_missing:
                continue
        if left_value != right_value:
            return False
    if _json_text(left.get("code_hashes")) != _json_text(right.get("code_hashes")):
        return False
    has_definitions = bool(
        not pd.isna(left.get("measurement_definition_hash"))
        and not pd.isna(left.get("measurement_definition_id"))
        and not pd.isna(right.get("measurement_definition_hash"))
        and not pd.isna(right.get("measurement_definition_id"))
    )
    if has_definitions:
        if _json_text(left.get("phase_settings")) != _json_text(right.get("phase_settings")):
            return False
    elif (
        not str(left.get("policy", "")).startswith("aggregate-")
        or left.get("continuation_status") != "reusable"
        or right.get("continuation_status") != "reusable"
    ):
        return False
    return (
        median_seconds(left.get("rows", [])) is not None
        and median_seconds(right.get("rows", [])) is not None
    )


def _json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value or "")


def main() -> None:
    st.set_page_config(page_title="Assignment 1 evidence", layout="wide")
    st.title("Assignment 1 — saved benchmark evidence")
    st.caption("Read-only dashboard. It loads saved records only; no engines or benchmark runner are imported.")

    all_rows = load_saved_rows()
    if not all_rows:
        st.warning("No saved measurement rows were found. Missing measurements are not treated as zero.")
        return
    frame = pd.DataFrame(all_rows)
    run_options = sorted(frame["run_id"].dropna().unique())
    default_run = "full_20261125" if "full_20261125" in run_options else run_options[-1]
    with st.sidebar:
        st.header("Evidence filters")
        run_id = st.selectbox("Run", run_options, index=run_options.index(default_run), key="run_filter")
        run_frame = frame[frame["run_id"] == run_id]
        scenarios = sorted(str(x) for x in run_frame["scenario"].dropna().unique())
        scenario = st.selectbox("Workload / scenario", ["All"] + scenarios, key="scenario_filter")
        seeds = sorted(int(x) for x in run_frame["seed"].dropna().unique())
        seed = st.selectbox("Seed", ["All"] + seeds, key="seed_filter")
        versions = sorted(str(x) for x in run_frame["version"].dropna().unique())
        version = st.selectbox("Version", ["All"] + versions, key="version_filter")
        policies = sorted(str(x) for x in run_frame["policy"].dropna().unique())
        policy = st.selectbox("Measurement policy", ["All"] + policies, key="policy_filter")

    selected = run_frame.copy()
    if scenario != "All":
        selected = selected[selected["scenario"] == scenario]
    if seed != "All":
        selected = selected[selected["seed"] == seed]
    if version != "All":
        selected = selected[selected["version"] == version]
    if policy != "All":
        selected = selected[selected["policy"] == policy]
    st.caption(f"Selected saved measurement rows: {len(selected)}")

    coverage_path = ROOT / "results" / "coverage.csv"
    if coverage_path.exists():
        coverage = pd.read_csv(coverage_path)
        coverage = coverage[coverage["run_id"] == run_id]
        statuses = coverage["status"].value_counts().to_dict()
        st.subheader("Coverage and correctness evidence")
        st.write({str(k): int(v) for k, v in statuses.items()})
        st.download_button(
            "Download full coverage table",
            coverage.to_csv(index=False),
            file_name=f"{run_id}_coverage.csv",
            mime="text/csv",
        )
        gaps = coverage[coverage["status"] != "completed"]
        st.dataframe(
            gaps[["config_id", "phase", "status", "configuration_status", "policy",
                  "repeat_count", "source_record", "decision"]],
            width="stretch",
        )
    else:
        st.warning("Coverage reconciliation file is missing: results/coverage.csv")

    st.subheader("Construction, replay and fixed-book sells")
    primary = selected[selected["phase"].isin(PRIMARY_PHASES)].copy()
    timing_rows = primary[
        (primary["record_status"] == "completed")
        & primary["elapsed_seconds"].notna()
        & primary["repeat"].notna()
    ]
    if timing_rows.empty:
        st.info("No completed primary timing repeats match these filters.")
    else:
        timing_rows["elapsed_seconds"] = pd.to_numeric(timing_rows["elapsed_seconds"])
        median_records = []
        for key, group in timing_rows.groupby(
            ["scenario", "seed", "event_count", "version", "phase"], dropna=False
        ):
            raw = group.to_dict("records")
            value = median_seconds(raw)
            if value is not None:
                throughput = (
                    float(key[2]) / value
                    if key[4] in ("engine_replay", "total_application") and value > 0 else None
                )
                median_records.append({
                    "scenario": key[0], "seed": key[1], "event_count": key[2],
                    "version": key[3], "phase": key[4], "median_seconds": value,
                    "throughput_events_per_second": throughput,
                })
        if median_records:
            medians = pd.DataFrame(median_records)
            st.dataframe(medians, width="stretch")
            st.bar_chart(medians, x="event_count", y="median_seconds", color="version")
        else:
            st.info("No complete five-repeat primary timing set matches these filters.")
        st.caption("Elapsed time is seconds per repeat. Incomplete repeat sets are listed in coverage and excluded from medians.")

    st.subheader("Compatible paired speedups")
    paired: list[dict[str, Any]] = []
    pair_rows = timing_rows.copy()
    pair_rows["case_key"] = pair_rows["config_id"].str.rsplit("__", n=1).str[0]
    pair_rows["input_key"] = pair_rows["input_checksums"].map(_json_text)
    pair_keys = [
        "case_key", "phase", "event_count", "policy", "input_key",
        "measurement_definition_id", "measurement_definition_hash",
    ]
    for key, group in pair_rows.groupby(pair_keys, dropna=False):
        baseline = group[group["version"] == "baseline"].to_dict("records")
        revised = group[group["version"] == "revised"].to_dict("records")
        if len(baseline) != 5 or len(revised) != 5:
            continue
        # Group rows are raw repeats; compare their common phase-definition metadata.
        left, right = baseline[0], revised[0]
        left_group = {**left, "rows": baseline}
        right_group = {**right, "rows": revised}
        if not compatible_pair(left_group, right_group):
            continue
        bmed, rmed = median_seconds(baseline), median_seconds(revised)
        if bmed and rmed:
            paired.append({
                "config_id": left["config_id"].rsplit("__", 1)[0],
                "phase": left["phase"],
                "event_count": left["event_count"],
                "policy": left["policy"],
                "speedup (baseline/revised)": bmed / rmed,
            })
    if paired:
        st.dataframe(pd.DataFrame(paired), width="stretch")
    else:
        st.info("No complete five-repeat paired measurements with matching inputs and measurement definitions.")

    st.subheader("Latency")
    latency = selected[selected["phase"] == "latency"]
    if latency.empty:
        st.info("No latency measurements match these filters.")
    else:
        columns = [c for c in (
            "scenario", "seed", "event_count", "version", "latency_median_seconds",
            "latency_p95_seconds", "latency_p99_seconds", "early_window_median_seconds",
            "late_window_median_seconds", "latency_process_throughput_events_per_second",
            "latency_percentile_convention", "latency_raw_path", "record_status",
        ) if c in latency.columns]
        st.dataframe(latency[columns], width="stretch")
        st.caption("Per-event latency is seconds/event; diagnostic throughput is events/second. Raw event timing paths are shown when saved.")
        available = latency[latency["latency_raw_path"].notna()]
        if not available.empty:
            choice = st.selectbox(
                "Raw latency distribution",
                available.index,
                format_func=lambda index: (
                    f"{latency.loc[index, 'scenario']} / M={latency.loc[index, 'event_count']} / "
                    f"seed={latency.loc[index, 'seed']} / {latency.loc[index, 'version']}"
                ),
                key="latency_choice",
            )
            samples = load_latency_samples(latency.loc[choice].to_dict())
            times = [
                float(item["elapsed_seconds"])
                for item in samples if item.get("elapsed_seconds") is not None
            ]
            if times:
                bin_count = 40
                maximum = max(times)
                counts = [0] * bin_count
                for value in times:
                    index = min(int(value / maximum * bin_count), bin_count - 1) if maximum else 0
                    counts[index] += 1
                histogram = pd.DataFrame({
                    "latency_seconds_upper_bound": [
                        maximum * (index + 1) / bin_count for index in range(bin_count)
                    ],
                    "events": counts,
                })
                st.bar_chart(histogram, x="latency_seconds_upper_bound", y="events")
                st.caption(f"Raw event samples loaded: {len(times)}; histogram bins are latency seconds and event counts.")

    st.subheader("Memory and post-cancellation state")
    memory = selected[selected["phase"].isin(["memory", "state_peaks", "counters"])]
    if memory.empty:
        st.info("No memory/state diagnostic records match these filters.")
    else:
        columns = [c for c in (
            "scenario", "event_count", "version", "phase", "traced_current_bytes",
            "traced_peak_bytes", "active_order_peak", "occupied_price_level_peak",
            "active_orders", "occupied_price_levels", "physical_storage_entries",
            "physical_heap_entries", "physical_order_entries", "final_active_orders",
            "final_occupied_price_levels", "maker_touches", "visited_price_levels",
            "record_status",
        ) if c in memory.columns]
        st.dataframe(memory[columns], width="stretch")
        st.caption("Tracemalloc bytes are Python-traced allocations, not total process/native memory. Churn rows expose post-cancellation observations when available.")

    st.subheader("Raw primary repeats")
    raw_columns = [c for c in (
        "run_id", "config_id", "phase", "version", "repeat", "elapsed_seconds",
        "requested_sell_qty_units", "fill_count", "active_order_peak",
        "occupied_price_level_peak", "record_status", "policy", "source_record",
    ) if c in primary.columns]
    st.dataframe(primary[raw_columns], width="stretch")
    st.caption("Raw repeat times are seconds; requested sale sizes are integer quantity units. Source records and policies are retained.")

    st.subheader("Price concentration and saved environment")
    concentration = selected[
        (selected["experiment"] == "queue_concentration")
        & selected["phase"].isin(PRIMARY_PHASES)
    ]
    if concentration.empty:
        st.info("Choose a queue-concentration scenario to view realized price-level evidence.")
    else:
        comparison_rows = []
        for key, group in concentration.groupby(
            ["scenario", "version", "phase", "event_count"], dropna=False
        ):
            comparison_rows.append({
                "scenario": key[0],
                "version": key[1],
                "phase": key[2],
                "event_count": key[3],
                "complete_five_repeat_median_seconds": median_seconds(
                    group.to_dict("records")
                ),
                "completed_repeat_count": int(
                    (
                        (group["record_status"] == "completed")
                        & group["repeat"].notna()
                        & group["elapsed_seconds"].notna()
                    ).sum()
                ),
            })
        st.dataframe(pd.DataFrame(comparison_rows), width="stretch")
        st.caption(
            "Compare queue_4_prices with queue_1000_prices by version and phase. "
            "A missing five-repeat median stays blank; the coverage table above "
            "shows stopped and unattempted phases."
        )
    st.markdown(
        "Correctness evidence: the independent specification and parity suites are in "
        "`results/tests_revised.txt`; dashboard and coverage checks are in "
        "`results/dashboard_verification.txt`."
    )
    meta = ROOT / "results" / "benchmarks" / run_id / "metadata.json"
    if meta.exists():
        metadata = json.loads(meta.read_text(encoding="utf-8"))
        row_hashes = selected.iloc[0]["code_hashes"] if not selected.empty else {}
        st.json({
            "environment": metadata.get("environment"),
            "settings": metadata.get("settings"),
            "sampled_code_hashes": row_hashes,
            "parity_validation": metadata.get("parity_validation"),
        })
    st.caption("Counters are small-workload diagnostics; snapshot-derived counts are estimates, not exact executed-operation counts.")


if __name__ == "__main__":
    main()
