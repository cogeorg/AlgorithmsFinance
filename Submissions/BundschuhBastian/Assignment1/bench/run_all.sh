#!/usr/bin/env bash
# All Phase 6 benchmarks, one after the other (never in parallel: they would disturb each other's
# timings). Resumable: finished runs are skipped. Leave the machine idle while this runs.
#   bash bench/run_all.sh             # everything
#   bash bench/run_all.sh quick       # only the first steps that need no long runs
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
mkdir -p results
"$PY" -m bench.peaks
"$PY" -m bench.correctness
[[ "${1:-}" == "quick" ]] && exit 0
"$PY" -m bench.bench_time              # Phase 6a: primary timing (writes results/env.json too)
"$PY" -m bench.bench_counts              # separate instrumented runs follow
"$PY" -m bench.bench_memory
"$PY" -m bench.bench_latency
"$PY" -m bench.liquidation              # Phase 6c from here
"$PY" -m bench.bench_concentration
"$PY" -m bench.bench_churn
"$PY" -m bench.bench_flood
"$PY" -m bench.bench_fairness
"$PY" -m pytest -q > results/pytest_summary.txt 2>&1 || true
echo "done"
