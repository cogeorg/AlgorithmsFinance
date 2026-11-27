"""Streamlit dashboard for saved timing and memory measurements."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SUMMARY = (
    PROJECT_ROOT / "04_results" / "benchmarks" / "result_02_median_summary.csv"
)
BENCHMARK_RAW = (
    PROJECT_ROOT / "04_results" / "benchmarks" / "result_01_raw_repetitions.csv"
)
MEMORY_RESULTS = (
    PROJECT_ROOT / "04_results" / "memory" / "result_01_memory_measurements.csv"
)
ENVIRONMENT_RESULTS = (
    PROJECT_ROOT / "04_results" / "metadata" / "result_01_environment.json"
)


@st.cache_data
def load_results() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Load saved results only; never execute a measurement from the dashboard."""

    summary = pd.read_csv(BENCHMARK_SUMMARY)
    raw = pd.read_csv(BENCHMARK_RAW)
    memory = pd.read_csv(MEMORY_RESULTS)
    environment = json.loads(ENVIRONMENT_RESULTS.read_text(encoding="utf-8"))
    return summary, raw, memory, environment


def method_label(frame: pd.DataFrame) -> pd.Series:
    return frame["method"] + " (" + frame["algorithm_version"] + ")"


def timing_chart(
    frame: pd.DataFrame,
    value_column: str,
    title: str,
) -> None:
    chart_frame = frame.copy()
    chart_frame["method_label"] = method_label(chart_frame)
    pivot = chart_frame.pivot_table(
        index="array_size",
        columns="method_label",
        values=value_column,
        aggfunc="first",
    ).sort_index()
    st.subheader(title)
    st.line_chart(
        pivot,
        x_label="Input array size (n)",
        y_label="Elapsed seconds per complete query batch",
    )


def main() -> None:
    st.set_page_config(page_title="Algorithms in Finance", layout="wide")
    st.title("Algorithms in Finance — Phase 1 Results")
    st.caption(
        "This dashboard reads previously saved measurements and never reruns "
        "benchmarks when controls change."
    )

    missing = [
        path
        for path in (
            BENCHMARK_SUMMARY,
            BENCHMARK_RAW,
            MEMORY_RESULTS,
            ENVIRONMENT_RESULTS,
        )
        if not path.exists()
    ]
    if missing:
        st.error("Missing saved result files: " + ", ".join(map(str, missing)))
        st.stop()

    summary, raw, memory, environment = load_results()

    query_count = st.sidebar.selectbox(
        "Query count (q)", sorted(summary["query_count"].unique())
    )
    scenario = st.sidebar.selectbox(
        "Query scenario", sorted(summary["scenario"].unique())
    )
    filtered = summary[
        (summary["query_count"] == query_count)
        & (summary["scenario"] == scenario)
    ]

    st.write(
        f"Selected complete query batch: q={query_count}, scenario={scenario}. "
        "All timing values are medians of five repetitions."
    )
    st.dataframe(
        filtered[
            [
                "array_size",
                "method",
                "algorithm_version",
                "actual_hit_rate",
                "median_preparation_seconds",
                "median_query_batch_seconds",
                "median_total_seconds",
            ]
        ].sort_values(["array_size", "method"]),
        width="stretch",
        hide_index=True,
    )

    preparation_tab, query_tab, total_tab = st.tabs(
        ["Preparation", "Query batch", "Total"]
    )
    with preparation_tab:
        timing_chart(
            filtered,
            "median_preparation_seconds",
            "Median preparation time",
        )
    with query_tab:
        timing_chart(
            filtered,
            "median_query_batch_seconds",
            "Median complete query-batch time",
        )
    with total_tab:
        timing_chart(
            filtered,
            "median_total_seconds",
            "Median total elapsed time",
        )

    st.header("Memory measurements")
    memory_filtered = memory[
        (memory["query_count"] == query_count)
        & (memory["scenario"] == scenario)
    ].copy()
    memory_filtered["method_label"] = method_label(memory_filtered)
    st.dataframe(
        memory_filtered[
            [
                "array_size",
                "method_label",
                "current_traced_bytes",
                "peak_traced_bytes",
                "preparation_included",
                "output_alive_at_read",
            ]
        ].sort_values(["array_size", "method_label"]),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "tracemalloc reports traced Python allocations, not exact auxiliary "
        "space or every native allocation. Inputs were created before tracing."
    )

    with st.expander("Raw benchmark repetitions"):
        raw_filtered = raw[
            (raw["query_count"] == query_count)
            & (raw["scenario"] == scenario)
        ]
        st.dataframe(raw_filtered, width="stretch", hide_index=True)

    with st.expander("Environment and code-version metadata"):
        st.json(environment)


if __name__ == "__main__":
    main()
