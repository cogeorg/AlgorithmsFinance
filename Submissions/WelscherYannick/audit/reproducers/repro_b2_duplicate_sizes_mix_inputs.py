"""B2: a repeated array size merges two different inputs into one summary row.

Usage (from Submissions/WelscherYannick):
    python3 audit/reproducers/repro_b2_duplicate_sizes_mix_inputs.py PATH/TO/Submissions/LaviBen

Equivalent command line in LaviBen's folder:
    python3 benchmark.py --sizes 10,10 --query-counts 1 --scenarios all_present --repeats 2 --output /tmp/dup

The audited code (commit 4777c48) is imported unchanged. Case ids are built
from n, q and scenario only (benchmark.py line 272), but each repeated size
gets its own seed and therefore different data. _summarize matches raw rows by
case id alone (line 362), so each summary row mixes both inputs while still
reporting the configured number of repeats.

Exit code 1 means the bug is present.
"""

import sys

if len(sys.argv) != 2:
    sys.exit(__doc__)
sys.path.insert(0, sys.argv[1])

from benchmark import run_benchmarks  # noqa: E402  (LaviBen's module, unchanged)

run = run_benchmarks((10, 10), (1,), scenarios=("all_present",), repeats=2)

print("Cases (id, seed, input digest):")
for c in run.cases:
    print(f"  {c.case_id}  seed={c.seed}  sha256={c.input_sha256[:12]}")

row = next(s for s in run.summary if s.algorithm == "Linear search")
raw = [r for r in run.raw_results if r.case_id == row.case_id and r.algorithm == row.algorithm]
digests = sorted({r.input_sha256[:12] for r in raw})
print(f"\nSummary row '{row.case_id} / {row.algorithm}' reports repeats={row.repeats}")
print(f"Raw rows with that case id: {len(raw)}, from {len(digests)} different inputs: {digests}")
print(f"Summary rows for linear search: {sum(s.algorithm == 'Linear search' for s in run.summary)} (identical ids)")

print("\nExpected: one summary row per input, built from that input's own repeats.")
if len(digests) > 1:
    print("Actual:   one summary row mixes repeats of two different inputs.\n")
    print("BUG PRESENT: duplicate sizes produce colliding case ids and mixed medians.")
    sys.exit(1)
print("Bug not reproduced.")
