#!/usr/bin/env bash
# Reproduce everything from a clean checkout (run from this folder):
#     bash run_all.sh            # full run, about 40 to 60 minutes on a laptop
#     bash run_all.sh --quick    # smaller grid, a few minutes
# Results go to results/, test logs to evidence/. The dashboard is started separately:
#     streamlit run dashboard.py
set -euo pipefail
cd "$(dirname "$0")"
QUICK=""
[ "${1:-}" = "--quick" ] && QUICK="--quick"

echo "== 1. data (generated outside timing; checksums in data/generated_manifest.json)"
python make_data.py > /dev/null && echo "datasets ready"
echo "== 2. tests"
python -m pytest -q -p no:cacheprovider tests | tee evidence/final_tests.txt | tail -1
echo "== 3. timing experiments"
python -m bench.experiments $QUICK
echo "== 4. latency, memory and operation counts (separate runs)"
python -m bench.instrumentation $QUICK
echo "== 5. profiling (diagnostic)"
python -m bench.profile_run
echo "done: see results/ and run 'streamlit run dashboard.py'"
