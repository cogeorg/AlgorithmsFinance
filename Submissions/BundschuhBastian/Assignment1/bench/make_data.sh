#!/usr/bin/env bash
# Generate ALL benchmark event streams, outside any timing, and record checksums.
#
#   bench/make_data.sh                 # everything (about 2-3 minutes, ~120 MB in data/generated/)
#   bench/make_data.sh --no-million    # skip the five 1,000,000-event files
#   bench/make_data.sh --force         # regenerate files that already exist
#   PYTHON=python3 bench/make_data.sh  # other interpreter (default: .venv/bin/python)
#
# Streams (file name = scenario_events_sSEED[_Llevels].jsonl.gz, all in data/generated/):
#   grid          5 scenarios x M in {1000, 10000, 100000} x seeds {42, 43, 44}
#   million       5 scenarios x M = 1000000, seed 42          (the assignment says "try 1e6")
#   concentration buildup, M = 100000, seed 42, --levels in {4, 16, 64, 256, 4000}
#                 (the grid file buildup_100000_s42 is the 1000-level case). Same order count,
#                 fewer prices = longer queues per price.
# Afterwards results/generated_data_checksums.json gets the sha256 of every .gz AND of the
# decompressed content (the .gz hash depends on the zlib version, the decompressed one does not).
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-.venv/bin/python}"
OUT=data/generated
MILLION=1
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --no-million) MILLION=0 ;;
    --force)      FORCE=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
mkdir -p "$OUT"

make_one() {  # scenario events seed levels name
  local scenario=$1 events=$2 seed=$3 levels=$4 name=$5
  local path="$OUT/$name.jsonl.gz"
  if [[ -f "$path" && -f "$path.metadata.json" && $FORCE -eq 0 ]]; then
    echo "keep      $name"
    return
  fi
  "$PY" generate_orders.py --scenario "$scenario" --events "$events" --levels "$levels" \
        --seed "$seed" --out "$path" > /dev/null
  echo "generated $name"
}

SCENARIOS="buildup crowded mixed sweep cancel_churn"

for scenario in $SCENARIOS; do
  for events in 1000 10000 100000; do
    for seed in 42 43 44; do
      make_one "$scenario" "$events" "$seed" 1000 "${scenario}_${events}_s${seed}"
    done
  done
done

if [[ $MILLION -eq 1 ]]; then
  for scenario in $SCENARIOS; do
    make_one "$scenario" 1000000 42 1000 "${scenario}_1000000_s42"
  done
fi

for levels in 4 16 64 256 4000; do
  make_one buildup 100000 42 "$levels" "buildup_100000_s42_L${levels}"
done

"$PY" tools/hash_generated.py --write
