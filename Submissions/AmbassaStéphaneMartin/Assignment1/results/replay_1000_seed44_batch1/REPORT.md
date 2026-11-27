# Replay batch: 1000 events, seed 44

Campaign status: complete. Audit: passed.
Total command wall time: 14.436778 seconds.
The wall time includes process startup and workload preparation; engine clocks use the original boundaries.
Jobs: 45 complete, 0 stopped, 0 unattempted, 0 failed.
Limits: 60 seconds per worker, 900 seconds per measurement campaign, 128 MiB input payload and 512 MiB traced allocations.
Workload preparation is outside the measurement campaign deadline. Limits apply equally to both versions.
The existing warm-up, five repetitions, fresh books, and separate I/O, timing, latency, memory and diagnostics phases were retained.

## Reproduce

Use a new output directory to preserve this saved run.

~~~console
python -B benchmark.py run --counts 1000 --seeds 44 --scenarios buildup crowded mixed sweep cancel_churn --experiments replay --versions baseline revised --levels 1000 --out results/replay_1000_seed44_batch1_repeat --worker-seconds 60 --campaign-seconds 900 --label remaining-small-replay
python -B results/replay_1000_seed44_batch1/audit.py
~~~

## Timing and diagnostics

Primary medians below use only complete five-repetition groups with matching diagnostic pairs.
Throughput is event count divided by replay seconds; initialization and total compute remain separately saved in raw.jsonl and summaries.jsonl.

| Scenario | Baseline replay, ms | Revised replay, ms | Baseline events/s | Revised events/s | B/R ratio | Diagnostic pair |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| buildup | 55.256700 | 2.748700 | 18097.4 | 363808.3 | 20.103 | passed |
| crowded | 56.608000 | 2.298300 | 17665.3 | 435104.2 | 24.630 | passed |
| mixed | 10.332700 | 2.399900 | 96780.1 | 416684.0 | 4.305 | passed |
| sweep | 63.537200 | 3.101300 | 15738.8 | 322445.4 | 20.487 | passed |
| cancel_churn | 1.787300 | 1.872800 | 559503.1 | 533959.8 | 0.954 | passed |

Missing diagnostic comparisons: 0. Failed comparisons: 0.

## Memory completion and separate instrumentation

| Scenario | Version | Memory repetitions | Peak-byte median | Current-byte median |
| --- | --- | ---: | ---: | ---: |
| buildup | baseline | 5/5 | 194400 | 193224 |
| buildup | revised | 5/5 | 958728 | 958024 |
| crowded | baseline | 5/5 | 194400 | 193224 |
| crowded | revised | 5/5 | 227232 | 226560 |
| mixed | baseline | 5/5 | 33104 | 31768 |
| mixed | revised | 5/5 | 192272 | 191408 |
| sweep | baseline | 5/5 | 156240 | 81240 |
| sweep | revised | 5/5 | 785192 | 426696 |
| cancel_churn | baseline | 5/5 | 1904 | 424 |
| cancel_churn | revised | 5/5 | 3480 | 1672 |

Incomplete jobs:

- None.

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
