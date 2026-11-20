"""Runtime dashboard. Run with:  streamlit run dashboard.py

Loads the SAVED results in results/ (it never reruns a benchmark), so changing the
view is instant and always agrees with the raw data.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

RES = Path(__file__).parent / "results"
HIT_LABEL = {1.0: "1.0 (all present)", 0.0: "0.0 (all absent)", 0.5: "0.5 (mixed)"}

st.set_page_config(page_title="Membership runtime dashboard", layout="wide")
st.title("Membership queries: LinearSearch vs BinarySearch vs hash set")
st.caption("Huang Jiaxin, Algorithms in Finance, Class 2 lab. "
           "bisect_ref is a standard-library reference, not one of my implementations.")

REQUIRED = {
    "timing_summary.csv": "python benchmark.py", "timing_raw.csv": "python benchmark.py",
    "environment.json": "python benchmark.py", "memory.csv": "python memory.py",
    "breakeven_curve.csv": "python breakeven.py", "breakeven_points.csv": "python breakeven.py",
}
missing = [name for name in REQUIRED if not (RES / name).exists()]
if missing:   # audit bug 5: show which file is missing instead of a traceback
    st.error("Missing result files in results/: " + ", ".join(missing) + ". Create them with: "
             + "; ".join(sorted({REQUIRED[name] for name in missing})))
    st.stop()

summary = pd.read_csv(RES / "timing_summary.csv")
raw = pd.read_csv(RES / "timing_raw.csv")
memory = pd.read_csv(RES / "memory.csv")
env = json.loads((RES / "environment.json").read_text())
be_curve = pd.read_csv(RES / "breakeven_curve.csv")
be_points = pd.read_csv(RES / "breakeven_points.csv")

c1, c2, c3, c4 = st.columns(4)
q = c1.selectbox("Query count q", sorted(summary["q"].unique()), index=1)
hit = c2.selectbox("Hit rate", sorted(summary["hit_rate"].unique()),
                   format_func=lambda h: HIT_LABEL.get(h, str(h)))
unit = c3.radio("Unit", ["ms", "s"], horizontal=True)
methods = c4.multiselect("Methods", list(summary["method"].unique()),
                         default=["linear_v2", "binary_v2", "hash"])
scale = 1e3 if unit == "ms" else 1.0

view = summary[(summary["q"] == q) & (summary["hit_rate"] == hit)
               & (summary["method"].isin(methods))]

tabs = st.tabs(["Total", "Preparation", "Query batch", "Revisions",
                "Break-even", "Memory", "Raw data and environment"])

for tab, col, what in zip(tabs[:3], ["total_median_s", "prepare_median_s", "query_median_s"],
                          ["preparation + query batch", "sorted copy or set construction "
                           "(zero for linear)", "complete batch of q queries"]):
    with tab:
        st.caption(f"Elapsed time ({unit}) per COMPLETE batch, {what}. q = {q}, "
                   f"hit rate {HIT_LABEL.get(hit, hit)}. Median of {env['repeats']} "
                   "repeats after one warm-up.")
        table = view.pivot(index="n", columns="method", values=col) * scale
        st.line_chart(table, x_label="array length n", y_label=f"time ({unit})")
        st.dataframe(table.style.format("{:.4f}"))
        raw_col = col.replace("_median", "")
        rv = raw[(raw["q"] == q) & (raw["hit_rate"] == hit) & (raw["method"].isin(methods))]
        spread = rv.groupby(["n", "method"])[raw_col].agg(["min", "max"])
        spread = (spread["max"] / spread["min"]).unstack("method")
        st.caption("Spread of the 5 repeats (max / min). Values far above 1 mean the median "
                   "is uncertain, so small differences between methods are not meaningful.")
        st.dataframe(spread.style.format("{:.2f}"))

with tabs[3]:
    sel = summary[(summary["q"] == q) & (summary["hit_rate"] == hit)]
    for title, old, new, note in [
        ("Revision 1: BinarySearch", "binary_v1", "binary_v2",
         "Original: recursive, copies list slices (Θ(n) per query). "
         "Revised: iterative with index bounds (Θ(log n) per query)."),
        ("Revision 2: LinearSearch", "linear_v1", "linear_v2",
         "Original: while loop with explicit index. Revised: for loop over values. "
         "Same Θ(n) per query; only the constant factor changes."),
    ]:
        st.subheader(title)
        st.caption(note + " Both versions pass the same tests on the same inputs.")
        t = sel.pivot(index="n", columns="method", values="query_median_s")[[old, new]] * scale
        st.line_chart(t, x_label="array length n", y_label=f"query batch ({unit})")
        t["speed-up (original / revised)"] = t[old] / t[new]
        st.dataframe(t.style.format("{:.3f}"))
    st.subheader("My BinarySearch vs library bisect")
    t = sel.pivot(index="n", columns="method", values="query_median_s")[["binary_v2", "bisect_ref"]] * scale
    t["ratio (mine / library)"] = t["binary_v2"] / t["bisect_ref"]
    st.dataframe(t.style.format("{:.3f}"))
    st.caption("bisect is implemented in C; the ratio shows the cost of running the "
               "same Θ(log n) idea in pure Python.")

with tabs[4]:
    st.caption("From how many queries does preparation pay off? Total time = preparation "
               "+ q queries, hit rate 0.5. Methods: best version of each required method.")
    n_be = st.selectbox("Array length n", sorted(be_curve["n"].unique()), index=2)
    t = be_curve[be_curve["n"] == n_be].pivot(index="q", columns="method",
                                              values="total_median_s") * scale
    st.line_chart(t, x_label="number of queries q", y_label=f"total time ({unit})")
    st.dataframe(t.style.format("{:.4f}"))
    st.markdown("**Estimated break-even q\\*** = preparation time ÷ (linear time per query "
                "− method time per query), per-query times measured at q = 1000.")
    st.dataframe(be_points.pivot(index="n", columns="method", values="breakeven_q")
                 .style.format("{:.1f}"))

with tabs[5]:
    st.caption("tracemalloc peak in KiB, hit rate 0.5. Includes the prepared structure, "
               "temporary objects (e.g. slices in binary_v1) and the output list; excludes "
               "the given input array and query list. Python allocations only, so this "
               "is not exactly auxiliary space.")
    mem = memory[memory["q"] == q].pivot(index="n", columns="method", values="peak_bytes") / 1024
    st.dataframe(mem.style.format("{:.1f}"))

with tabs[6]:
    st.subheader("Raw repeat values (seconds per complete batch)")
    st.dataframe(raw[(raw["q"] == q) & (raw["hit_rate"] == hit)])
    st.subheader("Environment and settings")
    st.json(env)
