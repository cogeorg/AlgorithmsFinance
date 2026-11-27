# Targeted comparison after identifier validation

On 23 November 2026, both current implementations replayed the same 15 workloads: five scenarios, 10,000 events, and seeds 42, 43 and 44. All **15 separate correctness checks passed**, comparing every ordered event result and the final canonical book. All **30 warm-ups, 150 timed replays, and 30 latency runs completed**. Four of 30 separate memory runs stopped; they do not affect the completed replay results.

## Replay results

Each number below is the median of three seed-specific medians; each seed-specific median is based on five timed repetitions after a warm-up. Speedup is the ratio of those two displayed scenario medians, A/B. Throughput is 10,000 divided by the corresponding scenario median, rounded to the nearest event per second. Per-seed raw results, median and throughput are in `runs.csv`.

| Scenario | A median (s) | B median (s) | A / B | A events/s | B events/s | Replay status |
|---|---:|---:|---:|---:|---:|---|
| buildup | 9.395343 | 0.032185 | 291.9× | 1,064 | 310,702 | all completed |
| crowded | 15.984131 | 0.030683 | 520.9× | 626 | 325,915 | all completed |
| mixed | 1.459713 | 0.034120 | 42.8× | 6,851 | 293,087 | all completed |
| sweep | 21.022947 | 0.053545 | 392.6× | 476 | 186,757 | all completed |
| cancel churn | 0.028604 | 0.036132 | 0.79× | 349,598 | 276,764 | all completed |

Version B was faster in the first four scenarios. Sweep remained the slowest replay for both versions, while Version A was faster under cancellation churn, whose active book stays very small. These observations support the rationale for indexing a growing book and finding makers without repeated full-list scans, but do not establish that Version B wins on every workload or machine.

## Method and memory

The timeout was 120 seconds per phase, applied to both versions by terminating a child process even if it was inside an event. Input loading had a separate 60-second limit; no process-memory cap was imposed. Every timed replay used a fresh book and excluded input loading, generation, tracing, and per-event latency measurement. Compared with the previous run, a shared progress value is updated once per 100 completed events instead of every event. This small progress and loop overhead remains in replay timing; a stopped run's recorded event count is a lower bound, up to 99 events behind.

Latency is measured separately per event, grouped by type, with median and nearest-rank p95/p99 in microseconds; absent event types have no measurement. Throughput is event count divided by replay median and does not describe the distribution of per-event latency. Input parsing time is recorded separately in `runs.csv`.

Tracing starts after inputs are loaded. It includes live book structures, the retained event output, and instrumentation; A counts active price levels using temporary sets and B wraps the cleanup method to count rebuilds. Peak traced allocations are therefore not directly comparable as pure book memory and are not total process memory. For seed 42, crowded peaked at 1,920,824 traced bytes for A and 2,251,768 for B; mixed peaked at 394,400 and 687,504 bytes. Churn peaked at 776 and 1,472 bytes respectively; B ended with zero heap entries and 5,000 rebuilds. These examples suggest additional indexed-structure overhead, but instrumentation differences limit attribution.

Four A memory runs stopped at the 120-second limit: buildup seeds 42 and 44, and sweep seeds 42 and 43. Their processed lower bounds were 9,700, 9,500, 9,300 and 9,100 events respectively. No completed memory values are inferred for them. The remaining 26 memory runs completed. Heap sizes, stale entries and rebuild counts for B are in `memory.csv`.

## Files and reproducibility

Raw measurements and source/input hashes are in `40_Results/targeted_comparison_20261123_175037/`. Reproduce from the project root with `python -B 20_Code/targeted_benchmark.py`. It uses the unchanged instructor generator and saved streams, writes a new timestamped results directory, and does not modify the dashboard. `environment.json` records Python, machine, source hashes, generator settings and measurement boundaries.

Verification found 15 matching A/B input fingerprints and settings, all recorded medians matched raw repeats, the code hashes matched the beginning-of-run record, and instructor files matched the original manifest. Earlier results were preserved. The CSV schema follows the previous full comparison (`runs.csv`, `latency.csv`, `memory.csv`); the existing diagnostic dashboard expects different input filenames and will require an adapter before it can load this run. No dashboard changes were made.
