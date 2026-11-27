# Findings from executed measurements

Verified 90 primary version/workload configurations.
Saved 2,478 raw/diagnostic rows and 642,536 individual latency samples.
48 timed trials stopped at the declared deadline (across all phases).

Only completed five-repeat replay medians are compared below. Stopped trials are not zeros.

The revised version was faster in 24/33 paired configurations.
Baseline/revised ratios range from 0.88 to 319.11;
the median paired ratio is 26.15. Ratios describe this run only.

| Scenario | Seed | Events | Baseline/revised replay ratio |
| --- | --- | --- | --- |
| buildup | 42 | 1,000 | 24.25 |
| buildup | 42 | 10,000 | 276.25 |
| buildup | 43 | 1,000 | 24.24 |
| buildup | 43 | 10,000 | 248.58 |
| buildup | 44 | 1,000 | 24.98 |
| buildup | 44 | 10,000 | 280.01 |
| cancel_churn | 42 | 1,000 | 0.89 |
| cancel_churn | 42 | 10,000 | 0.91 |
| cancel_churn | 42 | 100,000 | 0.95 |
| cancel_churn | 43 | 1,000 | 0.90 |
| cancel_churn | 43 | 10,000 | 0.92 |
| cancel_churn | 43 | 100,000 | 0.88 |
| cancel_churn | 44 | 1,000 | 0.92 |
| cancel_churn | 44 | 10,000 | 0.90 |
| cancel_churn | 44 | 100,000 | 0.91 |
| crowded | 42 | 1,000 | 29.95 |
| crowded | 42 | 10,000 | 289.45 |
| crowded | 43 | 1,000 | 30.16 |
| crowded | 43 | 10,000 | 271.28 |
| crowded | 44 | 1,000 | 30.54 |
| crowded | 44 | 10,000 | 281.98 |
| mixed | 42 | 1,000 | 4.15 |
| mixed | 42 | 10,000 | 36.96 |
| mixed | 43 | 1,000 | 4.22 |
| mixed | 43 | 10,000 | 38.77 |
| mixed | 44 | 1,000 | 4.33 |
| mixed | 44 | 10,000 | 37.15 |
| sweep | 42 | 1,000 | 26.31 |
| sweep | 42 | 10,000 | 313.66 |
| sweep | 43 | 1,000 | 25.99 |
| sweep | 43 | 10,000 | 317.73 |
| sweep | 44 | 1,000 | 26.15 |
| sweep | 44 | 10,000 | 319.11 |

## Largest seed-42 replay cases

| Scenario | Version | Seconds (median) | Repeats |
| --- | --- | --- | --- |
| buildup | baseline | stopped / no completed timed repeats | 0 |
| buildup | revised | 0.098105 | 5 |
| crowded | baseline | stopped / no completed timed repeats | 0 |
| crowded | revised | 0.093395 | 5 |
| mixed | baseline | stopped / no completed timed repeats | 0 |
| mixed | revised | 0.093447 | 5 |
| sweep | baseline | stopped / no completed timed repeats | 0 |
| sweep | revised | 0.119579 | 5 |
| cancel_churn | baseline | 0.065341 | 5 |
| cancel_churn | revised | 0.068907 | 5 |

## Measured scan bottleneck

Small counter runs are separate from timing. For 1,000-event buildup seed 42:

- baseline: `{"filled_price_levels": 0, "id_scan_upper_bound": 499500, "inserts": 1000, "matching_entries_scanned": 499500}`
- revised: `{"best_price_reads": 995, "id_lookups": 1000, "inserts": 1000, "price_entries_shifted": 77049}`

These counts expose the baseline's repeated scans of a growing book even when no maker fills.
The revision uses indexed validation and checks the best occupied price. Sorted price insertion still shifts entries.

## Post-cancellation allocation

| Events | Version | Current traced bytes | Peak bytes | Active/stored/stale |
| --- | --- | --- | --- | --- |
| 1,000 | baseline | 1,560 | 1,968 | 0/0/0 |
| 1,000 | revised | 1,832 | 2,240 | 0/0/0 |
| 10,000 | baseline | 1,624 | 2,032 | 0/0/0 |
| 10,000 | revised | 1,896 | 2,304 | 0/0/0 |
| 100,000 | baseline | 1,728 | 2,136 | 0/0/0 |
| 100,000 | revised | 1,896 | 2,304 | 0/0/0 |

This is traced engine allocation with preloaded events excluded, not total process memory.
Checkpoint records and the current output are included; allocator capacity need not shrink after every deletion.

## Million-event feasibility

Only cancel_churn, seed 42, was attempted at one million events. Streaming application time includes parsing.

- input parse warmup: ok, 0.828 s.
- baseline streaming_app warmup: ok, 1.489 s.
- revised streaming_app warmup: ok, 1.574 s.
- input parse: 0.822022 s median of 5 repeats.
- baseline streaming_app: 1.508710 s median of 5 repeats.
- revised streaming_app: 1.610197 s median of 5 repeats.

## Interpretation limits

Sequential run order, OS activity, Python version and allocator effects influence these measurements.
No network/queueing latency, overload capacity, confidence intervals or exchange calibration are claimed.
See docs/REPORT.md for measurement boundaries, full complexity qualifications and unattempted work.
