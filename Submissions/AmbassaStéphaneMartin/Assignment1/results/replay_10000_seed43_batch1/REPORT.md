# Replay batch: 10000 events, seed 43

Campaign status: incomplete. Audit: passed.
Total command wall time: 387.395641 seconds.
The wall time includes process startup and workload preparation; engine clocks use the original boundaries.
Jobs: 44 complete, 1 stopped, 0 unattempted, 0 failed.
Limits: 60 seconds per worker, 900 seconds per measurement campaign, 128 MiB input payload and 512 MiB traced allocations.
Workload preparation is outside the measurement campaign deadline. Limits apply equally to both versions.
The existing warm-up, five repetitions, fresh books, and separate I/O, timing, latency, memory and diagnostics phases were retained.

## Reproduce

Use a new output directory to preserve this saved run.

~~~console
python -B benchmark.py run --counts 10000 --seeds 43 --scenarios buildup crowded mixed sweep cancel_churn --experiments replay --versions baseline revised --levels 1000 --out results/replay_10000_seed43_batch1_repeat --worker-seconds 60 --campaign-seconds 900 --label remaining-small-replay
python -B results/replay_10000_seed43_batch1/audit.py
~~~

## Timing and diagnostics

Primary medians below use only complete five-repetition groups with matching diagnostic pairs.
Throughput is event count divided by replay seconds; initialization and total compute remain separately saved in raw.jsonl and summaries.jsonl.

| Scenario | Baseline replay, ms | Revised replay, ms | Baseline events/s | Revised events/s | B/R ratio | Diagnostic pair |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| buildup | 5202.065300 | 27.082200 | 1922.3 | 369246.2 | 192.084 | passed |
| crowded | 5317.558300 | 24.248700 | 1880.6 | 412393.2 | 219.293 | passed |
| mixed | 808.749700 | 28.311000 | 12364.8 | 353219.6 | 28.567 | passed |
| sweep | 6270.693700 | 31.447400 | 1594.7 | 317991.3 | 199.403 | passed |
| cancel_churn | 18.991700 | 19.418700 | 526545.8 | 514967.5 | 0.978 | passed |

Missing diagnostic comparisons: 0. Failed comparisons: 0.

## Memory completion and separate instrumentation

| Scenario | Version | Memory repetitions | Peak-byte median | Current-byte median |
| --- | --- | ---: | ---: | ---: |
| buildup | baseline | 5/5 | 1926720 | 1925544 |
| buildup | revised | 5/5 | 3823656 | 3822952 |
| crowded | baseline | 5/5 | 1926720 | 1925544 |
| crowded | revised | 5/5 | 2138992 | 2138320 |
| mixed | baseline | 5/5 | 318568 | 313240 |
| mixed | revised | 5/5 | 1072568 | 1061728 |
| sweep | baseline | 3/5 | unavailable | unavailable |
| sweep | revised | 5/5 | 3437824 | 1881376 |
| cancel_churn | baseline | 5/5 | 1904 | 424 |
| cancel_churn | revised | 5/5 | 3480 | 1672 |

Incomplete jobs:

- replay_sweep_n10000_s43_l1000 / baseline / memory: stopped; 3/5 complete. Worker wall limit reached (60.000 seconds)

Finished repetitions are preserved. Incomplete groups have null summary measurements; no five-repeat median is invented.
A worker timeout includes loading, warm-up and repetitions and is not a single-replay timing.
Memory comparisons require complete groups on both versions; incomplete memory groups are excluded.
Latency samples, P95/P99 nearest-rank statistics, I/O components, book initialization and active/occupied-price peaks remain available in their separate phase records.
price_levels_visited is null for ordinary replay by definition.

## Preservation and verification

All source fingerprints match the unchanged checkout. Existing datasets and previous results passed the recorded pre-run SHA-256 checks.
5 generated workloads were checked against the supplied generator and sidecar checksums.
Input prices and quantities remain positive built-in integers in cents per BTC and 10^-8 BTC; sequences remain positive increasing built-in integers.
audit.py validates the raw calculations, all summary medians, stopped/null fields, checkpoint recovery, latency samples, memory records, workload checksums and all available diagnostic pairs.
See audit.json, before_checks.json, command_wall_time.json and command_output.txt.
