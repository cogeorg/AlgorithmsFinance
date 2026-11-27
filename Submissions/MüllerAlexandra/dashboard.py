"""Streamlit dashboard that reads saved benchmark results without rerunning them."""

from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard_data import (
    filter_records,
    load_results,
    memory_rows,
    raw_repeat_rows,
    timing_rows,
)


RESULTS_PATH = Path(__file__).parent / "results" / "raw_benchmark.json"


st.set_page_config(page_title="Membership Runtime Dashboard", layout="wide")
st.title("Membership algorithm runtime dashboard")
st.caption("Saved measurements only — changing this view never reruns a benchmark.")

if not RESULTS_PATH.exists():
    st.error(
        "No saved results were found at results/raw_benchmark.json. "
        "Run benchmark.py first."
    )
    st.stop()


@st.cache_data
def cached_results(path: str, modified_ns: int):
    """Reload only when the selected saved result file changes."""
    del modified_ns
    return load_results(Path(path))


payload = cached_results(str(RESULTS_PATH), RESULTS_PATH.stat().st_mtime_ns)
records = payload["records"]

query_counts = sorted({record["q"] for record in records})
duplicate_policies = sorted({record["duplicate_policy"] for record in records})

st.sidebar.header("Saved-result filters")
selected_q = st.sidebar.selectbox("Queries per complete batch", query_counts)
available_scenarios = sorted(
    {record["scenario"] for record in records if record["q"] == selected_q}
)
selected_scenario = st.sidebar.selectbox("Query scenario", available_scenarios)
selected_policy = st.sidebar.selectbox("Duplicate policy", duplicate_policies)

selected = filter_records(
    records,
    q=selected_q,
    scenario=selected_scenario,
    duplicate_policy=selected_policy,
)
if not selected:
    st.warning("The saved file has no records for this filter combination.")
    st.stop()

actual_hit_rates = sorted({record["actual_hit_rate"] for record in selected})
requested_hit_rates = sorted({record["requested_hit_rate"] for record in selected})
code_version = payload["environment"]["code_version"]

summary_columns = st.columns(5)
summary_columns[0].metric("Query count", selected_q)
summary_columns[1].metric(
    "Requested hit rate", ", ".join(f"{rate:.0%}" for rate in requested_hit_rates)
)
summary_columns[2].metric(
    "Actual hit rate", ", ".join(f"{rate:.0%}" for rate in actual_hit_rates)
)
summary_columns[3].metric("Duplicate policy", selected_policy)
summary_columns[4].metric("Code version", code_version)

st.subheader("Median elapsed time against input length")
st.caption(
    "Units: milliseconds per preparation, per complete ordered query batch, "
    "or per fresh preparation plus complete batch. Each point is the median "
    "of five repeats."
)

metric_tabs = st.tabs(["Preparation", "Query batch", "Total"])
metric_names = ["preparation", "query_batch", "total"]
for tab, metric_name in zip(metric_tabs, metric_names, strict=True):
    with tab:
        frame = pd.DataFrame(timing_rows(selected, metric_name))
        chart = frame.pivot(
            index="n", columns="method/version", values="elapsed (ms)"
        ).sort_index()
        st.line_chart(chart, x_label="Input length n", y_label="Elapsed (ms)")
        st.dataframe(
            frame.sort_values(["n", "method/version"]),
            hide_index=True,
            width="stretch",
        )

st.subheader("Traced Python memory")
st.caption(payload["definitions"]["tracemalloc"] + ". Units in the table: KiB.")
memory_frame = pd.DataFrame(memory_rows(selected)).sort_values(
    ["n", "method/version"]
)
st.dataframe(memory_frame, hide_index=True, width="stretch")

with st.expander("Raw timing repeats and batching details"):
    raw_frame = pd.DataFrame(raw_repeat_rows(selected)).sort_values(
        ["n", "method/version", "repeat"]
    )
    st.dataframe(raw_frame, hide_index=True, width="stretch")

with st.expander("Measurement definitions and saved settings"):
    st.subheader("Definitions")
    st.json(payload["definitions"])
    st.subheader("Generator and measurement settings")
    st.json(payload["settings"])

with st.expander("Environment details"):
    st.json(payload["environment"])
