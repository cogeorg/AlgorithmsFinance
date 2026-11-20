#!/usr/bin/env bash
# Runs inside the container started by run_audit.sh. Writes only into ./logs and /tmp.
set -euo pipefail
LOGS="$(pwd)/logs"
TARGET=/repo/Submissions/BundschuhBastian

python --version | tee "$LOGS/python_version.txt"
pip install -q --no-cache-dir -r "$TARGET/requirements.txt" 2>&1 | tail -1 || true

# His tests, in a temporary copy so nothing is written into his folder.
rm -rf /tmp/bastian && cp -r "$TARGET" /tmp/bastian
(cd /tmp/bastian && python -m pytest -q -p no:cacheprovider) > "$LOGS/his_tests.txt" 2>&1 || true
tail -1 "$LOGS/his_tests.txt"

# Independent checks.
python fuzz_methods.py > /dev/null && tail -1 "$LOGS/fuzz_methods.txt"
python finding_1_public_method.py > /dev/null && tail -1 "$LOGS/finding_1_public_method.txt"
python check_claims.py > /dev/null && tail -1 "$LOGS/check_claims.txt"

# Rerun his timing pipeline in the copy, then compare with his saved results.
(cd /tmp/bastian && python bench_time.py && python check_total.py) > "$LOGS/rerun_bench_time.txt" 2>&1
mkdir -p "$LOGS/rerun_results" && cp /tmp/bastian/results/timing_*.* /tmp/bastian/results/total_consistency.csv "$LOGS/rerun_results/"
python compare_rerun.py "$LOGS/rerun_results" > /dev/null && tail -1 "$LOGS/compare_rerun.txt"
python finding_2_bugs.py > /dev/null && tail -1 "$LOGS/finding_2_bugs.txt"
echo "done: see logs/"
