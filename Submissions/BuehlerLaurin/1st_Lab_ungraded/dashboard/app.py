"""Streamlit dashboard for the membership benchmarks (LAB_SPEC.md D1-D6).

Reads saved results only (``results/raw/timing_*``, ``results/memory/memory_*``) through
``dashboard/data.py``. It never runs a benchmark (D4); loading is cached with
``st.cache_data``, so changing a filter does not even reread the files.

Views
    * Elapsed time vs. n (log-log), one curve per method, solid = original, dashed =
      revised; tabs for total, preparation and query batch (D1, D2). Vertical bars show
      the min-max range of the 5 repeats.
    * Original vs. revised: speed-up table (original median / revised median) (D1).
    * Memory table (tracemalloc) with what each value includes (D3).
    * Raw repeats and environment details in expanders (D5).
    Filters: query count q and hit rate; the realized hit rate and units are shown (D3).

Run (from Submissions/BuehlerLaurin):  streamlit run dashboard/app.py
Default address: http://localhost:8501
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

SUBMISSION_DIR = Path(__file__).resolve().parent.parent
if str(SUBMISSION_DIR) not in sys.path:  # `streamlit run` only adds dashboard/ to the path
    sys.path.insert(0, str(SUBMISSION_DIR))

from dashboard.data import (  # noqa: E402
    RunInfo,
    default_run,
    list_runs,
    speedup_table,
)

HIT_RATE_NAMES = {1.0: "all-present (1.0)", 0.0: "all-absent (0.0)", 0.5: "mixed (0.5)"}
METRICS = {
    "total_s": "Total (prepare + query batch)",
    "prep_s": "Preparation",
    "query_batch_s": "Query batch",
}


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data
def load_json(path: str) -> dict[str, Any]:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def pick_run(title: str, runs: list[RunInfo], key: str) -> RunInfo | None:
    """Sidebar selector; preselects the newest clean run."""
    if not runs:
        st.sidebar.warning(f"No saved {title.lower()} found.")
        return None
    chosen = default_run(runs)
    index = runs.index(chosen) if chosen in runs else 0
    run = st.sidebar.selectbox(title, runs, index=index, format_func=lambda r: r.label, key=key)
    if run.git_dirty:
        st.sidebar.warning("This run was measured on uncommitted code (git_dirty = true).")
    return run


def time_chart(data: pd.DataFrame, metric: str, per_query: bool, q: int) -> dict[str, Any]:
    """Vega-Lite spec: median vs. n on log-log axes, min-max rule per point."""
    if metric == "query_batch_s" and per_query:
        y_title = "seconds per query (batch / q)"
    elif metric == "query_batch_s":
        y_title = f"seconds per batch of q = {q} queries"
    elif metric == "prep_s":
        y_title = "seconds per preparation"
    else:
        y_title = f"seconds (preparation + batch of q = {q})"
    x = {"field": "n", "type": "quantitative", "scale": {"type": "log"},
         "title": "n (array length, log scale)", "axis": {"values": [1000, 10000, 100000]}}
    color = {"field": "method", "type": "nominal", "title": "method"}
    return {
        "height": 380,
        "layer": [
            {
                "mark": {"type": "rule", "opacity": 0.5},
                "encoding": {
                    "x": x,
                    "y": {"field": "min", "type": "quantitative", "scale": {"type": "log"}},
                    "y2": {"field": "max"},
                    "color": color,
                },
            },
            {
                "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": x,
                    "y": {"field": "median", "type": "quantitative",
                          "scale": {"type": "log"}, "title": f"{y_title} (log scale)"},
                    "color": color,
                    "strokeDash": {"field": "version", "type": "nominal", "title": "version"},
                    "detail": {"field": "label"},
                    "tooltip": [
                        {"field": "label", "title": "method-version"},
                        {"field": "n", "title": "n"},
                        {"field": "median", "title": "median [s]", "format": ".3e"},
                        {"field": "min", "title": "min [s]", "format": ".3e"},
                        {"field": "max", "title": "max [s]", "format": ".3e"},
                    ],
                },
            },
        ],
    }


def chart_data(summary: pd.DataFrame, metric: str, per_query: bool, q: int) -> pd.DataFrame:
    divisor = q if (metric == "query_batch_s" and per_query) else 1
    return pd.DataFrame(
        {
            "n": summary["n"],
            "method": summary["method"],
            "version": summary["version"],
            "label": summary["label"],
            "median": summary[f"{metric}_median"] / divisor,
            "min": summary[f"{metric}_min"] / divisor,
            "max": summary[f"{metric}_max"] / divisor,
        }
    )


def main() -> None:
    st.set_page_config(page_title="Membership benchmarks", layout="wide")
    st.title("Membership search: linear vs. binary vs. hash set")
    st.caption(
        "Reads saved results from `results/` only; no benchmark runs in this app. "
        "Re-measure with `python -m bench.timing` and `python -m bench.memory`."
    )

    # --- Sidebar: runs and filters --------------------------------------------------
    timing_run = pick_run("Timing run", list_runs("timing"), key="timing_run")
    memory_run = pick_run("Memory run", list_runs("memory"), key="memory_run")
    if timing_run is None:
        st.error("No timing results found in results/raw/. Run `python -m bench.timing` first.")
        return

    summary_all = load_csv(str(timing_run.summary_path))
    raw_all = load_csv(str(timing_run.raw_path))
    timing_env = load_json(str(timing_run.env_path))

    q_values = sorted(summary_all["q"].unique())
    hit_values = [h for h in (1.0, 0.0, 0.5) if h in set(summary_all["hit_rate"])]
    q = int(st.sidebar.radio("Query count q", [int(v) for v in q_values],
                             index=len(q_values) - 1,
                             format_func=lambda v: f"{v} queries", key="q"))
    hit_rate = float(st.sidebar.radio("Hit rate (requested)", hit_values,
                                      format_func=lambda h: HIT_RATE_NAMES.get(h, str(h)),
                                      key="hit_rate"))
    methods = st.sidebar.multiselect("Methods", ["linear", "binary", "hash"],
                                     default=["linear", "binary", "hash"], key="methods")
    versions = st.sidebar.multiselect("Versions", ["original", "revised"],
                                      default=["original", "revised"], key="versions")

    cell = summary_all[(summary_all["q"] == q) & (summary_all["hit_rate"] == hit_rate)]
    shown = cell[cell["method"].isin(methods) & cell["version"].isin(versions)]

    # --- Key facts --------------------------------------------------------------------
    realized = sorted(cell["realized_hit_rate"].dropna().unique())
    settings = timing_env.get("settings", {})
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Query count q", q)
    c2.metric("Hit rate (requested)", f"{hit_rate:.2f}")
    c3.metric("Hit rate (realized)", ", ".join(f"{r:.2f}" for r in realized) or "n/a")
    c4.metric("Unit", "seconds")
    c5.metric("Repeats per point", settings.get("repeats", "?"))
    st.caption(
        f"Seed {settings.get('seed')}, duplicate policy `{settings.get('duplicate_policy')}`, "
        f"code version {str(timing_env.get('env', {}).get('git_commit'))[:7]} "
        f"(dirty: {timing_env.get('env', {}).get('git_dirty')}). "
        "Points = median of the repeats, vertical bars = min-max of the repeats. "
        "Solid lines = original, dashed = revised. Linear search and hash set are the same "
        "code in both versions, so their two curves show the measurement noise."
    )

    # --- Time vs. n -------------------------------------------------------------------
    st.header("Elapsed time vs. input length n")
    if shown.empty:
        st.info("No method/version selected.")
    else:
        tabs = st.tabs(list(METRICS.values()))
        for tab, metric in zip(tabs, METRICS):
            with tab:
                per_query = False
                if metric == "query_batch_s":
                    per_query = st.toggle("Show per query (batch / q)", key="per_query")
                data = chart_data(shown, metric, per_query, q)
                st.vega_lite_chart(data, time_chart(data, metric, per_query, q), width="stretch")
                unit = "s per query" if per_query else "s"
                table = data.pivot_table(index="label", columns="n", values="median")
                st.dataframe(
                    table.map(lambda v: f"{v:.3e}"),
                    width="stretch",
                )
                st.caption(f"Median, {unit}. Rows: method-version, columns: n.")

    # --- Original vs revised ------------------------------------------------------------
    st.header("Original vs. revised")
    st.markdown(
        "Revision: binary search changed from **recursive with list slicing** (copies O(n) "
        "per query) to an **iterative lower-bound search** on index bounds (O(log n), no "
        "copies). Preparation (`sorted`) is unchanged. Linear and hash: unchanged code. "
        "Speed-up = original median / revised median; > 1 means the revision is faster."
    )
    rows = []
    for metric, name in METRICS.items():
        table = speedup_table(cell, metric)
        table["measure"] = name
        rows.append(table[["method", "n", "measure", "speedup_original_over_revised"]])
    speedups = pd.concat(rows).pivot_table(
        index=["method", "measure"], columns="n", values="speedup_original_over_revised"
    )
    st.dataframe(speedups.map(lambda v: f"{v:.2f}x"), width="stretch")

    # --- Memory -------------------------------------------------------------------------
    st.header("Memory (tracemalloc)")
    if memory_run is None:
        st.info("No memory results found. Run `python -m bench.memory`.")
    else:
        mem = load_csv(str(memory_run.summary_path))
        mem = mem[(mem["q"] == q) & (mem["hit_rate"] == hit_rate)]
        mem = mem[mem["method"].isin(methods) & mem["version"].isin(versions)]
        view = pd.DataFrame(
            {
                "n": mem["n"],
                "method-version": mem["label"],
                "phase": mem["phase"],
                "current [KiB]": (mem["current_bytes_median"] / 1024).round(1),
                "peak [KiB]": (mem["peak_bytes_median"] / 1024).round(1),
                "input included": mem["includes_input"],
                "prepared structure included": mem["includes_prepared"],
                "output included": mem["includes_output"],
                "state is caller's input": mem["state_is_input"],
            }
        )
        st.dataframe(view, width="stretch", hide_index=True)
        st.caption(
            f"Run {memory_run.label}. Unit: KiB (1 KiB = 1,024 bytes), median of the repeats. "
            "Input is built before tracing and never counted. phase `prepare` = prepared "
            "structure only; `query` = output and temporary objects (state built before "
            "tracing); `total` = both. `current` = still allocated when read (state/result "
            "kept alive); `peak` = maximum during the phase, including freed temporaries. "
            "tracemalloc counts Python allocations only; it is not process memory (RSS)."
        )

    # --- Raw data and environment -------------------------------------------------------
    with st.expander("Raw timing repeats (selected q and hit rate)"):
        raw = raw_all[(raw_all["q"] == q) & (raw_all["hit_rate"] == hit_rate)]
        raw = raw[raw["method"].isin(methods) & raw["version"].isin(versions)]
        st.dataframe(raw, width="stretch", hide_index=True)
        st.caption("One row per repeat. Times in seconds; query_batch_s is per batch of q "
                   "queries, query_per_query_s per query; k_* = calls per timed block.")
    if memory_run is not None:
        with st.expander("Raw memory repeats"):
            st.dataframe(load_csv(str(memory_run.raw_path)), width="stretch", hide_index=True)
    with st.expander("Measurement definitions and settings (timing run)"):
        st.json(settings)
    with st.expander("Environment (timing run)"):
        st.json(timing_env.get("env", {}))
    if memory_run is not None:
        with st.expander("Environment and settings (memory run)"):
            st.json(load_json(str(memory_run.env_path)))


main()
