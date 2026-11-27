"""Loading and summarising the saved measurements for the dashboard.

Only reads files in results/; never runs a benchmark. All summaries are
computed from the raw repeat values, so the dashboard cannot drift from them.
"""

import json
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
TIME_COLUMNS = ["prepare_s", "query_batch_s", "total_s"]
MEMORY_COLUMNS = [
    "prepare_current_B", "prepare_peak_B", "query_current_B", "query_peak_B",
    "total_current_B", "total_peak_B", "output_getsizeof_B",
]
SCENARIO_KEYS = ["scenario", "n", "q", "hit_rate_target", "hit_rate_actual", "duplicate_rate", "seed"]


def load_timing(results_dir=RESULTS_DIR):
    return pd.read_csv(Path(results_dir) / "timing_raw.csv")


def load_memory(results_dir=RESULTS_DIR):
    return pd.read_csv(Path(results_dir) / "memory_raw.csv")


def load_metadata(name, results_dir=RESULTS_DIR):
    with open(Path(results_dir) / f"{name}_metadata.json") as f:
        return json.load(f)


def timing_summary(raw):
    """Median, min and max over repeats for each scenario, version and method."""
    keys = SCENARIO_KEYS + ["version", "method"]
    agg = raw.groupby(keys)[TIME_COLUMNS].agg(["median", "min", "max"])
    agg.columns = [f"{col}_{stat}" for col, stat in agg.columns]
    return agg.reset_index()


def memory_summary(raw):
    keys = SCENARIO_KEYS + ["version", "method"]
    return raw.groupby(keys)[MEMORY_COLUMNS].median().reset_index()


def versions_of(summary):
    return sorted(summary["version"].unique())


def _ratios(summary, pairs):
    wide = summary.pivot_table(
        index=["scenario", "n", "q", "hit_rate_target", "method"],
        columns="version",
        values=[f"{c}_median" for c in TIME_COLUMNS],
    )
    parts = []
    for new, old in pairs:
        out = pd.DataFrame(index=wide.index)
        for c in TIME_COLUMNS:
            out[f"{c}_ratio"] = wide[(f"{c}_median", new)] / wide[(f"{c}_median", old)]
        out["step"] = f"{new}/{old}"
        out["version"] = new
        parts.append(out.reset_index())
    return pd.concat(parts, ignore_index=True)


def revision_ratios(summary):
    """Ratio of median times between consecutive versions (v2/v1, v3/v2, ...)
    per scenario and method; column `step` names the pair."""
    vs = versions_of(summary)
    return _ratios(summary, list(zip(vs[1:], vs[:-1])))


def relative_to_first(summary):
    """Ratio of every later version to the first one (v2/v1, v3/v1, ...)."""
    vs = versions_of(summary)
    return _ratios(summary, [(v, vs[0]) for v in vs[1:]])


def noise_bound(ratios, column="query_batch_s_ratio"):
    """Largest |ratio - 1| between consecutive versions among methods whose
    code is identical in all versions (linear, hash): an estimate of
    run-to-run measurement noise."""
    same_code = ratios[ratios["method"].isin(["linear", "hash"])]
    return float((same_code[column] - 1).abs().max())


def step_gain(ratios, step, method="binary", column="query_batch_s_ratio"):
    """Relative time saving of one revision step across scenarios:
    (smallest, largest, number of scenarios, median, scenarios that got faster)."""
    r = ratios[(ratios["method"] == method) & (ratios["step"] == step)][column]
    return 1 - r.max(), 1 - r.min(), len(r), 1 - r.median(), int((r < 1).sum())


def ranges_separated(summary, new, old, method="binary", column="query_batch_s"):
    """Scenarios in which every repeat of `new` is faster than every repeat of `old`."""
    s = summary[summary["method"] == method].set_index(["scenario", "version"])
    scenarios = sorted(summary["scenario"].unique())
    return [sc for sc in scenarios if s.loc[(sc, new), f"{column}_max"] < s.loc[(sc, old), f"{column}_min"]]


def headline(timing_sum, memory_sum, ratios):
    """Numbers for the KPI tiles, all derived from the saved results."""
    vs = versions_of(timing_sum)
    latest = timing_sum[timing_sum["version"] == vs[-1]]

    def fastest(q):
        rows = latest[latest["q"] == q]
        winners = rows.loc[rows.groupby("scenario")["total_s_median"].idxmin(), "method"]
        return winners.mode().iloc[0], int((winners == winners.mode().iloc[0]).sum()), len(winners)

    big = memory_sum[(memory_sum["version"] == vs[-1]) & (memory_sum["n"] == memory_sum["n"].max())]
    per_method = big.groupby("method")["prepare_current_B"].median()
    overall = step_gain(relative_to_first(timing_sum), f"{vs[-1]}/{vs[0]}")
    return {
        "versions": vs,
        "steps": {f"{new}/{old}": step_gain(ratios, f"{new}/{old}") for old, new in zip(vs, vs[1:])},
        "overall": overall,
        "noise": noise_bound(ratios),
        "fastest_q1": fastest(1),
        "fastest_q100": fastest(100),
        "hash_vs_sorted": per_method["hash"] / per_method["binary"],
        "n_max": int(memory_sum["n"].max()),
    }


def fmt_seconds(x):
    for unit, factor in (("s", 1.0), ("ms", 1e-3), ("µs", 1e-6), ("ns", 1e-9)):
        if abs(x) >= factor:
            return f"{x / factor:.3g} {unit}"
    return f"{x / 1e-9:.3g} ns"


def fmt_bytes(x):
    x = float(x)
    for unit, factor in (("MiB", 1024 ** 2), ("KiB", 1024)):
        if x >= factor:
            return f"{x / factor:.3g} {unit}"
    return f"{x:,.0f} B"
