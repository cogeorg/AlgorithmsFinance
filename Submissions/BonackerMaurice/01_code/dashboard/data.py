"""Loading and derivation helpers for the dashboard (no Streamlit code in here).

Everything reads the saved files in ../02_results/<run_id>/ (AGENTS.md section 7).
Nothing here runs a benchmark. Times stay in seconds; units are chosen only
for display.
"""
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
SEGMENTS = ("prepare", "query", "total")
SEGMENT_TITLES = {"prepare": "Prepare", "query": "Query batch", "total": "Total (prepare + batch)"}
METHOD_ORDER = ("linear", "binary", "hash")
SCENARIO_ORDER = ("all_present", "all_absent", "mixed")
MAX_SPOT_ELEMENTS = 10_000

OVERHEAD_FACTOR = 10  # medians within 10x of the harness overhead are overhead-dominated

# Expected log-log slope of time against n over n = 1e3..1e5, per (method, version, segment);
# version None = any version. Bands, not pass/fail thresholds: log n is not flat over this
# range, and cache effects add to it.
EXPECTED_SLOPE = {
    ("linear", "v1", "prepare"): ("≈ 1", "list(ids) copy, O(n)"),
    ("linear", "v2", "prepare"): ("≈ 0 (overhead only)", "no work: returns the input"),
    ("linear", None, "query"): ("≈ 1", "scan, O(n) per query; hits stop at the first occurrence"),
    ("linear", None, "total"): ("≈ 1", "the O(q·n) scan dominates (plus the O(n) copy in v1)"),
    ("binary", None, "prepare"): ("≈ 1.0–1.2", "sorted() copy, O(n log n)"),
    ("binary", None, "query"): ("≈ 0.1–0.3", "O(log n) per query, plus cache effects"),
    ("binary", None, "total"): ("≈ 0.9–1.2", "the O(n log n) sort dominates as n grows"),
    ("hash", None, "prepare"): ("≈ 1", "set() construction, expected O(n)"),
    ("hash", None, "query"): ("≈ 0–0.3", "expected O(1) per query, plus cache effects"),
    ("hash", None, "total"): ("≈ 1", "set() construction dominates"),
}


# --- finding and loading runs ---------------------------------------------------------

def results_dir() -> Path:
    """../02_results/ next to the code folder, unless the RESULTS_DIR environment variable
    says otherwise."""
    return Path(os.environ.get("RESULTS_DIR") or PROJECT_DIR.parent / "02_results")


def list_runs(root) -> list:
    """Run directories that contain run.json, newest first (run_id starts with a UTC timestamp)."""
    runs = []
    for path in sorted(Path(root).glob("*/run.json"), reverse=True):
        config = _read_json(path)
        if config is None:
            continue
        name = path.parent.name
        runs.append({"run_id": config.get("run_id", name), "path": str(path.parent),
                     "quick": bool(config.get("quick")) or name.endswith("_quick")})
    return runs


def default_run_index(runs) -> int:
    """Newest non-quick run; the newest run if all are quick."""
    return next((i for i, r in enumerate(runs) if not r["quick"]), 0)


def dir_stamp(run_dir) -> tuple:
    """Changes whenever a file in the run directory changes (cache key for loading)."""
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                 for p in sorted(Path(run_dir).iterdir()) if p.is_file())


def load_run(run_dir) -> dict:
    """All files of one run. Missing files come back as None (e.g. a --skip-memory run)."""
    run_dir = Path(run_dir)
    config = _read_json(run_dir / "run.json") or {}
    labels = {m["key"]: m["label"] for m in config.get("methods", [])}
    tests = parse_junit(run_dir / "tests.xml") if (run_dir / "tests.xml").exists() else None
    tests_txt = run_dir / "tests.txt"
    return {
        "dir": str(run_dir),
        "config": config,
        "env": _read_json(run_dir / "environment.json"),
        "datasets": _read_csv(run_dir / "datasets.csv"),
        "raw": _with_labels(_read_csv(run_dir / "timings_raw.csv"), labels),
        "summary": _with_labels(_read_csv(run_dir / "timings_summary.csv"), labels),
        "memory": _with_labels(_read_csv(run_dir / "memory.csv"), labels),
        "tests": tests,
        "tests_txt": tests_txt.read_text(errors="replace") if tests_txt.exists() else None,
        "files": sorted(p.name for p in run_dir.iterdir() if p.is_file()),
    }


def _read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _read_csv(path):
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return None


def _with_labels(df, labels):
    if df is None:
        return None
    keys = df["method"] + "_" + df["version"]
    return df.assign(key=keys, label=[labels.get(k, k) for k in keys])


def parse_junit(path) -> dict:
    """Per-test outcomes and counts from pytest's JUnit XML."""
    outcomes = {"failure": "failed", "error": "error", "skipped": "skipped"}
    rows = []
    for case in ET.parse(path).getroot().iter("testcase"):
        outcome, message = "passed", ""
        for child in case:
            if child.tag in outcomes:
                outcome = outcomes[child.tag]
                message = child.get("message") or (child.text or "").strip()[:500]
                break
        rows.append({"test": f"{case.get('classname', '')}::{case.get('name', '')}",
                     "outcome": outcome, "time_s": float(case.get("time") or 0.0),
                     "message": message})
    table = pd.DataFrame(rows, columns=["test", "outcome", "time_s", "message"])
    counts = {k: int((table["outcome"] == k).sum()) for k in ("passed", "failed", "skipped", "error")}
    counts["total"] = len(table)
    return {"table": table, "counts": counts}


# --- units ----------------------------------------------------------------------------

def pick_unit(seconds) -> tuple:
    """(unit, seconds per unit) that suits the typical value of a chart or table."""
    values = [v for v in seconds if v > 0]
    typical = float(np.median(values)) if values else 1.0
    if typical >= 1:
        return "s", 1.0
    if typical >= 1e-3:
        return "ms", 1e-3
    return "µs", 1e-6


def format_seconds(value) -> str:
    """One value with its own unit, e.g. '24.6 ns' or '1.23 ms'."""
    if value is None or not math.isfinite(value):
        return "n/a"
    for unit, size in (("s", 1.0), ("ms", 1e-3), ("µs", 1e-6)):
        if abs(value) >= size:
            return f"{value / size:.3g} {unit}"
    return f"{value / 1e-9:.3g} ns"


# --- derived tables -------------------------------------------------------------------

def two_version_methods(config) -> list:
    """Methods that have both a v1 and a v2 in the run, in the usual order."""
    versions = {}
    for m in config.get("methods", []):
        versions.setdefault(m["method"], set()).add(m["version"])
    return [m for m in _ordered(versions) if {"v1", "v2"} <= versions[m]]


def _ordered(methods) -> list:
    rank = {m: i for i, m in enumerate(METHOD_ORDER)}
    return sorted(methods, key=lambda m: (rank.get(m, len(rank)), m))


def per_query(df):
    """Derived per-query values (batch / q) for rows of the query segment."""
    return df.assign(**{c: df[c] / df["q"] for c in ("median_s", "min_s", "max_s")})


def overhead_floor(config, segment):
    """Harness overhead per call for the wrapper used by this segment, or None.

    prepare and query are timed through functools.partial (noop_call_s), total
    through a lambda (noop_lambda_call_s; older runs only recorded noop_call_s).
    """
    if segment == "total" and config.get("noop_lambda_call_s"):
        return config["noop_lambda_call_s"]
    return config.get("noop_call_s")


def near_overhead(df, config, column="median_s"):
    """True where a time is within OVERHEAD_FACTOR x the harness overhead of its segment."""
    floors = df["segment"].map(lambda seg: overhead_floor(config, seg) or 0.0)
    return df[column] < OVERHEAD_FACTOR * floors


def speedup_table(summary, methods) -> pd.DataFrame:
    """median v1 / median v2 per (method, segment, q, scenario, n); > 1 means v2 is faster."""
    s = summary[summary["method"].isin(methods) & summary["version"].isin(["v1", "v2"])]
    wide = s.pivot_table(index=["method", "segment", "q", "scenario", "n"], columns="version",
                         values=["median_s", "min_s", "max_s"], aggfunc="first")
    wide.columns = [f"{value}_{version}" for value, version in wide.columns]
    wide = wide.reset_index().dropna(subset=["median_s_v1", "median_s_v2"])
    wide["speedup"] = wide["median_s_v1"] / wide["median_s_v2"]
    wide["ranges_overlap"] = (np.maximum(wide["min_s_v1"], wide["min_s_v2"])
                              <= np.minimum(wide["max_s_v1"], wide["max_s_v2"]))
    return sort_rows(wide)


def sort_rows(df) -> pd.DataFrame:
    """Sort by method, version, segment, q, scenario and n; named values in their usual order."""
    rank = {"method": METHOD_ORDER, "segment": SEGMENTS, "scenario": SCENARIO_ORDER}

    def key(col):
        if col.name not in rank:
            return col
        order = {v: i for i, v in enumerate(rank[col.name])}
        return col.map(lambda v: order.get(v, len(order)))

    keys = [c for c in ("method", "version", "segment", "q", "scenario", "n") if c in df.columns]
    return df.sort_values(keys, key=key).reset_index(drop=True)


def loglog_slope(n, seconds) -> float:
    """Least-squares slope of log10(time) against log10(n); NaN with fewer than two sizes."""
    n, seconds = np.asarray(n, dtype=float), np.asarray(seconds, dtype=float)
    if len(set(n)) < 2:
        return float("nan")
    return float(np.polyfit(np.log10(n), np.log10(seconds), 1)[0])


def expected_slope(method, version, segment) -> tuple:
    return (EXPECTED_SLOPE.get((method, version, segment))
            or EXPECTED_SLOPE.get((method, None, segment)) or ("?", "no expectation recorded"))


def scaling_table(summary, q, scenario, config) -> pd.DataFrame:
    """Fitted log-log slope of median time vs n per method/version/segment, for one q and scenario."""
    sel = summary[(summary["q"] == q) & (summary["scenario"] == scenario)]
    sel = sel.assign(near_overhead=near_overhead(sel, config))
    sizes = sorted(sel["n"].unique())
    rows = []
    for (method, version, segment), g in sel.groupby(["method", "version", "segment"]):
        g = g.sort_values("n")
        expected, why = expected_slope(method, version, segment)
        row = {"method": method, "version": version, "label": g["label"].iloc[0],
               "segment": segment, "fitted_slope": loglog_slope(g["n"], g["median_s"])}
        t = dict(zip(g["n"], g["median_s"]))
        for a, b in zip(sizes, sizes[1:]):
            row[f"local {a:,}→{b:,}"] = (math.log(t[b] / t[a]) / math.log(b / a)
                                         if a in t and b in t else float("nan"))
        row.update({"expected": expected, "why": why,
                    "smallest_median_s": g["median_s"].min(),
                    "near_overhead": bool(g["near_overhead"].any()),
                    "max_rel_spread": ((g["max_s"] - g["min_s"]) / g["median_s"]).max()})
        rows.append(row)
    return sort_rows(pd.DataFrame(rows)) if rows else pd.DataFrame()


def all_slopes(summary) -> pd.DataFrame:
    """Fitted slopes for every q and scenario (rows: method/version/segment)."""
    rows = []
    for (method, version, segment, q, scenario), g in summary.groupby(
            ["method", "version", "segment", "q", "scenario"]):
        rows.append({"method": method, "version": version, "segment": segment,
                     "column": f"q={q}, {scenario}", "slope": loglog_slope(g["n"], g["median_s"])})
    if not rows:
        return pd.DataFrame()
    columns = [f"q={q}, {s}" for q, s in sort_rows(summary[["q", "scenario"]].drop_duplicates())
               .itertuples(index=False)]
    wide = pd.DataFrame(rows).pivot_table(index=["method", "version", "segment"],
                                          columns="column", values="slope", aggfunc="first")
    wide = wide[[c for c in columns if c in wide.columns]]
    return sort_rows(wide.reset_index())


# --- spot check -----------------------------------------------------------------------

_SEPARATORS = re.compile(r"[\s,;\[\]()]+")


def parse_values(text, name="input") -> list:
    """Comma/space separated values. Integers become int; anything else is passed on
    unchanged (True/False as bool, decimals as float, other text as str) so that the
    methods' own validation can reject it with TypeError."""
    tokens = [t for t in _SEPARATORS.split(text or "") if t]
    if len(tokens) > MAX_SPOT_ELEMENTS:
        raise ValueError(f"{name} has {len(tokens):,} elements; the limit is {MAX_SPOT_ELEMENTS:,}")
    return [_convert(t) for t in tokens]


def _convert(token):
    try:
        return int(token)
    except ValueError:
        pass
    if token in ("True", "False"):
        return token == "True"
    try:
        return float(token)
    except ValueError:
        return token


def is_valid_ids(values) -> bool:
    return all(isinstance(v, int) and not isinstance(v, bool) for v in values)


def run_spot_check(methods, ids, queries) -> dict:
    """Call every method through Method.__call__ (validation included) on fresh copies.

    Valid input: each method must return a list of bools equal to the reference
    [q in list(ids) for q in queries] and leave its input unchanged.
    Invalid input: each method must raise TypeError.
    """
    valid = is_valid_ids(ids) and is_valid_ids(queries)
    reference = [q in list(ids) for q in queries]
    rows, outputs = [], {}
    for m in methods:
        ids_arg, queries_arg = list(ids), list(queries)
        try:
            out, error = m(ids_arg, queries_arg), None
        except Exception as exc:  # TypeError is the specified outcome for invalid input
            out, error = None, f"{type(exc).__name__}: {exc}"
        is_list = isinstance(out, list)
        bools = is_list and all(type(v) is bool for v in out)
        unchanged = ids_arg == list(ids) and queries_arg == list(queries)
        mismatches = (sum(not (type(a) is bool and a == b) for a, b in zip(out, reference))
                      + abs(len(out) - len(reference))) if is_list else None
        if valid:
            ok = error is None and bools and mismatches == 0 and unchanged
        else:
            ok = error is not None and error.startswith("TypeError")
        if error:
            result = error
        else:
            result = f"returned a list of {len(out)}" if is_list else f"returned {type(out).__name__}"
        rows.append({"key": m.key, "label": m.label, "ok": ok, "result": result,
                     "list of bool": bools if error is None else None,
                     "mismatches vs reference": mismatches, "input unchanged": unchanged})
        if is_list:
            outputs[m.key] = out
    return {"valid": valid, "reference": reference, "rows": rows, "outputs": outputs}
