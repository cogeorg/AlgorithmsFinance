"""Dashboard for Assignment 1. Run from this folder:   streamlit run dashboard.py

It only LOADS the saved results in results/; changing a view never reruns an experiment.
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RES = Path(__file__).resolve().parent / "results"
st.set_page_config(page_title="Limit order book benchmark", layout="wide")
st.title("Limit order book: version A (baseline) vs version B (revision)")
st.caption("Huang Jiaxin · Algorithms in Finance, Assignment 1 · synthetic teaching data, "
           "not historical exchange records · single venue, sequential, no fees or network delay")

NEEDED = {"timing_raw.csv": "python -m bench.experiments",
          "liquidation_raw.csv": "python -m bench.experiments",
          "concentration_correctness.csv": "python -m bench.experiments",
          "latency_summary.csv": "python -m bench.instrumentation",
          "memory.csv": "python -m bench.instrumentation",
          "operation_counts.csv": "python -m bench.instrumentation"}
missing = [f for f in NEEDED if not (RES / f).exists()]
if missing:
    st.error("Missing result files: " + ", ".join(missing) + ". Create them with: "
             + "; ".join(sorted({NEEDED[f] for f in missing})))
    st.stop()


@st.cache_data
def load(name, **kw):
    return pd.read_csv(RES / name, **kw)


timing = load("timing_raw.csv")
if (RES / "timing_million_raw.csv").exists():
    timing = pd.concat([timing, load("timing_million_raw.csv")], ignore_index=True)
liq = load("liquidation_raw.csv")
conc = load("concentration_correctness.csv")
lat = load("latency_summary.csv")
mem = load("memory.csv")
growth = load("memory_growth.csv")
ops = load("operation_counts.csv")
env_t = json.loads((RES / "timing_environment.json").read_text())
env_i = json.loads((RES / "instrumentation_environment.json").read_text())
COLORS = alt.Scale(domain=["A", "B", "B_nocompact"], range=["#c0504d", "#1f6fb5", "#9bbbd9"])


def medians(df, value="elapsed_s"):
    ok = df[df.status == "ok"]
    return ok.groupby([c for c in df.columns if c in
                       ["experiment", "scenario", "events", "levels", "version", "phase", "fraction"]],
                      as_index=False)[value].median()


def stopped_note(df):
    s = df[df.status == "stopped"]
    if not s.empty:
        cols = [c for c in ["experiment", "scenario", "seed", "events", "levels", "version", "fraction", "note"] if c in s]
        st.warning(f"{len(s)} run(s) stopped at the declared limit of "
                   f"{env_t['time_limit_s_per_run']:g} s per run; no values are shown for them.")
        st.dataframe(s[cols], hide_index=True, width="stretch")


tabs = st.tabs(["Replay scaling", "A vs B", "Large liquidation", "Queue concentration",
                "Cancellation churn", "Latency", "Memory", "Correctness", "Bottleneck",
                "Raw data and settings"])

# ------------------------------------------------------------------ replay scaling
with tabs[0]:
    st.subheader("Full-stream replay time by number of events M (median of 5 repeats)")
    rep = timing[timing.experiment.isin(["replay", "replay_million"])]
    scen = st.selectbox("Workload", sorted(rep.scenario.unique()), key="rs")
    view = medians(rep[rep.scenario == scen])
    eng = view[view.phase == "replay"]
    chart = alt.Chart(eng).mark_line(point=True).encode(
        x=alt.X("events:Q", scale=alt.Scale(type="log"), title="events M (log)"),
        y=alt.Y("elapsed_s:Q", scale=alt.Scale(type="log"), title="replay seconds (log)"),
        color=alt.Color("version:N", scale=COLORS), tooltip=["version", "events", "elapsed_s"])
    st.altair_chart(chart, width="stretch")
    tbl = view.pivot_table(index="events", columns=["phase", "version"], values="elapsed_s")
    st.caption("Seconds per complete run. 'parse' = reading and parsing the gzip JSON Lines file "
               "(same for both versions); 'replay' = engine only, fresh empty book. Application "
               "time = parse + replay.")
    st.dataframe(tbl.style.format("{:.4f}"), width="stretch")
    thr = eng.assign(events_per_s=eng.events / eng.elapsed_s).pivot_table(
        index="events", columns="version", values="events_per_s")
    st.caption("Throughput: events divided by replay seconds.")
    st.dataframe(thr.style.format("{:,.0f}"), width="stretch")
    peaks = rep[rep.scenario == scen].groupby(["events", "seed"], as_index=False)[
        ["peak_active_orders", "peak_price_levels", "end_active_orders"]].first()
    st.caption("Book size: peak active orders B and occupied price levels P (both sides).")
    st.dataframe(peaks, hide_index=True)
    stopped_note(rep[rep.scenario == scen])

# ------------------------------------------------------------------ A vs B
with tabs[1]:
    st.subheader("Original (A) versus revised (B): median replay time ratio A / B")
    r = medians(timing[(timing.experiment == "replay") & (timing.phase == "replay")])
    piv = r.pivot_table(index=["scenario", "events"], columns="version", values="elapsed_s")
    piv["A / B"] = piv["A"] / piv["B"]
    st.dataframe(piv.style.format("{:.4f}"), width="stretch")
    st.markdown("A ratio below 1 means the baseline was faster. **Cancellation churn** is such a "
                "case: with almost no active orders, A's list scan is nearly free while B pays "
                "for dictionary, deque and heap bookkeeping.")

# ------------------------------------------------------------------ liquidation
with tabs[2]:
    st.subheader("One fresh bid book (buildup, seed 42); sale of 10 %, 100 %, 200 % of its bid quantity")
    ok = liq[liq.status != "stopped"]          # status holds the sale status: filled/partial
    g = ok.groupby(["events", "fraction", "version"], as_index=False).agg(
        construction_s=("construction_s", "median"), sale_s=("sale_s", "median"),
        fills=("fill_count", "first"), makers=("makers_touched", "first"),
        levels=("price_levels_visited", "first"), unfilled_units=("unfilled_units", "first"),
        best_bid=("best_bid_ticks", "first"), vwap=("vwap_ticks", "first"),
        worst=("worst_fill_ticks", "first"))
    chart = alt.Chart(g).mark_line(point=True).encode(
        x=alt.X("events:Q", scale=alt.Scale(type="log"), title="events used to build the book (log)"),
        y=alt.Y("sale_s:Q", scale=alt.Scale(type="log"), title="sale seconds (log)"),
        color=alt.Color("version:N", scale=COLORS), strokeDash="fraction:N",
        tooltip=["version", "events", "fraction", "sale_s", "fills"])
    st.altair_chart(chart, width="stretch")
    st.caption("Sale time includes matching, state updates and building the fill list. "
               "Construction (replaying the stream) is measured separately; every repeat uses a "
               "freshly built book.")
    st.dataframe(g[["events", "fraction", "version", "construction_s", "sale_s", "fills", "makers",
                    "levels", "unfilled_units"]], hide_index=True, width="stretch")
    st.markdown("**Extra: price impact of the sale** (from the fills; integers until display)")
    imp = g[g.version == "B"].copy()
    imp["avg_price_usd"] = imp.vwap / 100
    imp["best_bid_usd"] = imp.best_bid / 100
    imp["avg_below_best_usd"] = (imp.best_bid - imp.vwap) / 100
    imp["worst_fill_usd"] = imp.worst / 100
    st.dataframe(imp[["events", "fraction", "best_bid_usd", "avg_price_usd", "avg_below_best_usd",
                      "worst_fill_usd"]], hide_index=True)
    stopped_note(liq)

# ------------------------------------------------------------------ concentration
with tabs[3]:
    st.subheader("Same number of events, 4 versus 1,000 price levels per side (buildup)")
    c = timing[timing.scenario.eq("buildup") & timing.phase.eq("replay") &
               timing.experiment.isin(["replay", "concentration"]) &
               timing.events.isin(timing[timing.experiment == "concentration"].events.unique())]
    cm = medians(c).pivot_table(index=["events", "levels"], columns="version", values="elapsed_s")
    st.dataframe(cm.style.format("{:.4f}"), width="stretch")
    st.caption("Correctness at both concentrations: a full liquidation of the resulting bid book "
               "must fill in price-time order, and A and B must hold identical books.")
    st.dataframe(conc, hide_index=True, width="stretch")
    stopped_note(timing[timing.experiment == "concentration"])

# ------------------------------------------------------------------ churn
with tabs[4]:
    st.subheader("Cancellation churn: one submission, then its cancellation")
    ch = medians(timing[(timing.experiment == "churn") & (timing.phase == "replay")])
    st.dataframe(ch.pivot_table(index="events", columns="version", values="elapsed_s")
                 .style.format("{:.4f}"), width="stretch")
    m = mem[mem.scenario == "cancel_churn"]
    st.caption("Memory after the churn (tracemalloc; input excluded). B_nocompact is version B "
               "with its compaction rules switched off.")
    st.dataframe(m[["version", "events", "active_orders_after", "book_bytes_after_replay",
                    "replay_peak_bytes", "stale_deque_entries", "stale_heap_entries"]],
                 hide_index=True, width="stretch")

# ------------------------------------------------------------------ latency
with tabs[5]:
    st.subheader("Per-event processing latency (separate instrumentation run, microseconds)")
    st.caption(f"Percentiles: {env_i['percentile_convention']}. Engine time only: no queueing or "
               "network delay. Reciprocal throughput is not a latency estimate.")
    sc = st.selectbox("Workload", sorted(lat.scenario.unique()), key="lat")
    v = lat[lat.scenario == sc]
    st.dataframe(v.drop(columns=["scenario"]), hide_index=True, width="stretch")
    raw_path = RES / "latency_raw_10000.csv.gz"
    if raw_path.exists():
        raw = load("latency_raw_10000.csv.gz")
        rv = raw[raw.scenario == sc].assign(latency_us=lambda d: d.latency_ns / 1000)
        st.altair_chart(alt.Chart(rv).mark_point(size=4, opacity=0.4).encode(
            x=alt.X("index:Q", title="event number (book grows from left to right)"),
            y=alt.Y("latency_us:Q", scale=alt.Scale(type="log"), title="latency µs (log)"),
            color=alt.Color("version:N", scale=COLORS)), width="stretch")
    st.dataframe(load("latency_stopped.csv"), hide_index=True)

# ------------------------------------------------------------------ memory
with tabs[6]:
    st.subheader("Traced memory (tracemalloc; separate run)")
    st.caption(env_i["memory_boundary"] + ". Traced Python allocations are neither auxiliary "
               "space alone nor total process memory.")
    st.dataframe(mem, hide_index=True, width="stretch")
    sc = st.selectbox("Workload", sorted(growth.scenario.unique()), key="mem")
    gv = growth[growth.scenario == sc]
    st.altair_chart(alt.Chart(gv).mark_line(point=True).encode(
        x=alt.X("percent_of_events:Q", title="% of events processed"),
        y=alt.Y("traced_bytes:Q", title="traced bytes"),
        color=alt.Color("version:N", scale=COLORS), strokeDash="events:N"), width="stretch")

# ------------------------------------------------------------------ correctness
with tabs[7]:
    st.subheader("Correctness outcomes")
    ev = Path(__file__).resolve().parent / "evidence"
    rows = []
    for f in sorted(ev.glob("*.txt")):
        last = [ln for ln in f.read_text().splitlines() if ln.strip()][-1]
        rows.append({"evidence file": f.name, "pytest summary": last})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown("Liquidation: identical fills from A and B (where A finished within the limit)")
    st.dataframe(load("liquidation_versions_agree.csv"), hide_index=True)
    st.markdown("Queue concentration: price-time order and agreement")
    st.dataframe(conc, hide_index=True)

# ------------------------------------------------------------------ bottleneck
with tabs[8]:
    st.subheader("Bottleneck explained with operation counts")
    st.markdown(
        "Version A keeps all orders in one list. Every LIMIT event first checks that its "
        "identifier is not already live (`_find`, one scan) and then looks for the best opposite "
        "order (`_best`, another scan), so each event costs about 2B list reads for B active "
        "orders. A stream that only adds orders therefore costs about M² list reads in total. "
        "Version B answers both questions with a dictionary lookup and the top of a heap.")
    oc = ops.pivot_table(index=["scenario", "events", "operation"], columns="version", values="count")
    st.dataframe(oc.style.format("{:,.0f}"), width="stretch")

# ------------------------------------------------------------------ raw data
with tabs[9]:
    for name, df in [("timing_raw.csv", timing), ("liquidation_raw.csv", liq)]:
        with st.expander(name + " (one row per raw repeat)"):
            st.dataframe(df, hide_index=True, width="stretch")
    with st.expander("timing_environment.json"):
        st.json(env_t)
    with st.expander("instrumentation_environment.json"):
        st.json(env_i)
