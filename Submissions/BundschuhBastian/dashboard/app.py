"""Report page for the saved results of the membership lab. It measures nothing.

    .venv/bin/streamlit run dashboard/app.py          (run from the lab folder)

Reads results/ (written by bench_time.py, bench_memory.py, check_total.py). If a file is
missing, the page says which commands create it.
"""
import math

import altair as alt
import pandas as pd
import streamlit as st

import loaders
import report
from report import HIT_LABEL, METHOD_LABEL, METHOD_ORDER

st.set_page_config(page_title="Membership search", layout="wide")
st.markdown(
    "<style>.block-container{max-width:1000px;padding-top:2.5rem}"
    "[data-testid=stHeading] h1{font-size:1.6rem !important;font-weight:600 !important}"
    "[data-testid=stHeading] h2,[data-testid=stHeading] h3{font-size:1.05rem !important;"
    "font-weight:600 !important}</style>",
    unsafe_allow_html=True)

COLORS = {"linear_v1": "#8c8c8c", "binary_v1": "#4d4d4d", "binary_v2": "#4d4d4d",
          "hash_v1": "#1f4e79"}
COLOR = alt.Color("method:N", legend=None, scale=alt.Scale(
    domain=METHOD_ORDER, range=[COLORS[m] for m in METHOD_ORDER]))
DASH = alt.StrokeDash("version:N", legend=None, scale=alt.Scale(
    domain=["v1", "v2"], range=[[1, 0], [5, 3]]))       # v1 solid, v2 dashed
SIZES = [1000, 10000, 100000]
CHART_HEIGHT = 210


@st.cache_data
def cached_results(signature):
    return loaders.load_results()


def signature():
    return tuple((name, (loaders.RESULTS_DIR / name).stat().st_mtime)
                 for name in loaders.REQUIRED if (loaders.RESULTS_DIR / name).exists())


def plain_table(frame, formats):
    """Static, quiet table: no index, numbers right-aligned, formatted by `formats`."""
    numeric = [c for c in frame.columns if c in formats]
    styled = (frame.style.hide(axis="index").format(formats)
              .set_properties(subset=numeric, **{"text-align": "right"})
              .set_table_styles([{"selector": "th", "props": [("text-align", "left")]}]))
    st.table(styled)


def line_chart(frame, y_domain, y_title, show_y, labels=None):
    """Thin lines, small points, direct labels at the right end, no legend, no title."""
    n_max = float(frame["n"].max())
    x_scale = alt.Scale(type="log", domain=[min(SIZES) / 1.25, n_max * 4], nice=False)
    y_scale = alt.Scale(type="log", domain=y_domain, nice=False)
    x = alt.X("n:Q", scale=x_scale, title="n (number of IDs)",
              axis=alt.Axis(values=SIZES, format="~s", grid=True))
    y = alt.Y("value:Q", scale=y_scale, title=y_title if show_y else None,
              axis=alt.Axis(format=",~g", grid=True, labels=show_y, ticks=show_y))
    base = alt.Chart(frame).encode(x=x, y=y, color=COLOR)
    line = base.mark_line(strokeWidth=1.5).encode(strokeDash=DASH)
    points = base.mark_point(filled=True, size=16, opacity=1)
    ends = frame[frame["n"] == frame["n"].max()]
    span = math.log10(y_domain[1] / y_domain[0])
    gap = 11.0 / (CHART_HEIGHT - 45) * span
    adjusted = report.spread_labels(dict(zip(ends["method"], ends["value"])), gap,
                                    math.log10(y_domain[0]), math.log10(y_domain[1]))
    names = labels or METHOD_LABEL
    label_frame = pd.DataFrame({"method": list(adjusted), "n": float(frame["n"].max()),
                                "y": list(adjusted.values()),
                                "label": [names[m] for m in adjusted]})
    text = alt.Chart(label_frame).mark_text(
        align="left", baseline="middle", dx=6, fontSize=10).encode(
        x=alt.X("n:Q", scale=x_scale), y=alt.Y("y:Q", scale=y_scale), text="label:N",
        color=COLOR)
    return (alt.layer(line, points, text).properties(height=CHART_HEIGHT)
            .configure_view(stroke=None)
            .configure_axis(labelFontSize=10, titleFontSize=10, labelColor="#444444",
                            titleColor="#444444", gridColor="#e6e6e6", gridWidth=0.6,
                            domainColor="#bbbbbb", tickColor="#bbbbbb",
                            labelFont="sans-serif", titleFont="sans-serif"))


# ---- missing results ----------------------------------------------------------------
missing = loaders.missing_files()
if missing:
    st.title("Membership search: Linear, Binary, Hash set")
    st.markdown("Saved results not found: " + ", ".join(missing) + ". Create them from the "
                "lab folder first:")
    st.code(".venv/bin/python bench_time.py\n.venv/bin/python bench_memory.py", language="bash")
    st.stop()

data = cached_results(signature())
time_summary, time_raw = data["time_summary"], data["time_raw"]
mem_summary, mem_raw = data["mem_summary"], data["mem_raw"]
time_meta, mem_meta = data["time_meta"], data["mem_meta"]
env = time_meta["environment"]

# ---- header -------------------------------------------------------------------------
st.title("Membership search: Linear, Binary, Hash set")
st.caption(f"Bastian Bundschuh · Algorithms in Finance · commit {env['git_commit'][:7]} · "
           f"Python {env['python_version'].split()[0]} · "
           f"{env.get('cpu_model') or env['machine']}")

# ---- findings -----------------------------------------------------------------------
st.subheader("Findings")
st.write(" ".join(report.findings(time_summary, mem_summary)))

# ---- controls -----------------------------------------------------------------------
q_options = sorted(int(v) for v in time_summary["q"].unique())
left, middle, right = st.columns([1, 2, 1.3])
q = left.radio("Queries q", q_options, index=len(q_options) - 1, horizontal=True)
hit = middle.radio("Hit rate", ["mixed", "all-present", "all-absent"],
                   format_func=HIT_LABEL.get, horizontal=True)
per_query = right.radio("Time per", ["batch", "query"], horizontal=True) == "query"
selection = time_summary[(time_summary["q"] == q) & (time_summary["hit_rate"] == hit)]

# ---- figure 1 -----------------------------------------------------------------------
st.subheader("Time by phase")
frames = {}
for phase in loaders.PHASES:
    frame = loaders.scaled_times(selection, phase, per_query, 1.0)       # seconds
    frames[phase] = frame[frame["method"] != "linear_v1"] if phase == "prepare" else frame
unit, factor = report.pick_unit(max(f["value"].max() for f in frames.values()))
for frame in frames.values():
    frame["value"] = frame["value"] * factor
domain = report.log_domain(min(f["value"].min() for f in frames.values()),
                           max(f["value"].max() for f in frames.values()))
titles = {"prepare": "Preparation", "query": "Query batch", "total": "Total"}
columns = st.columns(3)
for index, (phase, column) in enumerate(zip(loaders.PHASES, columns)):
    per_text = frames[phase]["per"].iloc[0]
    # the tick labels are shared when all panels have the same unit per ...
    show_y = index == 0 or per_query
    with column:
        st.write(titles[phase])
        st.altair_chart(line_chart(frames[phase], domain, f"{unit} {per_text}", show_y),
                        theme=None, width="stretch")
unit_text = "per batch" if not per_query else "per query (preparation: per batch)"
st.caption(f"Figure 1. Median time of preparation, query batch and total for q = {q} and "
           f"{HIT_LABEL[hit]} hits in {unit} {unit_text}, one y scale for all three panels; "
           f"linear search has no preparation, and the total is measured on its own.")

# ---- figure 2 -----------------------------------------------------------------------
st.subheader("Binary search: v1 and v2")
frame2 = loaders.scaled_times(selection[selection["algorithm"] == "binary"], "query",
                              per_query, 1.0)
unit2, factor2 = report.pick_unit(frame2["value"].max())
frame2["value"] = frame2["value"] * factor2
domain2 = report.log_domain(frame2["value"].min(), frame2["value"].max())
chart_col, text_col = st.columns([3, 2])
with chart_col:
    st.altair_chart(line_chart(frame2, domain2, f"{unit2} {frame2['per'].iloc[0]}", True,
                               labels={"binary_v1": "v1 recursive",
                                       "binary_v2": "v2 iterative"}),
                    theme=None, width="stretch")
with text_col:
    st.write(report.version_sentence(time_summary, q, hit))
st.caption(f"Figure 2. Query batch of binary search for q = {q} and {HIT_LABEL[hit]} hits, "
           f"v1 solid and v2 dashed, in {unit2} {frame2['per'].iloc[0]}.")

# ---- figure 3 -----------------------------------------------------------------------
st.subheader("Total and preparation plus query")
comparison = loaders.total_vs_sum(time_summary)
shown = comparison[(comparison["q"] == q) & (comparison["hit_rate"] == hit)].copy()
shown["method"] = shown["method"].map(METHOD_LABEL)
for column in ("measured_total", "prepare_plus_query"):
    shown[column] = (shown[column] * 1e3).map(report.round3)
table3 = shown.rename(columns={
    "measured_total": "total (ms)", "prepare_plus_query": "prepare + query (ms)",
    "ratio": "ratio", "spread_prepare": "spread prepare", "spread_query": "spread query",
    "spread_total": "spread total"})[
    ["method", "n", "total (ms)", "prepare + query (ms)", "ratio", "spread prepare",
     "spread query", "spread total"]].reset_index(drop=True)
plain_table(table3, {"n": "{:,.0f}", "total (ms)": report.sig3,
                    "prepare + query (ms)": report.sig3, "ratio": "{:.2f}",
                    "spread prepare": "{:.2f}", "spread query": "{:.2f}",
                    "spread total": "{:.2f}"})
ratios = comparison["ratio"]
st.caption(f"Figure 3. Measured total next to preparation plus query (medians) for q = {q} "
           f"and {HIT_LABEL[hit]} hits, with ratio = total / (preparation + query) and "
           f"spread = max / min of the repeats; over all {len(comparison)} settings the "
           f"ratio is {ratios.min():.2f} to {ratios.max():.2f}.")

# ---- table 1 ------------------------------------------------------------------------
st.subheader("Memory")
memory = mem_summary[(mem_summary["q"] == q) & (mem_summary["hit_rate"] == hit)]
rows = []
for method in METHOD_ORDER:
    for n in sorted(int(v) for v in memory["n"].unique()):
        part = memory[(memory["method"] == method) & (memory["n"] == n)]
        prepared = float(part[part["phase"] == "prepare"]["median_current_bytes"].iloc[0])
        peak = float(part[part["phase"] == "total"]["median_peak_bytes"].iloc[0])
        rows.append({"method": METHOD_LABEL[method], "n": n,
                     "prepared structure (kB)": report.round3(prepared / 1e3),
                     "peak during the call (kB)": report.round3(peak / 1e3)})
plain_table(pd.DataFrame(rows), {"n": "{:,.0f}", "prepared structure (kB)": report.sig3,
                                 "peak during the call (kB)": report.sig3})
st.caption(f"Table 1. Memory allocated by each method for q = {q} and {HIT_LABEL[hit]} hits "
           f"(tracemalloc, kB = 1,000 bytes, input not counted, output kept alive).")

# ---- appendix -----------------------------------------------------------------------
with st.expander("Appendix: protocol, raw repeats, environment and metadata", expanded=False):
    protocol = time_meta["protocol"]
    st.markdown(
        f"- Timer {protocol['timer']}; median of {protocol['repeats']} repeats; "
        f"seed {time_meta['seed']}; same data for every method.\n"
        f"- Preparation, query batch and total are separate measurements; the total is "
        f"its own run, not the sum.\n"
        f"- {protocol['calibration']}; one untimed warm-up repeat; new prepared state "
        f"before every repeat; garbage collector off during a repeat.\n"
        f"- Not timed: data generation, correctness checks, printing.\n"
        f"- Memory: tracemalloc, fresh trace per method and phase, input built before "
        f"tracing, output kept alive.")
    st.write("Raw timing repeats (seconds)")
    st.dataframe(time_raw, hide_index=True, height=260, width="stretch")
    st.write("Raw memory repeats (bytes)")
    st.dataframe(mem_raw, hide_index=True, height=260, width="stretch")
    st.write("Environment")
    st.json(env, expanded=False)
    st.write("Timing metadata")
    st.json({k: v for k, v in time_meta.items() if k != "environment"}, expanded=False)
    st.write("Memory metadata")
    st.json({k: v for k, v in mem_meta.items() if k != "environment"}, expanded=False)
