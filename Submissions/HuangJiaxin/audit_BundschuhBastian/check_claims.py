"""Check Bastian's saved results and every number his README / REVISIONS.md quote.

Only reads his results/ folder; recomputes summaries from the raw repeats.
Run:  python check_claims.py      (writes logs/check_claims.txt)
"""
import json

import pandas as pd

from _common import TARGET, Report

R = Report("check_claims")
res = TARGET / "results"
raw = pd.read_csv(res / "timing_raw.csv")
s = pd.read_csv(res / "timing_summary.csv")
tc = pd.read_csv(res / "total_consistency.csv")
mem = pd.read_csv(res / "memory_summary.csv")
meta = json.loads((res / "timing_metadata.json").read_text())

# 1. Summary = medians / min / max of the raw repeats; per query = per batch / q.
key = ["n", "q", "hit_rate", "method", "phase"]
g = raw.groupby(key)["seconds_per_batch"].agg(["median", "min", "max", "count"]).reset_index()
m = s.merge(g, on=key)
R.check(len(m) == len(s) == 216, f"all {len(s)} summary rows have raw repeats")
for col, ours in [("median_seconds_per_batch", "median"), ("min_seconds_per_batch", "min"),
                  ("max_seconds_per_batch", "max")]:
    bad = int((~((m[col] - m[ours]).abs() <= 1e-15 + 1e-12 * m[ours].abs())).sum())
    R.check(bad == 0, f"{col} recomputed from timing_raw.csv: {bad} mismatches")
R.check(bool((m["count"] == 5).all()), "every configuration has exactly 5 timed repeats")
qq = s[s.phase != "prepare"]
bad = int((~((qq.median_seconds_per_query - qq.median_seconds_per_batch / qq.q).abs()
             <= 1e-15 + 1e-12 * qq.median_seconds_per_batch.abs())).sum())
R.check(bad == 0, f"per-query value = per-batch value / q: {bad} mismatches")

# 2. total_consistency.csv recomputed, and the README sentence about it.
piv = s.pivot_table(index=["n", "q", "hit_rate", "method"], columns="phase",
                    values="median_seconds_per_batch").reset_index()
c = tc.merge(piv, on=["n", "q", "hit_rate", "method"])
ratio = c["total"] / (c["prepare"] + c["query"])
R.check(bool(((c.ratio_total_over_sum - ratio).abs() < 1e-12).all()), "total_consistency.csv ratios recomputed")
r = tc.ratio_total_over_sum
R.check(round(r.min(), 2) == 0.73 and round(r.max(), 2) == 1.25, f"README: ratio from 0.73 to 1.25 (data {r.min():.2f} to {r.max():.2f})")
counts = (int(((r >= 0.97) & (r <= 1.03)).sum()), int((r < 0.97).sum()), int((r > 1.03).sum()))
R.check(counts == (42, 22, 8), f"README: 42 within 3 %, 22 below, 8 above (data {counts})")
R.check(int((~tc.ranges_overlap).sum()) == 12, f"README: ranges do not overlap in 12 configurations "
        f"(data {int((~tc.ranges_overlap).sum())})")

# 3. Revision claims (README "Revision v1 to v2", REVISIONS.md "Measured effect").
Q = s[s.phase == "query"].pivot_table(index=["n", "q", "hit_rate"], columns="method",
                                      values="median_seconds_per_batch")
T = s[s.phase == "total"].pivot_table(index=["n", "q", "hit_rate"], columns="method",
                                      values="median_seconds_per_batch")
rq, rt = Q.binary_v2 / Q.binary_v1, T.binary_v2 / T.binary_v1
R.check(round(rq.min(), 2) == 0.64 and round(rq.max(), 2) == 0.75,
        f"README: query v2/v1 from 0.64 to 0.75 over all 18 configurations (data {rq.min():.2f} to {rq.max():.2f})")
R.check(round(rt.min(), 2) == 0.82 and round(rt.max(), 2) == 1.06,
        f"README: total v2/v1 from 0.82 to 1.06 (data {rt.min():.2f} to {rt.max():.2f})")
q1 = Q.loc[(100000, 1)] * 1e6
R.note(f"REVISIONS q = 1, n = 100,000 query (us): v1 {q1.binary_v1.min():.2f} to {q1.binary_v1.max():.2f}, "
       f"v2 {q1.binary_v2.min():.2f} to {q1.binary_v2.max():.2f} (document: 1.9 and 1.2)")
q100 = Q.loc[(100000, 100)] * 1e3
R.check(abs(q100.binary_v1.min() - 0.177) < 5e-4 and abs(q100.binary_v1.max() - 0.188) < 5e-4
        and abs(q100.binary_v2.min() - 0.128) < 5e-4 and abs(q100.binary_v2.max() - 0.133) < 5e-4,
        "REVISIONS: q = 100 query 0.177 to 0.188 ms (v1), 0.128 to 0.133 ms (v2)")

# 4. Sorting share of the total (REVISIONS: "about 20 ms of the 21 to 25 ms total").
P = s[(s.phase == "prepare") & (s.n == 100000) & s.method.str.startswith("binary")]
Tt = s[(s.phase == "total") & (s.n == 100000) & (s.q == 100) & s.method.str.startswith("binary")]
pmin, pmax = P.median_seconds_per_batch.min() * 1e3, P.median_seconds_per_batch.max() * 1e3
tmin, tmax = Tt.median_seconds_per_batch.min() * 1e3, Tt.median_seconds_per_batch.max() * 1e3
R.check(pmax <= tmax, f"REVISIONS: sort 'about 20 ms' of a '21 to 25 ms' total; data: sort medians "
        f"{pmin:.1f} to {pmax:.1f} ms, totals (q = 100) {tmin:.1f} to {tmax:.1f} ms")

# 5. README evidence table (q = 100, all absent, query phase, ms).
claimed = {1000: (1.03, 0.102, 0.075, 0.0026), 10000: (10.8, 0.144, 0.105, 0.0026),
           100000: (133, 0.177, 0.128, 0.0027)}
ev = Q.xs((100, "all-absent"), level=(1, 2)) * 1e3
ok = True
for n, vals in claimed.items():
    for meth, v in zip(["linear_v1", "binary_v1", "binary_v2", "hash_v1"], vals):
        d = ev.loc[n, meth]
        ok &= abs(d - v) <= 0.006 * max(abs(v), 1e-9) + 5e-5
R.check(bool(ok), "README evidence table (q = 100, all absent) matches timing_summary.csv")

# 6. Hit-rate claim: linear all-present about half of all-absent; others independent.
L = Q.xs(100, level=1)
lin = (L.linear_v1.xs("all-present", level=1) / L.linear_v1.xs("all-absent", level=1))
R.check(bool(((lin > 0.4) & (lin < 0.6)).all()), f"README: linear all-present about half of all-absent "
        f"(ratios {', '.join(f'{x:.2f}' for x in lin)})")
for meth in ["binary_v1", "binary_v2", "hash_v1"]:
    x = L[meth].xs("all-present", level=1) / L[meth].xs("all-absent", level=1)
    R.check(bool(((x > 0.9) & (x < 1.1)).all()), f"README: {meth} does not depend on hit rate "
            f"(present/absent {', '.join(f'{v:.2f}' for v in x)})")

# 7. Memory figures quoted in README.
M = mem[(mem.n == 100000) & (mem.phase == "prepare")]
cur = M.groupby("method").median_current_bytes.median()
peak = M.groupby("method").median_peak_bytes.median()
R.check(cur["binary_v1"] == 800056 and cur["hash_v1"] == 4194520,
        f"README memory: sorted copy 800,056 B, set 4,194,520 B (data {int(cur['binary_v1'])}, {int(cur['hash_v1'])})")
R.note(f"peak / current while preparing: sort {peak['binary_v1'] / cur['binary_v1']:.2f}, "
       f"set {peak['hash_v1'] / cur['hash_v1']:.2f} (README: 1.5 and 1.5)")
R.note(f"memory repeats per configuration: {sorted(mem.repeats.unique())} (timing uses 5)")

# 8. Workloads: for q = 1 the 'mixed' setting has the same single present query as 'all-present'.
ds = pd.DataFrame(meta["generator"].get("datasets", meta.get("datasets", [])))
if not ds.empty:
    same = ds[(ds.q == 1) & (ds.hit_rate == "mixed")].hits.tolist()
    R.check(not all(h == 1 for h in same), f"'mixed' differs from 'all-present' for q = 1 "
            f"(hits of q = 1 'mixed' datasets: {same})")

# 9. Code version recorded with the results.
env = meta["environment"]
R.note(f"timing results recorded at commit {env['git_commit'][:7]}, uncommitted changes outside "
       f"results: {env['git_uncommitted_changes_outside_results']}, Python {env['python_version'][:6]}, {env['cpu_model']}")
R.save()
