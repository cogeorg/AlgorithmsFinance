# Remaining small replay batches: seeds 43 and 44

Only the four requested batches ran, in order, with no overlap. The required 89-test suite passed before the first batch.
There were 20 workload cases across five scenarios, each processed by both implementations (40 version cases).
Source revision: c3e27f9f5154a888b4faaa32381d4c1fa0e4a574. Source files and measurement methodology remained unchanged.
All 607 previously existing project/data/result files passed preservation checks, including the seed-42 results.

## Batch completion and wall time

| Events | Seed | Command wall, s | Complete jobs | Stopped | Unattempted | Failed |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1000 | 43 | 14.387342 | 45 | 0 | 0 | 0 |
| 1000 | 44 | 14.436778 | 45 | 0 | 0 | 0 |
| 10000 | 43 | 387.395641 | 44 | 1 | 0 | 0 |
| 10000 | 44 | 387.707504 | 44 | 1 | 0 | 0 |

Sum of command wall times: 803.927266 seconds (13.40 minutes).
Each external perf_counter wall time includes startup and workload generation, all five phases, warm-ups and repetitions.
The sum excludes test execution, audits, documentation and gaps between batches. It is not an engine replay measurement.
Limits stayed at 60 seconds per worker and 900 seconds per measurement campaign, with preparation outside the campaign deadline.
The existing 128 MiB payload and 512 MiB tracemalloc caps were retained for both versions.

## Results by scenario and seed

Cells show Baseline / Revised median replay milliseconds. Every displayed pair has five complete repetitions per version and a matching diagnostic pair.
Unavailable or incomplete groups are not compared.

| Scenario | 1000, seed 43 | 1000, seed 44 | 10000, seed 43 | 10000, seed 44 |
| --- | ---: | ---: | ---: | ---: |
| buildup | 53.339 / 2.897 | 55.257 / 2.749 | 5202.065 / 27.082 | 5210.952 / 25.985 |
| crowded | 55.984 / 2.454 | 56.608 / 2.298 | 5317.558 / 24.249 | 5333.202 / 25.405 |
| mixed | 9.269 / 2.419 | 10.333 / 2.400 | 808.750 / 28.311 | 767.451 / 26.826 |
| sweep | 63.947 / 3.206 | 63.537 / 3.101 | 6270.694 / 31.447 | 6325.530 / 32.229 |
| cancel_churn | 1.844 / 1.842 | 1.787 / 1.873 | 18.992 / 19.419 | 17.906 / 18.699 |

Per-batch REPORT.md files include throughput and memory completion tables. Raw and summary JSON Lines preserve initialization, total compute, latency, memory and diagnostic fields separately.
Latency uses one separately instrumented pass and nearest-rank P95/P99. Tracemalloc runs in separate workers, excluding preloaded inputs and including book construction and transient results; no history is saved.

## Diagnostics and incomplete measurements

Available matching diagnostic pairs: 20. Missing pairs: 0. Failed pairs: 0.
Diagnostic checks include ordered result and canonical-book digests, quantities/fills/rejections, and common active-order/occupied-price peaks and final counts.

- 10000 events, seed 43, replay_sweep_n10000_s43_l1000 / baseline / memory: stopped, 3/5 repetitions retained; Worker wall limit reached (60.000 seconds).
- 10000 events, seed 44, replay_sweep_n10000_s44_l1000 / baseline / memory: stopped, 3/5 repetitions retained; Worker wall limit reached (60.000 seconds).

Incomplete groups retain their complete raw repetitions and explicit stopped/unattempted records; summary measurements remain null.
A 60-second worker timeout includes loading, warm-up and repetitions. It is not treated as a single replay, and no complete median is fabricated.
The validated seed-42 Baseline/sweep memory group remains incomplete at 3/5 with null summary memory values; its saved files are unchanged.

## Reproduce the audits

Run from the Assignment1 directory. Audits read the recorded data and do not launch benchmarks.

~~~console
python -B results/replay_1000_seed43_batch1/audit.py
python -B results/replay_1000_seed44_batch1/audit.py
python -B results/replay_10000_seed43_batch1/audit.py
python -B results/replay_10000_seed44_batch1/audit.py
~~~

before_checks.json records the pre-run checksums and passing test gate. Each audit verifies current source hashes, workload bytes, generator replay, strict integer inputs, timestamps before measurement, repetition counts, calculations, medians and checkpoint exports.
20 newly generated datasets were saved under data/benchmark with checksum sidecars. Existing datasets were preserved.
all_batches.json contains the combined machine-readable report. command_wall_time.json in each directory records the exact command and timing boundary.
No 100000-event runs, complementary experiments, dashboard, commits or pushes were performed.
