"""Loading and reshaping of the SAVED results for the dashboard.

Nothing here measures anything or imports the algorithms: the dashboard only reads the
files that bench_time.py, bench_memory.py and check_total.py wrote to results/.
"""
import json
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
REQUIRED = ["timing_raw.csv", "timing_summary.csv", "timing_metadata.json",
            "memory_raw.csv", "memory_summary.csv", "memory_metadata.json"]
UNITS = {"seconds (s)": 1.0, "milliseconds (ms)": 1e3,
         "microseconds (µs)": 1e6, "nanoseconds (ns)": 1e9}
PHASES = ["prepare", "query", "total"]
KEY = ["n", "q", "hit_rate", "method"]


def missing_files(results_dir=None):
    folder = Path(results_dir) if results_dir is not None else RESULTS_DIR
    return [name for name in REQUIRED if not (folder / name).exists()]


def load_results(results_dir=None):
    """Read all saved files. Raises FileNotFoundError naming the missing ones."""
    results_dir = Path(results_dir) if results_dir is not None else RESULTS_DIR
    missing = missing_files(results_dir)
    if missing:
        raise FileNotFoundError(", ".join(missing))
    return {
        "time_raw": pd.read_csv(results_dir / "timing_raw.csv"),
        "time_summary": pd.read_csv(results_dir / "timing_summary.csv"),
        "time_meta": json.loads((results_dir / "timing_metadata.json").read_text()),
        "mem_raw": pd.read_csv(results_dir / "memory_raw.csv"),
        "mem_summary": pd.read_csv(results_dir / "memory_summary.csv"),
        "mem_meta": json.loads((results_dir / "memory_metadata.json").read_text()),
    }


def scaled_times(summary, phase, per_query, factor):
    """Rows of one phase with columns value / low / high in the chosen unit.

    per_query divides by q; it exists only for the phases 'query' and 'total'
    (preparation does not belong to a single query), so 'prepare' stays per batch.
    """
    part = summary[summary["phase"] == phase].copy()
    divide = part["q"] if (per_query and phase != "prepare") else 1
    part["value"] = part["median_seconds_per_batch"] / divide * factor
    part["low"] = part["min_seconds_per_batch"] / divide * factor
    part["high"] = part["max_seconds_per_batch"] / divide * factor
    part["per"] = "per query" if (per_query and phase != "prepare") else "per batch"
    return part


def total_vs_sum(summary):
    """One row per (n, q, hit rate, method): measured total next to prepare + query.

    ratio = total / (prepare + query), spread = max / min of the repeats,
    ranges_overlap: [min total, max total] overlaps [min prepare + min query,
    max prepare + max query].
    """
    wide = summary.pivot_table(index=KEY, columns="phase",
                               values=["median_seconds_per_batch", "min_seconds_per_batch",
                                       "max_seconds_per_batch"])
    out = wide.index.to_frame(index=False)
    med, low, high = (wide[f"{s}_seconds_per_batch"] for s in ("median", "min", "max"))
    out["prepare"] = med["prepare"].values
    out["query"] = med["query"].values
    out["measured_total"] = med["total"].values
    out["prepare_plus_query"] = out["prepare"] + out["query"]
    out["ratio"] = out["measured_total"] / out["prepare_plus_query"]
    for phase in PHASES:
        out[f"spread_{phase}"] = (high[phase] / low[phase]).values
    out["total_low"], out["total_high"] = low["total"].values, high["total"].values
    out["sum_low"] = (low["prepare"] + low["query"]).values
    out["sum_high"] = (high["prepare"] + high["query"]).values
    out["ranges_overlap"] = (out["total_low"] <= out["sum_high"]) & \
                            (out["sum_low"] <= out["total_high"])
    return out.sort_values(KEY).reset_index(drop=True)


def version_comparison(summary):
    """binary_v1 vs binary_v2 per (n, q, hit rate, phase); ratio = v2 / v1 (medians)."""
    binary = summary[summary["algorithm"] == "binary"]
    wide = binary.pivot_table(index=["n", "q", "hit_rate", "phase"], columns="version",
                              values="median_seconds_per_batch").reset_index()
    wide = wide.rename(columns={"v1": "v1_recursive", "v2": "v2_iterative"})
    wide["v2_over_v1"] = wide["v2_iterative"] / wide["v1_recursive"]
    return wide


def memory_table(mem_summary, q, hit_rate, field):
    """Flat table for one q and hit rate: method, phase, then one column per n (bytes)."""
    part = mem_summary[(mem_summary["q"] == q) & (mem_summary["hit_rate"] == hit_rate)]
    wide = part.pivot_table(index=["method", "phase"], columns="n", values=field)
    wide = wide.reindex(columns=sorted(wide.columns)).reset_index()
    wide.columns = ["method", "phase"] + [f"n = {int(n):,}" for n in wide.columns[2:]]
    wide["phase"] = pd.Categorical(wide["phase"], PHASES, ordered=True)
    return wide.sort_values(["method", "phase"]).reset_index(drop=True)
