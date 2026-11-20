"""Finding 2: two small reproducible bugs outside the algorithms.

B1  dashboard/report.py sig3() promises "3 significant digits" but shows 4 when rounding
    crosses a power of ten (0.9996 -> "1.000", 99.96 -> "100.0").
B2  bench_time.py environment() reports git_commit = "" and
    git_uncommitted_changes_outside_results = False when git is not available (Docker,
    a copied folder, a ZIP download). "No uncommitted changes" is then claimed although
    the code version is unknown.
Also: the dashboard sentence "binary search in X ms (Y % of it is sorting)" takes X from
the measured total but Y from prepare / (prepare + query), so the sorting time can exceed X.

Run:  python finding_2_bugs.py      (writes logs/finding_2_bugs.txt)
"""
import json
import sys

import pandas as pd

from _common import LOGS, TARGET, Report, import_target

import_target()
sys.path.insert(0, str(TARGET / "dashboard"))
import bench_time                      # noqa: E402  (Bastian's timing script, only imported)
import report                          # noqa: E402  (Bastian's dashboard helpers)

R = Report("finding_2_bugs")

# B1: significant digits.
for value, want in [(0.1769, "0.177"), (133.39, "133"), (0.9996, "1.00"), (99.96, "100"),
                    (9.996, "10.0")]:
    got = report.sig3(value)
    R.check(got == want, f"B1 sig3({value}) -> '{got}' (3 significant digits: '{want}')")

# B2: code version when git is not available.
env = bench_time.environment()
R.note(f"B2 environment() here: git_commit={env['git_commit']!r}, "
       f"git_uncommitted_changes_outside_results={env['git_uncommitted_changes_outside_results']}")
R.check(not (env["git_commit"] == "" and env["git_uncommitted_changes_outside_results"] is False),
        "B2 an unknown code version is not reported as 'no uncommitted changes'")
rerun_meta = LOGS / "rerun_results" / "timing_metadata.json"
if rerun_meta.exists():
    e = json.loads(rerun_meta.read_text())["environment"]
    R.note(f"B2 in the saved rerun metadata: git_commit={e['git_commit']!r}, "
           f"git_uncommitted_changes_outside_results={e['git_uncommitted_changes_outside_results']}")

# Dashboard findings sentence vs his saved data.
s = pd.read_csv(TARGET / "results" / "timing_summary.csv")
m = pd.read_csv(TARGET / "results" / "memory_summary.csv")
sentence = report.findings(s, m)[0]
R.note(f"dashboard sentence: {sentence}")
row = s[(s.n == 100000) & (s.q == 100) & (s.hit_rate == "mixed") & (s.method == "binary_v2")]
prep = float(row[row.phase == "prepare"].median_seconds_per_batch.iloc[0]) * 1e3
total = float(row[row.phase == "total"].median_seconds_per_batch.iloc[0]) * 1e3
R.check(prep <= total, f"sorting median {prep:.2f} ms is not larger than the quoted binary total {total:.2f} ms")
R.save()
