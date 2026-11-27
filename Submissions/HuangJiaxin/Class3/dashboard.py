"""Dashboard for the Class 3 lab. Reads the saved results only; it never reruns pricing.

    streamlit run Submissions/HuangJiaxin/Class3/dashboard.py

Pages: overview, runtime, memory, Bitcoin (boundary and exercise), all 40 assets,
predictions vs results, correctness. Units: prices in USDT per unit of the asset,
time in seconds, memory in megabytes (1 MB = 10^6 bytes) of peak traced allocations.
"""
import json
import math
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
MAX_POINTS = 4000                      # chart points per line (every k-th hour is drawn)

st.set_page_config(page_title="Class 3: PriceAmericanPut", layout="wide")

def metric(col, label, value, note=None):
    """A number with an optional grey note below it (no arrow: the note is not a change)."""
    col.metric(label, value)
    if note:
        col.caption(note)



@st.cache_data
def load():
    d = {"runs": pd.read_csv(RES / "runs.csv"),
         "btc": pd.read_csv(RES / "bitcoin.csv"),
         "a1": pd.read_csv(RES / "assets_1y.csv"),
         "a5": pd.read_csv(RES / "assets_5y.csv"),
         "mem": pd.read_csv(RES / "memory_full_tree.csv"),
         "env": json.loads((RES / "environment.json").read_text())}
    for lab in ("1y", "5y"):
        b = pd.read_csv(RES / f"btc_{lab}_boundary.csv", parse_dates=["timestamp_utc"])
        d[f"b{lab}"] = b
    return d


d = load()
runs, env = d["runs"], d["env"]
med = runs.groupby(["run", "version"], as_index=False).agg(
    N=("N", "first"), assets=("assets", "first"), repeats=("seconds", "size"),
    seconds=("seconds", "median"), peak_mb=("peak_traced_bytes", "max"))
med["peak_mb"] = med["peak_mb"] / 1e6


def peak(run, version):
    r = med[(med.run == run) & (med.version == version)]
    return float(r.peak_mb.iloc[0]) if len(r) else float("nan")


def sec(run, version):
    r = med[(med.run == run) & (med.version == version)]
    return float(r.seconds.iloc[0]) if len(r) else float("nan")


st.title("PriceAmericanPut on hourly market data")
st.caption(f"Jiaxin Huang, Class 3 lab. Measured on {env['platform']}, Python "
           f"{env['python'].split()[0]}, numpy {env['numpy']}, code {env['code_commit']}, "
           f"{env['timestamp_utc']} UTC. All numbers are read from `results/`.")

tabs = st.tabs(["Overview", "Runtime", "Memory", "Bitcoin", "All 40 assets",
                "Predictions vs results", "Correctness"])

# ------------------------------------------------------------------ overview
with tabs[0]:
    b1, b5 = d["btc"].iloc[0], d["btc"].iloc[1]
    c = st.columns(4)
    metric(c[0], "Bitcoin put, one year", f"{b1.american_value:,.0f} USDT",
           f"{b1.american_pct_of_S0:.1f} % of S0")
    metric(c[1], "Early-exercise premium, one year", f"{b1.early_exercise_premium:,.0f} USDT",
           f"{b1.premium_pct_of_american:.1f} % of the value")
    metric(c[2], "numpy vs plain Python, five years",
           f"{sec('bitcoin_5y', 'plain') / sec('bitcoin_5y', 'numpy'):.0f} × faster",
           "same prices, measured on Bitcoin")
    mem4000 = d["mem"][d["mem"].N == 4000].set_index("version").peak_traced_bytes
    metric(c[3], "Full tree at N = 4,000", f"{mem4000['full_tree'] / 1e6:,.0f} MB",
           f"two arrays: {mem4000['two_arrays_numpy'] / 1e6:.2f} MB")
    st.markdown(
        "**Contract**: American put written at the first hourly close and expiring at the "
        "last, strike = first close (at the money), exercisable every hour. **Tree**: one "
        "period per hour, u = e^s with s the sample standard deviation of hourly log "
        "returns, d = 1/u, interest 4 % a year. **Windows**: one year (N = 8,760 periods) and "
        "the whole file (N = 43,822).")
    st.markdown(f"**Exercise rule**: {env['exercise_rule']}. "
                f"**First exercise on the real path**: {env['first_exercise_rule']}.")

# ------------------------------------------------------------------ runtime
with tabs[1]:
    st.subheader("Seconds per run (task 6)")
    show = med.copy()
    show["seconds"] = show.seconds.round(3)
    show["peak_mb"] = show.peak_mb.round(2)
    st.dataframe(show.rename(columns={"peak_mb": "peak traced MB", "repeats": "timed runs"}),
                 hide_index=True, width="stretch")
    st.caption("Single-asset numpy runs: one warm-up, median of three repeats. Plain Python "
               "and the 40-asset runs: timed once. Reading the CSV files is not included "
               "(about 2 s for 40 files). The 40-asset runs price the American and the "
               "European put of every asset. Empty memory: not traced (plain Python, five years).")
    rows = []
    for version, r1, r5 in (("plain Python", ("bitcoin_1y", "plain"), ("bitcoin_5y", "plain")),
                            ("numpy", ("bitcoin_1y", "numpy"), ("bitcoin_5y", "numpy")),
                            ("numpy, 40 assets", ("assets_1y", "numpy"), ("assets_5y", "numpy"))):
        rows.append({"version": version, "one year (s)": round(sec(*r1), 3),
                     "five years (s)": round(sec(*r5), 3),
                     "growth": round(sec(*r5) / sec(*r1), 1), "Θ(N²) predicts": 25.0})
    st.subheader("Growth from one to five years (N × 5.00)")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    # cost model a·N + b·N²/2 fitted to the two Bitcoin numpy runs
    n1, n5 = 8760, 43822
    t1, t5 = sec("bitcoin_1y", "numpy"), sec("bitcoin_5y", "numpy")
    k1, k5 = (n1 + 1) * (n1 + 2) / 2, (n5 + 1) * (n5 + 2) / 2
    b = (t5 - t1 * n5 / n1) / (k5 - k1 * n5 / n1)
    a = (t1 - b * k1) / n1
    st.markdown(
        f"**Why numpy grows less than 25 times**: fitting time = a·N + b·(nodes) to the two "
        f"Bitcoin runs gives a fixed cost a ≈ {a * 1e6:.1f} µs per date and b ≈ {b * 1e9:.1f} ns "
        f"per node. The fixed part is {100 * a * n1 / t1:.0f} % of the one-year time but only "
        f"{100 * a * n5 / t5:.0f} % of the five-year time. Plain Python costs about "
        f"{1e9 * sec('bitcoin_1y', 'plain') / k1:.0f} ns per node at one year and "
        f"{1e9 * sec('bitcoin_5y', 'plain') / k5:.0f} ns at five years.")
    bars = pd.DataFrame([{"window": w, "version": v, "seconds": sec(f"bitcoin_{w}", k)}
                         for w in ("1y", "5y") for v, k in (("plain Python", "plain"), ("numpy", "numpy"))])
    st.altair_chart(alt.Chart(bars).mark_bar().encode(
        x=alt.X("version:N", title=None), y=alt.Y("seconds:Q", title="seconds (log scale)",
                                                   scale=alt.Scale(type="log")),
        color=alt.Color("version:N", legend=None), column=alt.Column("window:N", title="Bitcoin window"),
        tooltip=["window", "version", alt.Tooltip("seconds:Q", format=".3f")]).properties(width=220, height=260))

# ------------------------------------------------------------------ memory
with tabs[2]:
    st.subheader("Full tree vs two arrays (extra 2)")
    m = d["mem"].copy()
    m["MB"] = m.peak_traced_bytes / 1e6
    st.altair_chart(alt.Chart(m).mark_line(point=True).encode(
        x=alt.X("N:Q", scale=alt.Scale(type="log", base=2), title="N (periods, log scale)"),
        y=alt.Y("MB:Q", scale=alt.Scale(type="log"), title="peak traced MB (log scale)"),
        color=alt.Color("version:N", title=None),
        tooltip=["version", "N", "tree_nodes", alt.Tooltip("MB:Q", format=",.3f"),
                 alt.Tooltip("seconds:Q", format=".3f")]).properties(height=340), width="stretch")
    ft = m[m.version == "full_tree"].reset_index(drop=True)
    ft["factor vs previous N"] = (ft.MB / ft.MB.shift()).round(2)
    ft["bytes per node"] = (ft.peak_traced_bytes / ft.tree_nodes).round(1)
    st.dataframe(ft[["N", "tree_nodes", "MB", "factor vs previous N", "bytes per node", "seconds"]]
                 .round({"MB": 1, "seconds": 3}), hide_index=True, width="stretch")
    per_node = float(ft["bytes per node"].iloc[-1])
    proj = pd.DataFrame([{"window": w, "N": n, "nodes": (n + 1) * (n + 2) // 2} for w, n in
                         (("one year", 8760), ("five years", 43822))])
    proj["full tree, Python lists (GB)"] = (proj.nodes * per_node / 1e9).round(1)
    proj["full tree, two float64 arrays (GB)"] = (proj.nodes * 16 / 1e9).round(1)
    st.markdown("**Projection, not measured** (these runs were not attempted):")
    st.dataframe(proj, hide_index=True, width="stretch")
    st.subheader("Two arrays on the real data")
    st.dataframe(med[med.peak_mb.notna()][["run", "version", "N", "assets", "peak_mb"]]
                 .rename(columns={"peak_mb": "peak traced MB"}).round(2),
                 hide_index=True, width="stretch")
    st.caption("tracemalloc in a separate run: Python objects and numpy buffers created during "
               "the call. Not included: input prices already in memory, the interpreter, native "
               "stacks. Not total process memory.")

# ------------------------------------------------------------------ bitcoin
with tabs[3]:
    lab = st.radio("Window", ["1y", "5y"], horizontal=True,
                   format_func=lambda x: {"1y": "Last year", "5y": "Five years"}[x])
    row = d["btc"].iloc[0 if lab == "1y" else 1]
    b = d[f"b{lab}"]
    k = max(1, math.ceil(len(b) / MAX_POINTS))
    view = b.iloc[::k]
    long = view.melt(id_vars=["timestamp_utc"], value_vars=["price", "boundary"],
                     var_name="series", value_name="USDT").dropna()
    lines = alt.Chart(long).mark_line(strokeWidth=1.2).encode(
        x=alt.X("timestamp_utc:T", title=None), y=alt.Y("USDT:Q", title="USDT per BTC"),
        color=alt.Color("series:N", scale=alt.Scale(domain=["price", "boundary"],
                                                     range=["#1f4e79", "#c0504d"]), title=None))
    strike = alt.Chart(pd.DataFrame({"K": [row.S0_K]})).mark_rule(strokeDash=[4, 4], color="grey").encode(y="K:Q")
    layers = lines + strike
    if bool(row.exercised):
        pt = pd.DataFrame({"timestamp_utc": [pd.Timestamp(row.exercise_time)], "USDT": [row.exercise_price]})
        layers += alt.Chart(pt).mark_point(size=120, filled=True, color="black").encode(
            x="timestamp_utc:T", y="USDT:Q", tooltip=["timestamp_utc:T", alt.Tooltip("USDT:Q", format=",.2f")])
    st.altair_chart(layers.properties(height=380), width="stretch")
    st.caption(f"Every {k}-th hour is drawn ({len(view):,} of {len(b):,} points); the exercise "
               f"point is exact. Dashed line: strike K = P0. The boundary zig-zags by one tree "
               f"step between hours; compared every second hour it never decreases.")
    c = st.columns(4)
    c[0].metric("American put", f"{row.american_value:,.2f}")
    c[1].metric("European put", f"{row.european_value:,.2f}")
    metric(c[2], "Early-exercise premium", f"{row.early_exercise_premium:,.2f}",
           f"{row.premium_pct_of_american:.1f} % of the American value")
    metric(c[3], "First exercise", str(row.exercise_time)[:16].replace("T", " ") if bool(row.exercised) else "never",
           f"payoff {row.exercise_payoff:,.2f}" if bool(row.exercised) else None)
    st.image(str(RES / f"btc_{lab}_boundary.png"),
             caption="Static figure from plot_btc.py (all hours drawn)")

# ------------------------------------------------------------------ all assets
with tabs[4]:
    lab = st.radio("Window ", ["1y", "5y"], horizontal=True,
                   format_func=lambda x: {"1y": "Last year", "5y": "Five years"}[x])
    a = d["a1" if lab == "1y" else "a5"].copy()
    a["asset"] = a.symbol.str.replace("USDT", "", regex=False)
    c = st.columns(3)
    c[0].metric("Exercised early", f"{int(a.exercised.sum())} of {len(a)}")
    c[1].metric("Median put value", f"{a.american_pct_of_S0.median():.1f} % of S0")
    c[2].metric("Median premium", f"{a.premium_pct_of_american.median():.1f} % of the value")
    st.altair_chart(alt.Chart(a).mark_circle(size=90).encode(
        x=alt.X("s_hourly:Q", title="hourly volatility s", axis=alt.Axis(format="%")),
        y=alt.Y("premium_pct_of_american:Q", title="early-exercise premium, % of American value"),
        color=alt.Color("exercised:N", title="exercised early"),
        tooltip=["asset", alt.Tooltip("s_hourly:Q", format=".3%"),
                 alt.Tooltip("american_pct_of_S0:Q", format=".1f", title="value % of S0"),
                 alt.Tooltip("premium_pct_of_american:Q", format=".2f", title="premium %"),
                 "exercise_time"]).properties(height=340), width="stretch")
    st.caption("Calmer assets have a larger premium share: for a volatile asset most of the "
               "put's value is the chance of a large fall, which the European put has too.")
    cols = ["asset", "N", "S0_K", "P_N", "s_hourly", "american_value", "american_pct_of_S0",
            "european_value", "premium_pct_of_american", "exercised", "exercise_time", "exercise_payoff"]
    st.dataframe(a[cols].sort_values("premium_pct_of_american", ascending=False),
                 hide_index=True, width="stretch")

# ------------------------------------------------------------------ predictions
with tabs[5]:
    st.markdown("Predictions written and committed **before** the measurements (`PREDICTIONS.md`).")
    p = pd.DataFrame([
        ["1", "Five years take about 25× as long",
         f"plain × {sec('bitcoin_5y', 'plain') / sec('bitcoin_1y', 'plain'):.1f}, "
         f"numpy × {sec('bitcoin_5y', 'numpy') / sec('bitcoin_1y', 'numpy'):.1f}",
         "right for plain Python; numpy lower (fixed cost per date)"],
        ["2", "numpy is tens of times faster",
         f"{sec('bitcoin_1y', 'plain') / sec('bitcoin_1y', 'numpy'):.0f}× to "
         f"{sec('bitcoin_5y', 'plain') / sec('bitcoin_5y', 'numpy'):.0f}×", "correct"],
        ["3", "Two arrays fit easily in 3 GB",
         f"{peak('bitcoin_5y', 'numpy'):.1f} MB (Bitcoin), {peak('assets_5y', 'numpy'):.1f} MB (40 assets)",
         "correct"],
        ["4", "Full tree: × 4 per doubling of N",
         f"× {ft['factor vs previous N'].min():.2f} to × {ft['factor vs previous N'].max():.2f}", "correct"],
        ["5", "Premium about one third of the value or more",
         f"Bitcoin {d['btc'].premium_pct_of_american.iloc[0]:.1f} % (1y), "
         f"{d['btc'].premium_pct_of_american.iloc[1]:.1f} % (5y)",
         "wrong: low interest (4 % a year) makes early exercise worth little"],
        ["6", "The Bitcoin holder exercises early",
         f"yes, {str(d['btc'].exercise_time.iloc[0])[:10]}, payoff {d['btc'].exercise_payoff.iloc[0]:,.0f}",
         "correct"]], columns=["#", "My prediction", "Measured", "Verdict"])
    st.dataframe(p, hide_index=True, width="stretch")

# ------------------------------------------------------------------ correctness
with tabs[6]:
    def last_line(name):
        f = HERE / "evidence" / name
        return f.read_text().strip().splitlines()[-1] if f.exists() else "missing"
    st.dataframe(pd.DataFrame([
        ["Tests on stubs, before the implementation", last_line("step3_tests_before_implementation.txt")],
        ["Tests after the implementation", last_line("step4_tests_after_implementation.txt")],
        ["Final tests (with my hand trace)", last_line("final_tests.txt")],
        ["Slide example (two periods)", "1175/147 = 7.9932 exactly, all three versions"],
        ["My hand trace (three periods, TRACE.md)", "23.2; boundary none, 50, 25, 50; matches all versions"],
        ["Exact reference (fractions, every node)", "agrees on 40 random small trees, value and boundary"],
        ["Course code (Class3/class3_evidence.py)", "same one-year values for BTC, PAXG, SNX (relative difference < 2e-14)"],
        ["Sanity of saved results", "European ≤ American < K, payoff = K − price at exercise, 0 < q < 1 for all 80 runs"],
    ], columns=["Check", "Outcome"]), hide_index=True, width="stretch")
