# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportReturnType=false
# (pandas and altair give no usable types here; the pages are checked by tests/test_dashboard.py)
"""Loading and reshaping of the saved results for the dashboard.

Reads files in results/ only (CSV and JSON). It never imports the order books or the benchmark
code and never runs a replay: every number on the dashboard was measured earlier and saved.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS = Path(__file__).resolve().parent.parent / "results"
RUN_KEY = ["version", "scenario", "seed", "events", "levels"]
SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]
LIMIT_SECONDS = 600


def csv(name: str) -> pd.DataFrame:
    path = RESULTS / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def js(name: str):
    path = RESULTS / name
    return json.loads(path.read_text()) if path.exists() else {}


def runs(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per run (version, stream): status, median, repeats, reason. time_raw.csv has one row
    per replay and repeats the run-level fields on each of them."""
    if raw.empty:
        return raw
    out = raw.drop_duplicates(RUN_KEY, keep="first").copy()
    out["median_seconds"] = pd.to_numeric(out["median_seconds"], errors="coerce")
    out["throughput_eps"] = out["events"] / out["median_seconds"]
    return out


def marker_column(r: pd.DataFrame) -> pd.DataFrame:
    """Chart marker per run: measured / stopped at the limit / not run (no value)."""
    r = r.copy()
    r["marker"] = np.select(
        [r["status"] == "ok", r["status"] == "stopped", r["status"] == "not_run"],
        ["measured (median)", f"stopped at the {LIMIT_SECONDS} s limit", "not run (no value)"],
        default="error")
    return r


def scaling_exponents(r: pd.DataFrame) -> pd.DataFrame:
    """Fitted slope of log(median seconds) against log(events) for the grid sizes (10^3..10^5), from
    the median over seeds; only if all three sizes were measured. A description, not a proof."""
    rows = []
    ok = r[(r["status"] == "ok") & (r["events"] <= 100000) & (r["levels"] == 1000)]
    for (v, s), g in ok.groupby(["version", "scenario"]):
        m = g.groupby("events")["median_seconds"].median()
        if len(m) == 3:
            slope = float(np.polyfit(np.log10(m.index.astype(float)), np.log10(m.values), 1)[0])
            rows.append({"version": v, "scenario": s, "fitted_exponent": round(slope, 2)})
    return pd.DataFrame(rows)


def checkpoints(frame: pd.DataFrame) -> pd.DataFrame:
    """Memory checkpoints (every 10% of the events) as long format."""
    rows = []
    for _, r in frame.iterrows():
        if isinstance(r.get("checkpoints_bytes"), str):
            for i, b in enumerate(json.loads(r["checkpoints_bytes"]), start=1):
                rows.append({"version": r["version"], "scenario": r["scenario"],
                             "events": r["events"], "percent_of_events": i * 10, "bytes": b})
    return pd.DataFrame(rows)


def canary_blocks(c: pd.DataFrame) -> pd.DataFrame:
    """Canary median per (block, before/after)."""
    if c.empty:
        return c
    g = c.drop_duplicates(["block", "canary_point", "start_utc"]).copy()
    g["median_seconds"] = pd.to_numeric(g["median_seconds"])
    return g[["start_utc", "block", "canary_point", "median_seconds", "power_source",
              "low_power_mode"]].reset_index(drop=True)
