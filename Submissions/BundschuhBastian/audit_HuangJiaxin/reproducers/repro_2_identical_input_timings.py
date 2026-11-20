"""Bug 2: the saved timings give very different medians for IDENTICAL inputs.

Because of Bug 1, the settings (q=1, hit_rate=0.0) and (q=1, hit_rate=0.5) use the same
array and the same single query. breakeven.py also measures q=1, hit_rate=0.5 with the
same seed. Same code, same input -> the medians should agree within the repeat spread.
This script only READS the saved results of the audited commit and exits with code 1
if the medians differ by more than a factor of 1.5.

Run from Submissions/BundschuhBastian/:
    .venv/bin/python audit_HuangJiaxin/reproducers/repro_2_identical_input_timings.py
"""
import sys

import pandas as pd

from _target import TARGET

RES = TARGET / "results"
summary = pd.read_csv(RES / "timing_summary.csv")
raw = pd.read_csv(RES / "timing_raw.csv")
curve = pd.read_csv(RES / "breakeven_curve.csv")


def total(method, n, hit):
    row = summary[(summary.method == method) & (summary.n == n) & (summary.q == 1)
                  & (summary.hit_rate == hit)]
    return float(row.total_median_s.iloc[0])


worst = 1.0
print("n=1000, q=1, identical input (one absent query), total time in microseconds")
for method in ("linear_v2", "hash", "binary_v2"):
    a, b = total(method, 1000, 0.0), total(method, 1000, 0.5)
    c = float(curve[(curve.method == method) & (curve.n == 1000)
                    & (curve.q == 1)].total_median_s.iloc[0])
    reps = raw[(raw.method == method) & (raw.n == 1000) & (raw.q == 1)
               & (raw.hit_rate == 0.0)].total_s * 1e6
    ratio = max(a, b, c) / min(a, b, c)
    worst = max(worst, ratio)
    print(f"  {method:<9} benchmark hit 0.0: {a*1e6:7.2f}  benchmark hit 0.5: {b*1e6:7.2f}  "
          f"breakeven.py: {c*1e6:7.2f}  -> max/min {ratio:4.1f}x   "
          f"raw repeats (hit 0.0): {', '.join(f'{v:.1f}' for v in reps)}")

fastest = {hit: min(("linear_v2", "hash", "binary_v2"), key=lambda m: total(m, 1000, hit))
           for hit in (0.0, 0.5)}
print(f"fastest method for q=1, n=1000: hit 0.0 -> {fastest[0.0]}, hit 0.5 -> {fastest[0.5]} "
      "(same input!)")
print("README claim: 'q = 1: linear_v2 has the smallest total time'")
sys.exit(1 if worst > 1.5 else 0)
