"""Bug 2, part b: rerun the audited timing protocol (benchmark.measure, unchanged) ten times
on ONE fixed input and report how much the reported median moves between runs.

Run from Submissions/BundschuhBastian/ (about 10 s):
    .venv/bin/python audit_HuangJiaxin/reproducers/repro_2b_rerun_protocol.py
Numbers depend on the machine; the point is the spread for identical input.
"""
import statistics

import _target  # noqa: F401
from benchmark import SEED, measure
from data import make_ids, make_queries

ids = make_ids(1_000, SEED, "none")
queries = make_queries(ids, 1, 0.5, SEED)
print("n=1000, q=1, the same input every time; median total per run in microseconds")
for method in ("linear_v2", "hash"):
    medians = [statistics.median(r[3] for r in measure(method, ids, queries)) * 1e6
               for _ in range(10)]
    print(f"  {method:<9} {', '.join(f'{m:.1f}' for m in medians)}"
          f"   -> max/min {max(medians) / min(medians):.2f}x")
