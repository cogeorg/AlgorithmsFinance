# First 10,000-event replay batch

Code revision: c8640308742f5fbd05253d3082455d569239c6c0. The checkout was clean before execution.
The runner, engine, tests, generator, README, workloads and previous results were preserved.
All 496 pre-existing project/data/result files passed SHA-256 preservation checks.
New result files make the recorded working tree dirty; recorded source hashes match the unchanged code.

## Test gate and command

The required test command passed 89 tests with no failures or errors (0.943 seconds within unittest).
The benchmark was launched only after this passed. The full log is correctness_tests.txt.

~~~console
python -B -m unittest -v test_order_book test_price_heaps test_lazy_cancellation test_benchmark
python -B benchmark.py run --counts 10000 --seeds 42 --scenarios buildup crowded mixed sweep cancel_churn --experiments replay --versions baseline revised --levels 1000 --out results/replay_10000_seed42_batch1 --worker-seconds 60 --campaign-seconds 900 --label first-10000-batch
~~~

The output directory was new. All five supplied 10,000-event seed-42 datasets were reused after checksum checks.
Market prices and quantities remained positive built-in integers in cents per BTC and 10^-8 BTC units; sequences were increasing positive built-in integers.

## Wall time, limits and completion

Total benchmark command wall time: **388.028753 seconds (6.47 minutes)**.
This external perf_counter measurement surrounds command process creation through process exit.
It includes Python startup, workload preparation, all workers/warm-ups/repetitions/phases and runner output.
It excludes the test gate, audit and report writing. It is distinct from engine replay timing.
See command_wall_time.json and command_output.txt.

The per-worker wall cap was 60 seconds, including input loading, warm-up and all repetitions.
The measurement campaign cap was 900 seconds and excludes workload preparation.
Payload limits remained 128 MiB compressed/decoded, and the separate traced-allocation cap remained 512 MiB.

| Job outcome | Count |
| --- | ---: |
| complete | 44 |
| stopped | 1 |
| unattempted | 0 |
| failed | 0 |

The campaign is **incomplete**, exit code 2, because sweep/Baseline/memory reached its worker wall limit.
That worker retained 3 of 5 completed repetitions. Repetitions 4 and 5 are labelled stopped with null metrics.
There are 143 complete raw records and 2 stopped raw records across 145 raw records / 45 summaries.
No five-repetition memory median is available for sweep/Baseline, and none was fabricated.
The 60-second worker limit is not a single replay duration and is not divided by repetitions to estimate one.
Every other phase completed, including all ten primary timing jobs (five repetitions each).

## Primary timing

Medians use only complete five-repetition groups. Events are preloaded; direct engine execution, initialization and replay use the existing perf_counter boundaries.
Initialization is separate; replay total compute is initialization plus replay, calculated per repetition before taking the median.
Canonical inspection, diagnostic counters, latency sampling, tracemalloc, startup, loading and preparation are outside primary timing.

| Scenario | Version | Init median, us | Replay median, s | Events/s | Total compute median, s |
| --- | --- | ---: | ---: | ---: | ---: |
| buildup | baseline | 2.900 | 5.231033100 | 1911.7 | 5.231035500 |
| buildup | revised | 4.400 | 0.025500100 | 392155.3 | 0.025504500 |
| crowded | baseline | 4.200 | 5.341705100 | 1872.1 | 5.341710900 |
| crowded | revised | 3.900 | 0.025427700 | 393271.9 | 0.025431600 |
| mixed | baseline | 3.200 | 0.762378200 | 13116.8 | 0.762381300 |
| mixed | revised | 4.200 | 0.028049000 | 356518.9 | 0.028052300 |
| sweep | baseline | 3.100 | 6.349201600 | 1575.0 | 6.349203300 |
| sweep | revised | 4.500 | 0.030827000 | 324391.0 | 0.030831000 |
| cancel_churn | baseline | 2.500 | 0.018697900 | 534819.4 | 0.018700400 |
| cancel_churn | revised | 3.800 | 0.018748400 | 533378.8 | 0.018752400 |

Both timing groups are complete and the diagnostic pair matches in every scenario, so their primary medians are comparable.

| Scenario | Baseline replay / Revised replay |
| --- | ---: |
| buildup | 205.138 |
| crowded | 210.074 |
| mixed | 27.180 |
| sweep | 205.962 |
| cancel_churn | 0.997 |

Ratios describe this workload and machine. The supplied cancel_churn stream peaks at one active order; its two replay medians are roughly equal.

## Separate latency and memory phases

Each latency job contains 10,000 separately instrumented event samples. Median uses the average middle pair; P95/P99 use nearest rank without interpolation.
Memory is incremental tracemalloc allocation in a separate worker: preloaded inputs/imports are excluded, while construction, engine/transient result allocations and cleanup are included.
No saved result history is included. Current bytes are sampled after GC with the book alive. These are Python allocations rather than process RSS.

| Scenario | Version | Latency median, us | P95, us | P99, us | Memory repetitions | Peak bytes median | Current bytes median |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| buildup | baseline | 508.800 | 992.100 | 1501.400 | 5/5 | 1926720 | 1925544 |
| buildup | revised | 2.500 | 4.000 | 5.600 | 5/5 | 3814312 | 3813608 |
| crowded | baseline | 521.600 | 1041.400 | 1622.100 | 5/5 | 1926720 | 1925544 |
| crowded | revised | 2.400 | 4.000 | 5.800 | 5/5 | 2138992 | 2138320 |
| mixed | baseline | 46.500 | 250.000 | 489.600 | 5/5 | 308984 | 305296 |
| mixed | revised | 2.500 | 5.200 | 9.400 | 5/5 | 1150096 | 1143272 |
| sweep | baseline | 417.900 | 2382.100 | 4974.800 | 3/5 | unavailable | unavailable |
| sweep | revised | 2.400 | 10.000 | 21.800 | 5/5 | 3432688 | 1865776 |
| cancel_churn | baseline | 2.000 | 2.600 | 3.200 | 5/5 | 1904 | 424 |
| cancel_churn | revised | 2.200 | 2.700 | 3.600 | 5/5 | 3480 | 1672 |

Sweep memory is not compared between versions because Baseline lacks a complete group. No partial-memory median is presented as a five-repetition result.

## Diagnostics and audit

All five diagnostic comparisons passed. **Missing comparisons: 0. Failed comparisons: 0.**
Ordered-result and canonical-book digests, fill counts, residuals, cancelled quantities, rejected counts and the applicable/null price-level metric agree.
No workload event was rejected. price_levels_visited is null throughout this replay campaign because it is defined for controlled single-sale experiments.

| Scenario | Active-order peak | Occupied-price peak | Maker fills | Comparison |
| --- | ---: | ---: | ---: | --- |
| buildup | 10000 | 1977 | 0 | passed |
| crowded | 10000 | 8 | 0 | passed |
| mixed | 1588 | 752 | 3926 | passed |
| sweep | 8000 | 1959 | 5035 | passed |
| cancel_churn | 1 | 1 | 0 | passed |

The independent saved-data audit checks workload checksums and integer fields, source hashes, repetition counts, surviving checkpoints, I/O sums, throughput, total-compute sums, all summary medians, individual latency samples and their percentiles, memory validity and complete diagnostic pairs.
Completed checkpoint rows match exported raw rows. Incomplete groups keep null summary measurements.

~~~console
python -B results/replay_10000_seed42_batch1/audit.py
~~~

See audit.json, before_checks.json and the unchanged raw.jsonl / summaries.jsonl for the full evidence.

## Estimate for the remaining replay matrix

No additional campaign was started. The scope below excludes complementary experiments and a retry of this stopped memory worker.
It covers the seven untouched replay batches: 1000/43,44; 10000/43,44; 100000/42,43,44 (35 workload cases, both versions).
Assumptions: same machine/load, runner, five scenarios, 1000 price-setting parameter, warm-up/five repetitions and phase boundaries.
Seed-dependent depth can change runtime. Ranges are planning envelopes, not confidence intervals.

| Remaining group | Batches | Estimated total capped-attempt time |
| --- | ---: | ---: |
| 1000 events, seeds 43,44 | 2 | 0.4-0.7 min |
| 10000 events, seeds 43,44 | 2 | 10.3-19.4 min |
| 100000 events, seeds 42,43,44 | 3 | about 45 min |

Estimated total: **55.7-65.1 minutes**, plus unmeasured missing-dataset preparation and verification.
The small-batch estimate uses the prior 14.24-second smoke measurement span (0.8-1.5x); the remaining 10,000-event batches use this 388.03-second command (0.8-1.5x).
For 100,000 events, quadratic Baseline growth in the four growing-depth scenarios projects enough 60-second worker stops to exhaust each 900-second campaign window.
Those three roughly 15-minute attempts are expected to be incomplete and may leave later jobs unattempted. Preparation is outside those windows.

This is an estimate for attempts under the present caps, not for obtaining all complete measurements.
If quadratic scaling continues, Baseline primary timing alone (warm-up plus five replays across the four growing-depth scenarios) extrapolates to 2.95 hours per 100,000-event seed, or 8.84 hours for three seeds.
That separate uncapped extrapolation uses only completed replay timings and excludes latency, memory, diagnostics and preparation, which add further work.
The timed-out memory worker supplies no complete full-worker duration; a full uncapped campaign estimate remains uncertain.
See forecast.json for the formulas and assumptions. No larger batch, other seed, complementary experiment or dashboard was run.
