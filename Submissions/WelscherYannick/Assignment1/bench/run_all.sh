#!/bin/sh
# Full reproducible pipeline (about 35 minutes on an Apple M4 Pro). Run from anywhere.
set -e
cd "$(dirname "$0")/.."
python3 bench/make_data.py          # inputs, outside timing; checksums -> results/generated_inputs.json
python3 bench/verify_correctness.py # oracle + A-vs-B after every event -> results/correctness.json
python3 bench/run_timing.py         # replay, warmup + 5 repeats -> results/timing.csv, env.json
python3 bench/run_parse.py          # read+gzip+JSON, warmup + 5 repeats -> results/parse.csv
python3 bench/run_revision_steps.py # B revision steps 1-3 on 100k inputs -> results/revision_steps.csv
python3 bench/run_version_c.py      # experiment: Version C vs B -> results/version_c.json
python3 bench/run_liquidation.py    # 10/100/200% sells on fresh books -> results/liquidation.csv
python3 bench/run_latency.py        # per-event latency percentiles -> results/latency.json
python3 bench/run_memory.py         # tracemalloc -> results/memory.csv
python3 bench/run_counts.py         # operation counts (separate from timing) -> results/op_counts.csv
python3 bench/run_profile.py        # cProfile hot spots (separate run) -> results/profile.json
python3 bench/run_mutations.py      # 20 injected bugs vs unchanged tests -> results/mutations.json
python3 bench/run_gc_check.py       # diagnostic: GC on vs off for B (1M buildup) -> results/gc_check.json
python3 bench/summarize.py          # key tables quoted in REPORT.md -> results/summary.md
python3 dashboard/build.py          # dashboard/index.html from the saved results only
