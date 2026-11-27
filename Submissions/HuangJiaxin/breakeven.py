"""Break-even analysis: from how many queries does preparation pay off?

Run with:  python breakeven.py   (after benchmark.py is not required; this is standalone)

Question: LinearSearch needs no preparation but pays about n per query. Sorting or
building a set costs time once, then each query is cheap. For which query count q is
the prepared method's TOTAL time (prepare + q queries) below LinearSearch's?

Two pieces of evidence are saved:
  1. results/breakeven_curve.csv  - measured total time for q in a grid
  2. results/breakeven_points.csv - estimated break-even q*:
        q* = prepare_time / (linear_time_per_query - method_time_per_query)
     using per-query times measured at q = 1000 (hit rate 0.5).
Same timing rules as benchmark.py (warm-up, 5 repeats, median, fresh preparation).
"""
import csv
import json
import math
import statistics
from pathlib import Path

from benchmark import SEED, DUPLICATES, environment, measure
from data import make_ids, make_queries

SIZES = [1_000, 10_000, 100_000]
Q_GRID = [1, 3, 10, 30, 100, 300, 1000]
HIT = 0.5
COMPARED = ["linear_v2", "binary_v2", "hash"]  # best version of each required method


def med(reps, k):
    return statistics.median(r[k] for r in reps)


def main():
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    curve, points, raw = [], [], []
    for n in SIZES:
        ids = make_ids(n, SEED, DUPLICATES)
        per_query, prep = {}, {}
        for q in Q_GRID:
            queries = make_queries(ids, q, HIT, SEED)
            id_set = set(ids)
            expected = [x in id_set for x in queries]
            for method in COMPARED:
                reps = measure(method, ids, queries, expected)
                for rep_i, p, qs, tot, ip, iq in reps:
                    raw.append([method, n, q, HIT, rep_i, p, qs, tot, ip, iq])
                curve.append([method, n, q, HIT, med(reps, 1), med(reps, 2), med(reps, 3)])
                if q == max(Q_GRID):
                    per_query[method] = med(reps, 2) / q
                    prep[method] = med(reps, 1)
            print(f"n={n:>6} q={q:>5} done")
        for method in ["binary_v2", "hash"]:
            gain = per_query["linear_v2"] - per_query[method]
            q_star = prep[method] / gain if gain > 0 else math.inf
            points.append([method, n, HIT, prep[method], per_query[method],
                           per_query["linear_v2"], q_star])
            print(f"n={n:>6} {method:<9} break-even q* = {q_star:8.2f}")

    with open(out / "breakeven_curve.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "n", "q", "hit_rate", "prepare_median_s",
                    "query_median_s", "total_median_s"])
        w.writerows(curve)
    with open(out / "breakeven_points.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "n", "hit_rate", "prepare_s", "per_query_s",
                    "linear_per_query_s", "breakeven_q"])
        w.writerows(points)
    with open(out / "breakeven_raw.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "n", "q", "hit_rate", "repeat", "prepare_s", "query_s",
                    "total_s", "inner_prepare", "inner_query"])
        w.writerows(raw)
    meta = {**environment("breakeven.py"), "seed": SEED, "sizes": SIZES, "q_grid": Q_GRID,
            "hit_rate": HIT, "methods": COMPARED,
            "units": "seconds per complete batch; breakeven_q in queries"}
    (out / "breakeven_environment.json").write_text(json.dumps(meta, indent=2))
    print(f"saved {out/'breakeven_curve.csv'}, {out/'breakeven_points.csv'}, "
          f"{out/'breakeven_raw.csv'}, {out/'breakeven_environment.json'}")


if __name__ == "__main__":
    main()
