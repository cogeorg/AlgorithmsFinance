"""Streamlit dashboard that reads saved benchmark measurements."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_DIR / "results"
SUMMARY_PATH = RESULTS_DIR / "summary.csv"
RAW_PATH = RESULTS_DIR / "raw_timings.csv"
ENVIRONMENT_PATH = RESULTS_DIR / "environment.json"


st.set_page_config(page_title="Membership Search Runtime", layout="wide")
st.title("Membership Search: Runtime and Memory")
st.caption("Saved measurements only - changing the view never reruns benchmarks.")

missing = [
    path.name
    for path in (SUMMARY_PATH, RAW_PATH, ENVIRONMENT_PATH)
    if not path.exists()
]
if missing:
    st.error(
        "Missing saved results: " + ", ".join(missing) + ". Run `python3 benchmark.py`."
    )
    st.stop()

summary = pd.read_csv(SUMMARY_PATH)
raw = pd.read_csv(RAW_PATH)
environment = json.loads(ENVIRONMENT_PATH.read_text(encoding="utf-8"))

summary["series"] = summary["method"] + " / " + summary["version"]
query_counts = sorted(summary["q"].unique().tolist())
scenarios = sorted(summary["scenario"].unique().tolist())

selected_q = st.sidebar.selectbox("Query count", query_counts)
selected_scenario = st.sidebar.selectbox("Scenario", scenarios)
filtered = summary[
    (summary["q"] == selected_q) & (summary["scenario"] == selected_scenario)
].copy()

hit_rate = filtered["hit_rate"].iloc[0]
st.write(
    f"Complete query batch: **q={selected_q}** | "
    f"scenario: **{selected_scenario}** | hit rate: **{hit_rate:.0%}** | "
    "unit: **seconds per complete batch**"
)

timing_columns = {
    "Preparation": "preparation_median_seconds",
    "Query batch": "query_batch_median_seconds",
    "Total": "total_median_seconds",
}

for heading, value_column in timing_columns.items():
    st.subheader(f"{heading} time")
    chart_data = filtered.pivot(index="n", columns="series", values=value_column)
    st.line_chart(chart_data, x_label="Input length n", y_label="Seconds")

st.subheader("Memory measurements")
memory_table = filtered[
    [
        "method",
        "version",
        "n",
        "q",
        "scenario",
        "memory_current_bytes",
        "memory_peak_bytes",
    ]
].sort_values(["n", "method", "version"])
st.dataframe(memory_table, width="stretch", hide_index=True)
st.caption(environment["memory_scope"])

with st.expander("Raw timing repeats"):
    raw_filtered = raw[
        (raw["q"] == selected_q) & (raw["scenario"] == selected_scenario)
    ]
    st.dataframe(raw_filtered, width="stretch", hide_index=True)
    st.download_button(
        "Download raw timings CSV",
        data=RAW_PATH.read_bytes(),
        file_name="raw_timings.csv",
        mime="text/csv",
    )

with st.expander("Environment and generator settings"):
    st.json(environment)

st.download_button(
    "Download summary CSV",
    data=SUMMARY_PATH.read_bytes(),
    file_name="summary.csv",
    mime="text/csv",
)
