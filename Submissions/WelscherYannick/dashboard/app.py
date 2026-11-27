"""Search Lab dashboard: the saved timing and memory measurements (slide 63).

Run from Submissions/WelscherYannick:

    .venv/bin/streamlit run dashboard/app.py

Opens on http://localhost:8501. The dashboard only reads results/; it never
runs a benchmark. To refresh the numbers, rerun bench/benchmark.py and
bench/memory.py.
"""

import html
import json
import math

import plotly.graph_objects as go
import streamlit as st

import data as D
import theme as T

st.set_page_config(page_title="Search Lab", page_icon="◐", layout="wide")
st.markdown(T.CSS, unsafe_allow_html=True)

METHODS = ["linear", "binary", "hash"]
HIT_LABELS = {1.0: "All present", 0.5: "Mixed", 0.0: "All absent"}
METRIC_LABELS = {"prepare_s": "Preparation", "query_batch_s": "Query batch", "total_s": "Total"}
PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


@st.cache_data
def load():
    timing, memory = D.load_timing(), D.load_memory()
    tsum = D.timing_summary(timing)
    return {
        "timing": timing, "memory": memory,
        "tmeta": D.load_metadata("timing"), "mmeta": D.load_metadata("memory"),
        "tsum": tsum, "msum": D.memory_summary(memory), "ratios": D.revision_ratios(tsum),
    }


R = load()
tsum, msum, ratios, tmeta, mmeta = R["tsum"], R["msum"], R["ratios"], R["tmeta"], R["mmeta"]
H = D.headline(tsum, msum, ratios)
esc = html.escape


def card(key):
    return st.container(key=f"card-{key}")


def card_header(title, sub=None):
    st.markdown(f"<div class='card-title'>{esc(title)}</div>"
                + (f"<div class='card-sub'>{sub}</div>" if sub else ""), unsafe_allow_html=True)


def show(fig, height=320):
    fig.update_layout(template=T.TEMPLATE, height=height)
    st.plotly_chart(fig, theme=None, config=PLOT_CONFIG)


# --- Hero -----------------------------------------------------------------------
m = tmeta["machine"]
chips = [
    f"<span class='chip'><b>{esc(m.get('cpu_brand') or m['machine'])}</b> · {esc(m.get('model') or '')}</span>",
    f"<span class='chip'>Python <b>{esc(tmeta['python_version'].split()[0])}</b></span>",
    f"<span class='chip'>timing @ <code>{esc(tmeta['code']['git_commit'][:7])}</code></span>",
    f"<span class='chip'>memory @ <code>{esc(mmeta['code']['git_commit'][:7])}</code></span>",
]
st.markdown(
    "<div class='hero'><div><h1>Search Lab</h1>"
    "<div class='sub'>Linear search, binary search and hash-set membership: runtime and memory, "
    "original (v1) against two revisions (v2, v3)</div></div>"
    f"<div class='chips'>{''.join(chips)}</div></div>",
    unsafe_allow_html=True,
)

# --- KPI tiles ------------------------------------------------------------------
f1, f100 = H["fastest_q1"], H["fastest_q100"]
ALL_VERSIONS = H["versions"]
def gain_tile(label, gain, accent):
    lo, hi, count, median, faster = gain
    return (label, f"{median:.0%} faster",
            f"median binary query batch · faster in {faster} of {count} scenarios · range {lo:+.0%} to {hi:+.0%}",
            accent)


step_tiles = [gain_tile(f"Revision {s.replace('/', ' vs ')}", g, T.METHOD_COLORS["binary"])
              for s, g in H["steps"].items()]
tiles = step_tiles + [
    gain_tile(f"{ALL_VERSIONS[-1]} vs {ALL_VERSIONS[0]} overall", H["overall"], T.TINTS["binary"]),
    ("Measurement noise", f"±{H['noise']:.1%}",
     "largest query-batch gap between versions for identical code (linear, hash)", T.INK_3),
    ("Fastest with 1 query", T.METHOD_LABELS[f1[0]],
     f"lowest total time in {f1[1]} of {f1[2]} scenarios", T.METHOD_COLORS[f1[0]]),
    ("Fastest with 100 queries", T.METHOD_LABELS[f100[0]],
     f"lowest total time in {f100[1]} of {f100[2]} scenarios", T.METHOD_COLORS[f100[0]]),
    ("Memory price of hashing", f"{H['hash_vs_sorted']:.1f}×",
     f"hash set vs sorted copy at n = {H['n_max']:,}", T.METHOD_COLORS["hash"]),
]
st.markdown(
    "<div class='kpis'>" + "".join(
        f"<div class='kpi' style='--accent:{accent}'><div class='label'>{esc(label)}</div>"
        f"<div class='value'>{esc(value)}</div><div class='note'>{esc(note)}</div></div>"
        for label, value, note, accent in tiles
    ) + "</div>",
    unsafe_allow_html=True,
)

# --- Filters (one row, above all views) -------------------------------------------
with card("filters"):
    c1, c2, c3, c4 = st.columns([1.1, 1.6, 1.1, 1.0])
    q = c1.segmented_control("Queries q", [1, 100], default=100, required=True, key="q")
    hit_options = [1.0, 0.0] if q == 1 else [1.0, 0.5, 0.0]
    hit = c2.segmented_control("Hit rate", hit_options, default=hit_options[-2] if q != 1 else 1.0,
                               format_func=lambda h: HIT_LABELS[h], required=True, key=f"hit_{q}")
    versions = c3.segmented_control("Versions", ALL_VERSIONS, selection_mode="multi",
                                    default=ALL_VERSIONS, key="versions") or [ALL_VERSIONS[-1]]
    scale = c4.segmented_control("Time axis", ["Log", "Linear"], default="Log", required=True, key="scale")

sel = tsum[(tsum["q"] == q) & (tsum["hit_rate_target"] == hit)]
actual_hit = sel["hit_rate_actual"].iloc[0]
st.markdown(
    f"<div class='context'><b>q = {q}</b> {'query' if q == 1 else 'queries'} · "
    f"hit rate <b>{actual_hit:.2f}</b> (generated) · duplicate rate <b>{sel['duplicate_rate'].iloc[0]:.2f}</b> · "
    f"times in <b>seconds per call</b>, query = whole batch of q · "
    f"markers = median of {tmeta['config']['repeats']} repeats, whiskers = min–max</div>",
    unsafe_allow_html=True,
)


def legend_html(methods, versions):
    items = [f"<span><span class='dot' style='background:{T.METHOD_COLORS[mm]}'></span>{T.METHOD_LABELS[mm]}</span>"
             for mm in methods]
    if len(versions) > 1:
        items += [f"<span><span class='sw {T.VERSION_DASH[v]}' style='border-color:{T.INK_2}'></span>"
                  f"{T.VERSION_LABELS[v]}</span>" for v in sorted(versions, reverse=True)]
    return "<div class='legend'>" + "".join(items) + "</div>"


def time_chart(metric, methods=METHODS, label_end=True, decade_ticks=True):
    fig = go.Figure()
    for method in methods:
        color = T.METHOD_COLORS[method]
        for v in sorted(versions):
            d = sel[(sel["method"] == method) & (sel["version"] == v)].sort_values("n")
            if d.empty:
                continue
            med, lo, hi = d[f"{metric}_median"], d[f"{metric}_min"], d[f"{metric}_max"]
            labelled = label_end and v == max(versions)
            text = [""] * (len(d) - 1) + [T.METHOD_LABELS[method].split()[0]] if labelled else None
            custom = [[T.METHOD_LABELS[method], v, f"{n:,}", D.fmt_seconds(a), D.fmt_seconds(b), D.fmt_seconds(c)]
                      for n, a, b, c in zip(d["n"], med, lo, hi)]
            fig.add_trace(go.Scatter(
                x=d["n"], y=med, mode="lines+markers" + ("+text" if text else ""),
                line=dict(color=color, width=2, dash=T.VERSION_DASH[v]),
                marker=dict(size=8, color=color, line=dict(color=T.SURFACE, width=2)),
                error_y=dict(type="data", symmetric=False, array=hi - med, arrayminus=med - lo,
                             color=color, thickness=1, width=0),
                text=text, textposition="middle right", textfont=dict(color=T.INK_2, size=11),
                customdata=custom, cliponaxis=False,
                hovertemplate="<b>%{customdata[0]} · %{customdata[1]}</b><br>n = %{customdata[2]}"
                              "<br>median %{customdata[3]}<br>range %{customdata[4]} – %{customdata[5]}<extra></extra>",
            ))
    fig.update_xaxes(type="log", tickvals=[1_000, 10_000, 100_000], ticktext=["1k", "10k", "100k"],
                     range=[math.log10(700), math.log10(260_000)], title_text="array length n")
    fig.update_yaxes(type="log" if scale == "Log" else "linear", tickformat="~s", ticksuffix="s",
                     dtick=1 if scale == "Log" and decade_ticks else None,
                     rangemode="tozero" if scale == "Linear" else None)
    fig.update_layout(hovermode="closest")
    return fig


tab_time, tab_rev, tab_mem, tab_raw, tab_env = st.tabs(
    ["Runtime", "Revisions", "Memory", "Raw data", "Environment"])

# --- Runtime ----------------------------------------------------------------------
with tab_time:
    st.markdown(legend_html(METHODS, versions), unsafe_allow_html=True)
    cols = st.columns(3)
    subs = {
        "prepare_s": "copying (linear), sorting a copy (binary) or building the set (hash)",
        "query_batch_s": f"all {q} {'query' if q == 1 else 'queries'} on a prepared state",
        "total_s": "preparation and query batch, timed together",
    }
    for col, metric in zip(cols, METRIC_LABELS):
        with col, card(f"time-{metric}"):
            card_header(METRIC_LABELS[metric], subs[metric])
            show(time_chart(metric), height=330)

# --- Revision ---------------------------------------------------------------------
with tab_rev:
    left, right = st.columns([1.35, 1])
    with left, card("ratios"):
        base = ALL_VERSIONS[0]
        card_header(f"Binary search: query-batch time relative to {base}",
                    f"each row runs from {base} (= 1) through the revisions · below 1 = faster · "
                    "grey band = noise seen for identical code")
        rel = D.relative_to_first(tsum)
        rel = rel[rel["method"] == "binary"].sort_values(["n", "q", "hit_rate_target"])
        later = ALL_VERSIONS[1:]
        first = rel[rel["version"] == later[0]]
        labels = [f"n={n:,} · q={qq} · {HIT_LABELS[h].lower()}" for n, qq, h in
                  zip(first["n"], first["q"], first["hit_rate_target"])]
        noise = H["noise"]
        fig = go.Figure()
        fig.add_vrect(x0=1 - noise, x1=1 + noise, fillcolor=T.NEUTRAL_BAND, line_width=0, layer="below")
        fig.add_vline(x=1.0, line=dict(color=T.INK_3, width=1))
        last = rel[rel["version"] == later[-1]]["query_batch_s_ratio"].tolist()
        for y, x in zip(labels, last):
            fig.add_shape(type="line", x0=1.0, x1=x, y0=y, y1=y, line=dict(color=T.METHOD_COLORS["binary"], width=2))
        for v in later:
            rv = rel[rel["version"] == v]
            fig.add_trace(go.Scatter(
                x=rv["query_batch_s_ratio"], y=labels, mode="markers", name=T.VERSION_LABELS[v],
                marker=dict(size=11, symbol=T.VERSION_SYMBOL[v], color=T.VERSION_MARKER[v],
                            line=dict(color=T.SURFACE, width=2)),
                customdata=[[v, f"{1 - r:.1%}"] for r in rv["query_batch_s_ratio"]],
                hovertemplate=f"<b>%{{y}}</b><br>%{{customdata[0]}}/{base} = %{{x:.3f}}"
                              "<br>%{customdata[1]} faster<extra></extra>",
            ))
        fig.update_xaxes(range=[0.7, 1.1], tickformat=".2f", title_text=f"version / {base} (median)")
        fig.update_yaxes(autorange="reversed", tickfont=dict(size=11, color=T.INK_2))
        st.markdown("<div class='legend'>" + "".join(
            f"<span><span class='dot' style='background:{T.VERSION_MARKER[v]};"
            f"border-radius:{'50%' if T.VERSION_SYMBOL[v] == 'circle' else '2px'};"
            f"{'transform:rotate(45deg);' if T.VERSION_SYMBOL[v] == 'diamond' else ''}'></span>"
            f"{T.VERSION_LABELS[v]}</span>" for v in later) + "</div>", unsafe_allow_html=True)
        show(fig, height=470)
    with right:
        with card("rev-line"):
            card_header("Binary search query batch", f"selected scenario: q = {q}, {HIT_LABELS[hit].lower()}")
            st.markdown(legend_html(["binary"], versions), unsafe_allow_html=True)
            show(time_chart("query_batch_s", methods=["binary"], label_end=False, decade_ticks=False), height=250)
        with card("rev-note"):
            card_header("What changed")
            st.markdown(
                "<div class='note-text'><b>v1 → v2:</b> the recursive search becomes a <code>while</code> "
                "loop over the same half-open range <code>[lo, hi)</code>; this removes the Python function "
                "calls. <b>v2 → v3:</b> one comparison per step instead of two: the loop only asks "
                "<code>s[mid] &lt; q</code> and finds the first position with a value ≥ q, then checks "
                "once for equality. No early exit on a hit, but every step is cheaper, most visibly for "
                "absent ids. Sorting is shared by all versions, so the <b>total</b> time barely moves.</div>",
                unsafe_allow_html=True,
            )

# --- Memory -----------------------------------------------------------------------
KIB_TICKS = [2 ** k for k in range(10, 24, 2)]


def kib_label(b):
    return f"{b // 1024 ** 2} MiB" if b >= 1024 ** 2 else f"{b // 1024} KiB"


def memory_bars(column, methods, title, sub):
    d = msum[(msum["q"] == q) & (msum["hit_rate_target"] == hit) & (msum["version"] == ALL_VERSIONS[-1])]
    fig = go.Figure()
    for method in methods:
        dm = d[d["method"] == method].sort_values("n")
        fig.add_trace(go.Bar(
            x=[f"{n:,}" for n in dm["n"]], y=dm[column], name=T.METHOD_LABELS[method],
            marker=dict(color=T.METHOD_COLORS[method], cornerradius=4, line=dict(color=T.SURFACE, width=2)),
            customdata=[[T.METHOD_LABELS[method], D.fmt_bytes(b), f"{int(b):,}"] for b in dm[column]],
            hovertemplate="<b>%{customdata[0]}</b><br>n = %{x}<br>%{customdata[1]} (%{customdata[2]} B)<extra></extra>",
        ))
    fig.update_yaxes(type="log", tickvals=KIB_TICKS, ticktext=[kib_label(t) for t in KIB_TICKS])
    fig.update_xaxes(type="category", title_text="array length n")
    fig.update_layout(barmode="group", bargap=0.28, bargroupgap=0.06)
    card_header(title, sub)
    show(fig, height=300)


with tab_mem:
    st.markdown(legend_html(METHODS, [ALL_VERSIONS[-1]]), unsafe_allow_html=True)
    a, b = st.columns(2)
    with a, card("mem-prep"):
        memory_bars("prepare_current_B", METHODS, "Prepared structure",
                    f"held after prepare ({ALL_VERSIONS[-1]}): tuple copy, sorted copy, hash set")
    with b, card("mem-peak"):
        memory_bars("total_peak_B", METHODS, "Peak during prepare + query",
                    f"includes temporaries such as sort buffers and set resizes ({ALL_VERSIONS[-1]})")

    with card("mem-table"):
        card_header("Memory measurements", f"q = {q}, {HIT_LABELS[hit].lower()} · medians over "
                    f"{mmeta['config']['memory_repeats']} identical repeats · tracemalloc, bytes")
        t = msum[(msum["q"] == q) & (msum["hit_rate_target"] == hit) & (msum["version"].isin(versions))]
        t = t.sort_values(["n", "method", "version"])
        table = {
            "n": [f"{n:,}" for n in t["n"]],
            "method": [T.METHOD_LABELS[x] for x in t["method"]],
            "version": t["version"].tolist(),
        }
        for col, name in [("prepare_current_B", "prepare current"), ("prepare_peak_B", "prepare peak"),
                          ("query_current_B", "query current (output)"), ("query_peak_B", "query peak"),
                          ("total_peak_B", "total peak")]:
            table[name] = [D.fmt_bytes(x) for x in t[col]]
        st.dataframe(table, hide_index=True)
        meas = mmeta["measurement"]
        st.markdown(
            "<div class='note-text'>Not included: the given input "
            f"(<code>input_included = {str(meas['input_included']).lower()}</code>), interpreter overhead, "
            "native allocations and call-stack frames. The recursion of v1 shows up only through the int "
            "objects its pending calls keep alive: a few hundred bytes more in the binary query peak.</div>",
            unsafe_allow_html=True,
        )

# --- Raw data ---------------------------------------------------------------------
with tab_raw:
    with card("raw-timing"):
        card_header("Timing: every repeat", f"q = {q}, {HIT_LABELS[hit].lower()} · seconds per call")
        rt = R["timing"]
        st.dataframe(rt[(rt["q"] == q) & (rt["hit_rate_target"] == hit) & (rt["version"].isin(versions))],
                     hide_index=True, height=320,
                     column_config={c: st.column_config.NumberColumn(format="%.4e") for c in D.TIME_COLUMNS})
        st.download_button("Download timing_raw.csv (all scenarios)", rt.to_csv(index=False),
                           file_name="timing_raw.csv", mime="text/csv")
    with card("raw-memory"):
        card_header("Memory: every repeat", f"q = {q}, {HIT_LABELS[hit].lower()} · bytes")
        rm = R["memory"]
        st.dataframe(rm[(rm["q"] == q) & (rm["hit_rate_target"] == hit) & (rm["version"].isin(versions))],
                     hide_index=True, height=320)
        st.download_button("Download memory_raw.csv (all scenarios)", rm.to_csv(index=False),
                           file_name="memory_raw.csv", mime="text/csv")

# --- Environment ------------------------------------------------------------------
def kv_block(meta):
    mc, cfg = meta["machine"], meta["config"]
    rows = [
        ("measured (UTC)", meta["created_utc"]),
        ("git commit", meta["code"]["git_commit"]),
        ("uncommitted changes", meta["code"]["uncommitted_changes_in_src_or_bench"]),
        ("python", meta["python_version"].split()[0] + " · " + meta["python_implementation"]),
        ("platform", mc["platform"]),
        ("machine", f"{mc.get('cpu_brand') or mc['machine']} · {mc.get('model') or ''} · {mc['cpu_count']} cores"),
        ("memory", f"{mc['memory_bytes'] / 1024 ** 3:.0f} GiB" if mc.get("memory_bytes") else "n/a"),
        ("clock", f"{meta['clock']['implementation']} · resolution {D.fmt_seconds(meta['clock']['resolution_s'])}"),
    ]
    if "loop_overhead_s_per_call" in meta.get("measurement", {}):
        rows.append(("loop overhead", D.fmt_seconds(meta["measurement"]["loop_overhead_s_per_call"]) + " per call"))
    rows += [("seed", cfg["seed"]), ("duplicate rate", cfg["duplicate_rate"]),
             ("repeats", cfg.get("memory_repeats", cfg["repeats"]))]
    return "<div class='kv'>" + "".join(
        f"<div class='k'>{esc(k)}</div><div class='v'>{esc(str(v))}</div>" for k, v in rows) + "</div>"


with tab_env:
    a, b = st.columns(2)
    with a, card("env-timing"):
        card_header("Timing run", "bench/benchmark.py")
        st.markdown(kv_block(tmeta), unsafe_allow_html=True)
    with b, card("env-memory"):
        card_header("Memory run", "bench/memory.py")
        st.markdown(kv_block(mmeta), unsafe_allow_html=True)
    with card("env-scenarios"):
        card_header("Generated data per scenario", esc(tmeta["generator"]["hit_policy"]))
        keep = ["scenario", "n", "q", "hit_rate", "hit_rate_actual", "n_unique", "hits", "duplicate_rate", "seed"]
        st.dataframe([{k: s[k] for k in keep} for s in tmeta["scenarios"]], hide_index=True)
    with st.expander("Full metadata (JSON)"):
        st.code(json.dumps({"timing": tmeta, "memory": mmeta}, indent=2), language="json")
