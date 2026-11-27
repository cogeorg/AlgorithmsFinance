"""Compare a fresh rerun of Bastian's timing script with his saved results.

The rerun happens in a temporary copy of his folder (see run_audit.sh), never in his folder.
Run:  python compare_rerun.py <rerun_results_dir>      (writes logs/compare_rerun.txt)
"""
import json
import sys
from pathlib import Path

import pandas as pd

from _common import TARGET, Report

R = Report("compare_rerun")
saved = TARGET / "results"
rerun = Path(sys.argv[1])
env = json.loads((rerun / "timing_metadata.json").read_text())["environment"]
R.note(f"rerun environment: Python {env['python_version'][:7]}, {env['platform']}, "
       f"CPU {env.get('cpu_model', 'unknown')}")


def load(folder):
    s = pd.read_csv(folder / "timing_summary.csv")
    Q = s[s.phase == "query"].pivot_table(index=["n", "q", "hit_rate"], columns="method",
                                          values="median_seconds_per_batch")
    T = s[s.phase == "total"].pivot_table(index=["n", "q", "hit_rate"], columns="method",
                                          values="median_seconds_per_batch")
    return s, Q, T


for label, folder in [("saved (Bastian)", saved), ("rerun (reviewer)", rerun)]:
    s, Q, T = load(folder)
    for q in (1, 100):
        row = T.loc[(100000, q, "mixed")].sort_values()
        R.note(f"{label}: n = 100,000, q = {q}, mixed, total: "
               + " < ".join(f"{m} {v * 1e3:.2f} ms" for m, v in row.items()))

s, Q, T = load(rerun)
# Qualitative conclusions of his README.
R.check(T.loc[(100000, 1, "mixed")].idxmin() == "linear_v1", "rerun: for q = 1 linear search has the smallest total")
R.check(T.loc[(100000, 100, "mixed")].idxmin() == "hash_v1", "rerun: for q = 100 the hash set has the smallest total")
lin = Q.xs((100, "all-absent"), level=(1, 2)).linear_v1
R.check(5 < lin[10000] / lin[1000] < 20 and 5 < lin[100000] / lin[10000] < 20,
        f"rerun: linear query time grows about 10x per 10x n ({lin[10000] / lin[1000]:.1f}x, {lin[100000] / lin[10000]:.1f}x)")
h = Q.xs((100, "all-absent"), level=(1, 2)).hash_v1
R.check(h.max() / h.min() < 2, f"rerun: hash query time is flat in n (max/min {h.max() / h.min():.2f})")

# The quantitative revision claim (README: v2/v1 query 0.64 to 0.75 over all 18 configurations).
rq = Q.binary_v2 / Q.binary_v1
slower = rq[rq >= 1]
R.check(slower.empty, f"rerun: binary_v2 query phase faster than v1 in all 18 configurations "
        f"(v2/v1 {rq.min():.2f} to {rq.max():.2f}; v2 not faster in {len(slower)})")
for (n, q, hr), v in slower.items():
    R.note(f"   v2/v1 = {v:.2f} at n = {n}, q = {q}, {hr}")
r100 = rq.xs(100, level=1)
R.note(f"rerun, q = 100 only: v2/v1 {r100.min():.2f} to {r100.max():.2f}")

tc = pd.read_csv(rerun / "total_consistency.csv")
R.note(f"rerun total/(prepare+query): {tc.ratio_total_over_sum.min():.2f} to {tc.ratio_total_over_sum.max():.2f}, "
       f"ranges not overlapping in {int((~tc.ranges_overlap).sum())} of {len(tc)} (saved: 0.73 to 1.25, 12 of 72)")
R.save()
