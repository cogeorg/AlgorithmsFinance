# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportReturnType=false
# (pandas and altair give no usable types here; the pages are checked by tests/test_dashboard.py)
"""Dashboard for Assignment 1: Version A (baseline) against Version B (revision).

    .venv/bin/streamlit run dashboard/app.py

It only LOADS the saved files in results/ (see dashboard/data.py). It never imports the order
books, never starts a replay, and every number on it was measured earlier. Stopped and not-run runs
are marked in the charts and listed in the tables; nothing is estimated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data  # noqa: E402  (dashboard/data.py)

A_COLOR, B_COLOR, A_LIGHT = "#d9480f", "#1c7ed6", "#f0a37c"
VERSION3_SCALE = alt.Scale(domain=["A", "A_idset", "B"], range=[A_COLOR, A_LIGHT, B_COLOR])
VERSION_SCALE = alt.Scale(domain=["A", "B"], range=[A_COLOR, B_COLOR])      # A and B: the same two colors on every page
MARKER_SHAPES = alt.Scale(domain=["measured (median)", f"stopped at the {data.LIMIT_SECONDS} s limit",
                                  "not run (no value)"], range=["circle", "cross", "diamond"])
LOG_FMT = "~s"

st.set_page_config(page_title="Order book: A against B", layout="wide")
st.markdown("""
<style>
  .block-container {max-width: 1280px; padding-top: 2rem;}
  h1 {font-size: 1.7rem; letter-spacing: -0.01em;}
  h2 {font-size: 1.25rem; margin-top: 1.6rem;}
  [data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
  [data-testid="stSidebar"] {min-width: 15rem;}
  table {font-variant-numeric: tabular-nums;}
</style>""", unsafe_allow_html=True)


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return data.csv(name)


@st.cache_data
def load_json(name: str):
    return data.js(name)


def log_axis(title: str, fmt: str = LOG_FMT) -> alt.Axis:
    return alt.Axis(title=title, format=fmt, grid=True)


def secs_axis(title: str) -> alt.Axis:
    """Seconds on a log axis: decade ticks, plain numbers (0.001, 0.1, 10, 1000)."""
    return alt.Axis(title=title, format=",g", grid=True, values=[0.001, 0.01, 0.1, 1, 10, 100, 1000])


def show(chart, height: int | None = None) -> None:
    st.altair_chart(chart.configure_axis(labelFontSize=12, titleFontSize=12)
                    .configure_legend(orient="bottom", title=None), width="stretch")


def table(df: pd.DataFrame, **kw) -> None:
    st.dataframe(df, hide_index=True, width="stretch", **kw)


def versions_note() -> None:
    st.markdown(f"<span style='color:{A_COLOR}'>■</span> **A** baseline (lists, scans) &nbsp; "
                f"<span style='color:{B_COLOR}'>■</span> **B** revision (price levels, order index)",
                unsafe_allow_html=True)


# --------------------------------------------------------------------------------------------
def page_overview() -> None:
    st.title("Limit order book: A against B")
    st.write("Version A keeps one list of orders per side and scans it. Version B keeps price levels "
             "with FIFO queues and an index of order ids. All numbers on these pages come from "
             "saved result files in `results/`; nothing here is recomputed.")
    versions_note()
    r = data.runs(load("time_raw.csv"))
    ok = r[(r["status"] == "ok") & (r["levels"] == 1000)]
    c = st.columns(4)
    big = ok[(ok["events"] == 100000) & (ok["seed"] == 42)]
    pivot = big.pivot(index="scenario", columns="version", values="median_seconds")
    if {"A", "B"} <= set(pivot.columns):
        speed = (pivot["A"] / pivot["B"]).dropna()
        c[0].metric("Largest speed-up, 100,000 events", f"{speed.max():,.0f}x", speed.idxmax(), delta_color="off", delta_arrow="off")
        c[1].metric("Smallest speed-up", f"{speed.min():.2f}x", speed.idxmin(), delta_color="off", delta_arrow="off")
    c[2].metric("Stopped runs (10 min limit)", int((r["status"] == "stopped").sum()))
    c[3].metric("Not-run runs", int((r["status"] == "not_run").sum()))
    st.subheader("Median replay seconds, 100,000 events, seed 42")
    out = pivot.reset_index()
    out["A / B"] = (out["A"] / out["B"]).round(1)
    table(out.rename(columns={"A": "A (s)", "B": "B (s)"}))
    st.caption("A ran under the same 10 minute limit as B. A run that reached it is marked as stopped "
               "on the scaling page and has no median.")
    st.subheader("Pages")
    st.markdown("""
- **Scaling**: replay seconds against events, log-log, stopped and not-run runs marked.
- **Throughput**: events per second.
- **Latency**: p50, p95, p99, max by event type; first against last 1,000 events; gc on and off.
- **Memory**: held and peak bytes; state after cancellations; cancel churn.
- **Liquidation**, **Concentration**, **Fairness**: individual large sales, few against many price levels, A with an id set.
- **Correctness**: A and B compared after every event.
- **Run-1 incident**: why the first timing run was discarded; canaries.
- **Workload and raw repeats**: settings, checksums, peaks, every repeat.
- **Why A is slow**: the bottleneck with code, operation counts and complexity.
""")


# --------------------------------------------------------------------------------------------
def page_scaling() -> None:
    st.title("Scaling: replay time against events")
    st.write("Seconds to replay one stream through a fresh book (parsing not included), median of 5 "
             "timed replays after a warm-up, gc on. Both axes are logarithmic: a straight line with "
             "slope 1 is linear growth, slope 2 is quadratic.")
    versions_note()
    r = data.marker_column(data.runs(load("time_raw.csv")))
    r = r[r["levels"] == 1000]
    r["median_seconds"] = r["median_seconds"].astype(float)
    r["y"] = r["median_seconds"]
    r.loc[r["status"] == "stopped", "y"] = data.LIMIT_SECONDS
    r.loc[r["status"] == "not_run", "y"] = 2000
    scen = st.multiselect("Scenarios", data.SCENARIOS, default=data.SCENARIOS)
    seeds = st.radio("Seeds", ["all seeds (42, 43, 44) + 1M file", "seed 42 only"], horizontal=True)
    r = r[r["scenario"].isin(scen)]
    if seeds == "seed 42 only":
        r = r[r["seed"] == 42]
    med = r[r["status"] == "ok"].groupby(["version", "scenario", "events"], as_index=False)[
        "median_seconds"].median().rename(columns={"median_seconds": "y"})
    plot = pd.concat([r.assign(kind="run"), med.assign(kind="median over seeds")], ignore_index=True)
    plot["marker"] = plot["marker"].fillna("measured (median)")

    def layers(frame: pd.DataFrame | None = None):
        src = alt.Chart(frame) if frame is not None else alt.Chart()
        enc = dict(x=alt.X("events:Q", scale=alt.Scale(type="log"), axis=log_axis("events (log)")),
                   y=alt.Y("y:Q", scale=alt.Scale(type="log", domain=[0.0005, 3000]),
                           axis=secs_axis("seconds (log)")),
                   color=alt.Color("version:N", scale=VERSION_SCALE))
        line = src.mark_line(strokeWidth=2).encode(**enc).transform_filter(
            alt.datum.kind == "median over seeds")
        points = src.mark_point(size=70, filled=True, opacity=0.7).encode(
            shape=alt.Shape("marker:N", scale=MARKER_SHAPES), **enc,
            tooltip=["version", "scenario", "seed", "events", "status", "median_seconds", "reason"]
        ).transform_filter(alt.datum.kind == "run")
        return line, points

    line, points = layers()
    limit = alt.Chart().mark_rule(strokeDash=[4, 4], color="#868e96").encode(
        y=alt.datum(data.LIMIT_SECONDS))
    show(alt.layer(line, points, limit).properties(width=270, height=230)
         .facet(facet=alt.Facet("scenario:N", sort=data.SCENARIOS), columns=3, data=plot))
    st.markdown("Dashed line: the 600 s limit. **Cross** = stopped at the limit (the true time is "
                "at least 600 s; the value is not known). **Diamond** at the top = not run, no value, "
                "its height means nothing.")
    st.subheader("Construction: the buildup scenario")
    st.write("`buildup` only adds resting orders, so it measures how fast a book is built. "
             "A scans the whole book for every new order, so its curve is steeper than B's.")
    bl, bp = layers(plot[plot["scenario"] == "buildup"])
    show(alt.layer(bl, bp, alt.Chart(pd.DataFrame({"y": [data.LIMIT_SECONDS]})).mark_rule(
        strokeDash=[4, 4], color="#868e96").encode(y="y:Q")).properties(height=300))
    st.subheader("Fitted exponent (slope on the log-log plot, three sizes 1k, 10k, 100k)")
    ex = data.scaling_exponents(data.runs(load("time_raw.csv")))
    table(ex.pivot(index="scenario", columns="version", values="fitted_exponent").reset_index())
    st.caption("A fit through three points, only a description. A needs all three sizes measured; "
               "A on buildup 100,000 events stopped for two of three seeds in run 1 and finished (270 s) "
               "in the repeated run.")
    st.subheader("Every run that did not produce a median")
    bad = r[r["status"] != "ok"][["version", "scenario", "seed", "events", "status", "reason"]]
    table(bad if not bad.empty else pd.DataFrame({"note": ["none"]}))


# --------------------------------------------------------------------------------------------
def page_throughput() -> None:
    st.title("Throughput")
    st.write("Events per second = events / median replay seconds of the run (never 1 / latency).")
    versions_note()
    r = data.runs(load("time_raw.csv"))
    r = r[(r["status"] == "ok") & (r["levels"] == 1000)]
    size = st.select_slider("Events", sorted(r["events"].unique()), value=100000)
    g = r[r["events"] == size].groupby(["version", "scenario"], as_index=False)[
        "throughput_eps"].median()
    show(alt.Chart(g).mark_circle(size=150, opacity=0.9).encode(
        x=alt.X("scenario:N", sort=data.SCENARIOS, axis=alt.Axis(title=None, labelAngle=0)),
        xOffset="version:N",
        y=alt.Y("throughput_eps:Q", scale=alt.Scale(type="log"), axis=log_axis("events per second (log)")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        tooltip=["version", "scenario", alt.Tooltip("throughput_eps:Q", format=",.0f")]
    ).properties(height=340))
    wide = g.pivot(index="scenario", columns="version", values="throughput_eps").reset_index()
    if {"A", "B"} <= set(wide.columns):
        wide["B / A"] = (wide["B"] / wide["A"]).round(1)
    table(wide.round(0))
    st.caption("Median over seeds 42-44 (only seed 42 at 1,000,000 events, and only B finished there on "
               "most scenarios). A scenario missing for a version = stopped or not run at this size.")


# --------------------------------------------------------------------------------------------
def page_latency() -> None:
    st.title("Processing latency")
    st.write("Time of one `process` call, measured per event in a separate instrumented run "
             "(`perf_counter_ns`; the timer itself costs about 40 ns and is not subtracted). "
             "Percentiles by the nearest-rank rule. No queueing, no network: algorithm time only.")
    versions_note()
    s = load("latency_summary.csv")
    s = s[s["status"] == "ok"]
    size = st.radio("Events in the stream", sorted(s["events"].unique()), horizontal=True)
    scen = st.selectbox("Scenario", data.SCENARIOS, index=2)
    q = s[(s["events"] == size) & (s["scenario"] == scen) & (s["window"] == "all")]
    long = q.melt(id_vars=["version", "event_type"], value_vars=["p50_ns", "p95_ns", "p99_ns", "max_ns"],
                  var_name="percentile", value_name="ns")
    long["percentile"] = long["percentile"].str.replace("_ns", "")
    st.subheader("By event type")
    show(alt.Chart(long).mark_circle(size=150, opacity=0.9).encode(
        x=alt.X("percentile:N", sort=["p50", "p95", "p99", "max"], axis=alt.Axis(title=None, labelAngle=0)),
        xOffset="version:N",
        y=alt.Y("ns:Q", scale=alt.Scale(type="log"), axis=log_axis("nanoseconds (log)")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        column=alt.Column("event_type:N", sort=["ALL", "LIMIT", "CANCEL", "MARKET_SELL"], title=None),
        tooltip=["version", "event_type", "percentile", "ns"]).properties(width=180, height=280))
    if q.empty:
        st.info("No latency result for this choice (the run was not run; see the table below).")
    st.subheader("First against last 1,000 events (all event types)")
    st.write("In `buildup` and `crowded` the book grows during the stream. If latency rises as the book "
             "fills, the last window is slower than the first.")
    fl = s[(s["events"] == size) & (s["scenario"].isin(["buildup", "crowded"]))
           & (s["event_type"] == "ALL") & (s["window"].isin(["first1000", "last1000"]))]
    fl = fl.melt(id_vars=["version", "scenario", "window"], value_vars=["p50_ns", "p95_ns", "p99_ns"],
                 var_name="percentile", value_name="ns")
    fl["percentile"] = fl["percentile"].str.replace("_ns", "")
    fl["set"] = fl["version"] + " " + fl["window"].str.replace("1000", " 1,000")
    show(alt.Chart(fl).mark_circle(size=150, opacity=0.9).encode(
        x=alt.X("window:N", sort=["first1000", "last1000"], axis=alt.Axis(title=None, labelAngle=0)),
        xOffset="version:N",
        y=alt.Y("ns:Q", scale=alt.Scale(type="log"), axis=log_axis("nanoseconds (log)")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        column=alt.Column("scenario:N", title=None), row=alt.Row("percentile:N", title=None,
                                                                sort=["p50", "p95", "p99"]),
        tooltip=["version", "scenario", "window", "percentile", "ns"]).properties(width=220, height=120))
    st.subheader("Latency along the stream (20 equal chunks, p50 and p99)")
    pos = load("latency_by_position.csv")
    pos = pos[(pos["events"] == size) & (pos["scenario"] == scen)]
    pl = pos.melt(id_vars=["version", "chunk"], value_vars=["p50_ns", "p99_ns"], var_name="percentile",
                  value_name="ns")
    pl["percentile"] = pl["percentile"].str.replace("_ns", "")
    show(alt.Chart(pl).mark_line(point=True).encode(
        x=alt.X("chunk:O", axis=alt.Axis(title="chunk of the stream (1/20 each)", labelAngle=0)),
        y=alt.Y("ns:Q", scale=alt.Scale(type="log"), axis=log_axis("nanoseconds (log)")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        strokeDash=alt.StrokeDash("percentile:N"), tooltip=["version", "chunk", "percentile", "ns"]
    ).properties(height=300))
    st.subheader("Rare long events: garbage collection on and off")
    st.write("B on `buildup`, 100,000 events, two runs each. With gc on the maximum is about 12 ms; "
             "with gc off it is below 1 ms. So those spikes are garbage-collector pauses. The remaining "
             "gc-off peaks (events 87,381, 43,690 and 21,845) are order-index dict resizes at 2/3 of "
             "capacity: each is one longer insert, and the cost per insert stays amortized O(1).")
    gc = load("latency_gc_test.csv")
    gc = gc.assign(run=gc.groupby("label").cumcount() + 1)
    gc["run"] = gc["label"] + " #" + gc["run"].astype(str)
    show(alt.Chart(gc).mark_circle(size=170, color=B_COLOR).encode(
        x=alt.X("run:N", axis=alt.Axis(title=None, labelAngle=0)),
        y=alt.Y("max_ns:Q", scale=alt.Scale(type="log"), axis=log_axis("maximum latency, nanoseconds (log)")),
        tooltip=["label", "max_ns", "p99_ns", "p999_ns", "events_over_1ms", "gc_collections",
                 "top5_index_ns"]).properties(height=260))
    table(gc[["label", "p50_ns", "p99_ns", "p999_ns", "max_ns", "events_over_1ms", "gc_collections",
              "top5_index_ns"]])
    st.subheader("All latency rows of this choice")
    table(q.drop(columns=[c for c in q.columns if c in ("start_utc", "power_source", "battery_percent",
                                                         "low_power_mode", "status", "reason", "seed")]))
    ns = s_not_run()
    if not ns.empty:
        st.subheader("Not run")
        table(ns)


def s_not_run() -> pd.DataFrame:
    s = load("latency_summary.csv")
    return s[s["status"] != "ok"][["version", "scenario", "events", "status", "reason"]]


# --------------------------------------------------------------------------------------------
def page_memory() -> None:
    st.title("Memory")
    st.write("`tracemalloc` in a separate run, started after the events are loaded. Counted: Python "
             "objects allocated during the replay that are still alive (book structures, the order "
             "index, the current result). Not counted: the input events, the interpreter, memory "
             "outside Python's allocator. \"After replay\" = bytes held after the last event. "
             "No trade history is stored by design.")
    versions_note()
    m = load("memory.csv")
    ok = m[m["status"] == "ok"].copy()
    size = st.radio("Events", sorted(m["events"].unique()), horizontal=True)
    q = ok[ok["events"] == size].melt(id_vars=["version", "scenario"],
                                       value_vars=["final_bytes", "peak_bytes"],
                                       var_name="measure", value_name="bytes")
    q["MB"] = q["bytes"] / 1e6
    q["measure"] = q["measure"].map({"final_bytes": "after replay", "peak_bytes": "peak"})
    show(alt.Chart(q).mark_bar().encode(
        x=alt.X("measure:N", axis=alt.Axis(title=None, labelAngle=0)), xOffset="version:N",
        y=alt.Y("MB:Q", axis=alt.Axis(title="megabytes (linear)")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        column=alt.Column("scenario:N", title=None, sort=data.SCENARIOS + ["insert_then_cancel"]),
        tooltip=["version", "scenario", "measure", alt.Tooltip("bytes:Q", format=",")]
    ).properties(width=120, height=260))
    nr = m[m["events"] == size]
    nr = nr[nr["status"] != "ok"][["version", "scenario", "events", "status", "reason"]]
    if not nr.empty:
        st.markdown("**Not run** (no value; A needs a timing median under 60 s at this size):")
        table(nr)
    st.subheader("State after cancellations")
    st.write("`insert_then_cancel`: N non-crossing orders, then N-1 cancels (one order stays). "
             "B drops empty price levels, but its order-index dict never gives its table back, so B "
             "keeps memory for the **peak** number of active orders (O(peak B)). A, a plain list, "
             "shrinks.")
    ic = ok[ok["scenario"] == "insert_then_cancel"].melt(
        id_vars=["version", "events"], value_vars=["bytes_after_insertion", "final_bytes"],
        var_name="when", value_name="bytes")
    ic["when"] = ic["when"].map({"bytes_after_insertion": "after the N inserts",
                                 "final_bytes": "after the N-1 cancels"})
    ic["MB"] = ic["bytes"] / 1e6
    show(alt.Chart(ic).mark_bar().encode(
        x=alt.X("when:N", sort=["after the N inserts", "after the N-1 cancels"],
                axis=alt.Axis(title=None, labelAngle=-25, labelLimit=240)), xOffset="version:N",
        y=alt.Y("MB:Q", axis=alt.Axis(title="megabytes")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        column=alt.Column("events:O", title="N orders"), tooltip=["version", "when", "bytes"]
    ).properties(width=200, height=260))
    st.subheader("Growth while the book fills (every 10% of the events)")
    sc = st.selectbox("Scenario ", ["buildup", "crowded", "mixed", "sweep"])
    cp = data.checkpoints(ok[(ok["events"] == size) & (ok["scenario"] == sc)])
    if not cp.empty:
        cp["MB"] = cp["bytes"] / 1e6
        show(alt.Chart(cp).mark_line(point=True).encode(
            x=alt.X("percent_of_events:Q", axis=alt.Axis(title="percent of the events replayed")),
            y=alt.Y("MB:Q", axis=alt.Axis(title="megabytes held")),
            color=alt.Color("version:N", scale=VERSION_SCALE)).properties(height=280))
    st.subheader("Cancel churn: memory and time against M")
    st.write("`cancel_churn` adds an order and cancels it again, over and over. The book stays almost "
             "empty, so memory must not grow with M.")
    cc = load("cancel_churn_scaling.csv")
    cc = cc[cc["status"] == "ok"]
    mem = cc.melt(id_vars=["version", "events"], value_vars=["final_bytes", "peak_bytes"],
                  var_name="measure", value_name="bytes")
    mem["measure"] = mem["measure"].map({"final_bytes": "after replay", "peak_bytes": "peak"})
    show(alt.Chart(mem).mark_line(point=True).encode(
        x=alt.X("events:Q", scale=alt.Scale(type="log"), axis=log_axis("events M (log)")),
        y=alt.Y("bytes:Q", scale=alt.Scale(domain=[0, 3500]), axis=alt.Axis(title="bytes")),
        color=alt.Color("version:N", scale=VERSION_SCALE), strokeDash="measure:N",
        tooltip=["version", "events", "measure", "bytes"]).properties(height=280))
    cc["microseconds per event"] = cc["time_per_event_ns"] / 1000
    show(alt.Chart(cc).mark_line(point=True).encode(
        x=alt.X("events:Q", scale=alt.Scale(type="log"), axis=log_axis("events M (log)")),
        y=alt.Y("microseconds per event:Q", scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(title="µs per event (time / M)")),
        color=alt.Color("version:N", scale=VERSION_SCALE)).properties(height=240))
    table(cc[["version", "events", "final_bytes", "peak_bytes", "max_checkpoint_bytes",
              "active_orders_end", "time_median_seconds"]])


# --------------------------------------------------------------------------------------------
def page_liquidation() -> None:
    st.title("Liquidation: one large market sell")
    st.write("A fresh book of N resting bids (buildup, 1,000 price levels); one market sell of 10%, "
             "100% or 200% of the total bid quantity. Only the sell is timed. 200% leaves an unfilled "
             "remainder because the book is empty after 100%.")
    versions_note()
    s = load("liquidation_summary.csv")
    ok = s[s["status"] == "ok"].copy()
    ok["median_sell_seconds"] = ok["median_sell_seconds"].astype(float)
    show(alt.Chart(ok).mark_line(point=True).encode(
        x=alt.X("bids:Q", scale=alt.Scale(type="log"), axis=log_axis("bids in the book N (log)")),
        y=alt.Y("median_sell_seconds:Q", scale=alt.Scale(type="log"), axis=secs_axis("seconds for the sell (log)")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        column=alt.Column("fraction:N", sort=["10%", "100%", "200%"], title="sale size"),
        tooltip=["version", "bids", "fraction", "median_sell_seconds", "fills", "price_levels_visited"]
    ).properties(width=250, height=280))
    cols = ["version", "bids", "fraction", "status", "repeats", "median_sell_seconds", "fills",
            "price_levels_visited", "unfilled_qty_units", "reason"]
    table(s[cols])
    st.caption("A at 100,000 bids: the first trial took over 60 s, so each sale size is one trial "
               "(repeats = 1). Fills = makers touched; levels = distinct fill prices. A and B produce the "
               "same fills (equal hashes in the raw file).")


def page_concentration() -> None:
    st.title("Queue concentration")
    st.write("Same 100,000 buildup orders, spread over 4 to 4,000 price levels. Few levels = long FIFO "
             "queues; many levels = a long sorted price list.")
    versions_note()
    r = data.marker_column(data.runs(load("concentration_raw.csv")))
    r["median_seconds"] = r["median_seconds"].astype(float)
    show(alt.Chart(r).mark_line(point=True).encode(
        x=alt.X("levels:Q", scale=alt.Scale(type="log"), axis=log_axis("price levels (log)")),
        y=alt.Y("median_seconds:Q", scale=alt.Scale(type="log"), axis=secs_axis("seconds, 100,000 events (log)")),
        color=alt.Color("version:N", scale=VERSION_SCALE),
        tooltip=["version", "levels", "median_seconds", "repeats", "status"]).properties(height=340))
    table(r[["version", "levels", "status", "repeats", "median_seconds"]].sort_values(["version", "levels"]))
    st.caption("A is flat: it scans all orders whatever the price structure (one measurement per level, "
               "first replay over 60 s). B changes by about 15% between 4 and 4,000 levels.")


def page_fairness() -> None:
    st.title("Fairness check: A plus an id set")
    st.write("A checks \"is this order id live?\" with a scan on every event. A fair reviewer may "
             "ask whether a baseline with a set of live ids would already be fast. `A_idset` is A with "
             "exactly that one change (10,000 events, seed 42). It is a labeled variant, not Version A.")
    versions_note()
    f = data.runs(load("fairness_time.csv"))
    f = f[f["status"] == "ok"].copy()
    f["median_seconds"] = f["median_seconds"].astype(float)
    show(alt.Chart(f).mark_circle(size=150, opacity=0.9).encode(
        x=alt.X("scenario:N", sort=data.SCENARIOS, axis=alt.Axis(title=None, labelAngle=0)), xOffset="version:N",
        y=alt.Y("median_seconds:Q", scale=alt.Scale(type="log"), axis=secs_axis("seconds (log)")),
        color=alt.Color("version:N", scale=VERSION3_SCALE, sort=["A", "A_idset", "B"]),
        tooltip=["version", "scenario", "median_seconds"]).properties(height=340))
    w = f.pivot(index="scenario", columns="version", values="median_seconds")
    w["A / A_idset"] = (w["A"] / w["A_idset"]).round(2)
    w["A_idset / B"] = (w["A_idset"] / w["B"]).round(1)
    table(w.reset_index().round(5))
    st.markdown("The id set removes about half of A's time on buildup, crowded, mixed and sweep. "
                "A with the set is still 100 to 200 times slower than B on buildup, crowded and sweep, "
                "because every new order still scans the opposite side for the best price.")


def page_correctness() -> None:
    st.title("Correctness: A against B")
    st.write("A and B replay the same stream; every result, the best bid and ask and the final book "
             "are compared after **every** event. The hand-written tests (validation, matching, "
             "invariants) are separate and run with `pytest`.")
    c = load("correctness.csv")
    k = st.columns(3)
    k[0].metric("Streams compared", len(c))
    k[1].metric("Streams with equal results", int(c["all_results_equal"].sum()))
    k[2].metric("Events compared", f"{int(c['results_compared'].sum()):,}")
    table(c.rename(columns={"all_results_equal": "all results equal",
                            "best_prices_equal": "best bid/ask equal",
                            "final_book_equal": "final book equal"}))
    st.caption("Streams of 1,000, 5,000 and 10,000 events (A is too slow to compare larger files after every "
               "event; see the report).")


def page_incident() -> None:
    st.title("Run-1 incident: why the first timing run was discarded")
    st.write("In the first full timing run (`time_raw_run1.csv`), B on `buildup` with 100,000 events took "
             "about 0.20 s for seeds 42 and 43 and about 0.09 s for seed 44, steady inside each run. Code "
             "and data were identical; the machine was in a different state (in use, maybe on battery). "
             "That run kept no power state, so the cause is not proven. The grid was repeated with "
             "canary runs and a logged power state.")
    versions_note()
    r1 = data.runs(load("time_raw_run1.csv"))
    r2 = data.runs(load("time_raw.csv"))
    both = pd.concat([r1.assign(run="run 1 (discarded)"), r2.assign(run="run 2 (reported)")])
    sel = both[(both["version"] == "B") & (both["scenario"] == "buildup") & (both["events"] == 100000)
               & (both["levels"] == 1000)].copy()
    sel["median_seconds"] = sel["median_seconds"].astype(float)
    show(alt.Chart(sel).mark_bar().encode(
        x=alt.X("seed:O", axis=alt.Axis(title="seed", labelAngle=0)), xOffset="run:N",
        y=alt.Y("median_seconds:Q", axis=alt.Axis(title="seconds, B buildup 100,000 events")),
        color=alt.Color("run:N", scale=alt.Scale(range=["#adb5bd", B_COLOR])),
        tooltip=["run", "seed", "median_seconds"]).properties(height=300))
    st.subheader("B: run 2 divided by run 1, all finished runs")
    m = r1.merge(r2, on=data.RUN_KEY, suffixes=("_1", "_2"))
    m = m[(m["status_1"] == "ok") & (m["status_2"] == "ok") & (m["version"] == "B")]
    m["ratio run2 / run1"] = (m["median_seconds_2"].astype(float) / m["median_seconds_1"].astype(float))
    m["stream"] = m["scenario"] + " " + m["events"].astype(str) + " s" + m["seed"].astype(str)
    show(alt.Chart(m).mark_circle(size=60, color=B_COLOR).encode(
        x=alt.X("events:Q", scale=alt.Scale(type="log"), axis=log_axis("events (log)")),
        y=alt.Y("ratio run2 / run1:Q", scale=alt.Scale(domain=[0.3, 1.3]), axis=alt.Axis(title="run 2 / run 1")),
        tooltip=["stream", "ratio run2 / run1"]).properties(height=260))
    st.subheader("Canary: B, mixed, 100,000 events, before and after every block of runs")
    st.write("A canary is a fixed small run repeated before and after each block. If the machine "
             "changes state, the canary changes. In run 2 and the later measurements it stayed flat.")
    cb = data.canary_blocks(load("canary_raw.csv"))
    cb["order"] = range(len(cb))
    show(alt.Chart(cb).mark_circle(size=45, color=B_COLOR).encode(
        x=alt.X("order:Q", axis=alt.Axis(title="canary run in time order")),
        y=alt.Y("median_seconds:Q", scale=alt.Scale(domain=[0, 0.12]), axis=alt.Axis(title="seconds (median of 5)")),
        shape=alt.Shape("canary_point:N"), tooltip=["start_utc", "block", "canary_point", "median_seconds"]
    ).properties(height=260))
    k = st.columns(3)
    k[0].metric("Canary runs", len(cb))
    k[1].metric("Lowest / highest (s)", f"{cb['median_seconds'].min():.4f} / {cb['median_seconds'].max():.4f}")
    k[2].metric("On AC power", f"{(cb['power_source'] == 'ac').mean():.0%}")
    table(cb.groupby(["power_source", "low_power_mode"]).size().rename("canary runs").reset_index())


def page_workload() -> None:
    st.title("Workload settings and raw repeats")
    env = load_json("env.json")
    st.subheader("Environment")
    keep = {k: env.get(k) for k in ("python", "implementation", "macos", "mac_model_id", "mac_hardware",
                                    "git_commit", "git_dirty", "timing", "power_at_start", "constants")}
    st.json(keep, expanded=False)
    with st.expander("Dependencies (pip freeze)"):
        st.code("\n".join(env.get("dependencies", [])))
    st.subheader("Generated streams and checksums")
    chk = load_json("generated_data_checksums.json")
    files = pd.DataFrame([{"file": k, **{x: v[x] for x in ("scenario", "events", "seed", "levels",
                                                           "gz_bytes", "decompressed_sha256")}}
                          for k, v in chk.get("files", {}).items()])
    st.write("Same seed and settings give the same events (checked by the decompressed sha256).")
    table(files)
    st.subheader("Flood and workload peaks")
    st.write("B = peak number of active orders, P = peak number of price levels. In `buildup` and "
             "`crowded` every order rests, so B equals M.")
    fp = load("flood_peaks.csv")
    table(fp)
    with st.expander("All streams: fills, outcomes, peaks"):
        table(load("workload_peaks.csv"))
    st.subheader("Raw repeats of the timing run")
    t = load("time_raw.csv")
    c = st.columns(4)
    v = c[0].selectbox("Version", sorted(t["version"].unique()))
    s = c[1].selectbox("Scenario ", data.SCENARIOS)
    e = c[2].selectbox("Events", sorted(t["events"].unique()), index=2)
    sd = c[3].selectbox("Seed", sorted(t["seed"].unique()))
    raw = t[(t["version"] == v) & (t["scenario"] == s) & (t["events"] == e) & (t["seed"] == sd)
            & (t["levels"] == 1000)]
    table(raw[["start_utc", "power_source", "status", "reason", "phase", "repeat", "elapsed_seconds",
               "median_seconds", "repeats", "parse_seconds", "events_done"]])
    st.caption("`warmup` is the first replay; `timed` are the five measured repeats; `single` means the "
               "first replay took over 60 s and was the only one.")


# --------------------------------------------------------------------------------------------
A_IS_LIVE = '''def _is_live(self, order_id: str) -> bool:
    return (any(r[ID] == order_id for r in self._bids)
            or any(r[ID] == order_id for r in self._asks))'''
A_BEST_INDEX = '''def _best_index(side: list[list], is_bid: bool) -> int:
    best = 0
    for i in range(1, len(side)):
        r, b = side[i], side[best]
        ...compare price, then arrival seq...
    return best'''
A_TAKE = '''while qty > 0 and side:
    i = self._best_index(side, side_is_bid)   # scans the whole side, EVERY time
    rec = side[i]
    if limit_price is not None:
        ... if the best price does not cross: break ...
    ...
    if rec[QTY] == 0:
        side.pop(i)                           # moves every later element'''


def page_bottleneck() -> None:
    st.title("Why Version A is slow")
    st.write("In `buildup` there are no cancels and no trades. Every event is a new resting order, "
             "so A does two linear scans per event, and the book grows by one order each time.")
    st.subheader("The code")
    st.markdown("**1. Validation asks every order whether the id is already taken** (every event):")
    st.code(A_IS_LIVE, language="python")
    st.markdown("**2. Matching finds the best price by scanning the whole opposite side**, even when "
                "the new order does not cross (a new buy order scans all asks to find that no ask is low enough):")
    st.code(A_BEST_INDEX, language="python")
    st.code(A_TAKE, language="python")
    st.subheader("Operation counts (separate instrumented runs)")
    c = load("counters.csv")
    a = c[(c["version"] == "A") & (c["status"] == "ok")].copy()
    a = a[a["scenario"].isin(["buildup", "crowded", "sweep"])]
    a["n(n-1)/2"] = a["events"] * (a["events"] - 1) // 2
    a["scan_is_live / (n(n-1)/2)"] = (a["scan_is_live"] / a["n(n-1)/2"]).round(4)
    table(a[["scenario", "events", "scan_is_live", "n(n-1)/2", "scan_is_live / (n(n-1)/2)",
             "best_index_calls", "scan_best_index"]])
    st.write("`scan_is_live` equals n(n-1)/2 exactly for buildup and crowded: event k scans the k-1 "
             "orders already resting, and 1 + 2 + ... + (n-1) = n(n-1)/2. At n = 10,000 that is "
             "49,995,000 record comparisons for the id check alone; `scan_best_index` adds about "
             "25 million (each new order scans the opposite side, about half of the book).")
    cc = a[a["scenario"] == "buildup"]
    lines = cc.melt(id_vars="events", value_vars=["n(n-1)/2", "scan_is_live", "scan_best_index"],
                    var_name="count", value_name="comparisons")
    show(alt.Chart(lines).mark_line(point=alt.OverlayMarkDef(size=90, filled=True)).encode(
        x=alt.X("events:Q", scale=alt.Scale(type="log"), axis=log_axis("events n (log)")),
        y=alt.Y("comparisons:Q", scale=alt.Scale(type="log"), axis=log_axis("record comparisons (log)")),
        color=alt.Color("count:N", scale=alt.Scale(domain=["n(n-1)/2", "scan_is_live", "scan_best_index"],
                                                   range=["#868e96", A_COLOR, A_LIGHT])),
        shape=alt.Shape("count:N", scale=alt.Scale(domain=["n(n-1)/2", "scan_is_live", "scan_best_index"],
                                                   range=["diamond", "circle", "square"])),
        tooltip=["count", "events", alt.Tooltip("comparisons:Q", format=",")]).properties(height=300))
    st.caption("Buildup, measured at 1,000 and 10,000 events. `scan_is_live` lies exactly on n(n-1)/2 "
               "(the grey diamond is hidden behind the circle).")
    b = c[(c["version"] == "B") & (c["status"] == "ok") & (c["scenario"] == "buildup")]
    st.write("B does no scans of orders. Its work on `buildup` is one `insort` into the sorted price list: "
             "elements shifted by C-level `memmove` at 10,000 events:")
    table(b[["scenario", "events", "key_inserts", "key_shift_elements"]])
    st.subheader("Complexity")
    table(pd.DataFrame({
        "operation": ["validate (id live?)", "best price", "insert / add order", "cancel",
                      "one fill", "buildup of M orders", "market sell of F fills"],
        "Version A": ["O(B)", "O(B)", "O(B)", "O(B)", "O(B) (find best + list.pop)", "O(M·B) = O(M²)",
                      "O(F·B)"],
        "Version B": ["O(1)", "O(1)", "O(1) at an existing price; O(P) for a new price", "O(1) amortized",
                      "O(1)", "O(M·P) worst case, small constant", "O(F)"]}))
    st.write("B = active orders, P = price levels, F = fills, M = events. In `buildup` "
             "the number of active orders B grows to M, and each side holds about M/2 of them, so "
             "A's scans get longer with every event and its total is quadratic; this is the slope near 2 on the scaling page.")
    st.subheader("How much of A's time is the id scan?")
    f = data.runs(load("fairness_time.csv"))
    f = f[(f["status"] == "ok") & (f["scenario"].isin(["buildup", "crowded", "sweep"]))]
    w = f.pivot(index="scenario", columns="version", values="median_seconds").astype(float)
    w["share removed by the id set"] = (1 - w["A_idset"] / w["A"]).round(2)
    table(w.reset_index().round(4))
    st.caption("Removing the id scan removes about half of A's time (10,000 events), not two thirds as "
               "the comparison counts alone might suggest: one `_best_index` comparison costs more than "
               "one id comparison. The rest is the best-price scan (and `list.pop` for fills).")
    st.info("Do not read this as a claim that B wins every workload: on `cancel_churn` (an almost empty "
            "book) A and B are within about 10% of each other, and B holds more memory than A.")


PAGES = {
    "Overview": page_overview, "Scaling": page_scaling, "Throughput": page_throughput,
    "Latency": page_latency, "Memory": page_memory, "Liquidation": page_liquidation,
    "Concentration": page_concentration, "Fairness": page_fairness, "Correctness": page_correctness,
    "Run-1 incident": page_incident, "Workload and raw repeats": page_workload,
    "Why A is slow": page_bottleneck,
}

if True:
    wanted = st.query_params.get("page", "Overview")      # ?page=Scaling opens that page
    choice = st.sidebar.radio("Page", list(PAGES), key="page",
                              index=list(PAGES).index(wanted) if wanted in PAGES else 0)
    st.sidebar.caption("Reads results/ only. Nothing is rerun.")
    PAGES[choice]()
