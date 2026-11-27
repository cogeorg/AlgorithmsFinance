# Baseline 100,000-event completion

The starting audit found no Baseline measurements at this size for any required seed.
Revised seed 42 already had five valid completed workloads; its saved audit passed and these results were reused.
Revised seeds 43 and 44 have no saved 100,000-event runs and remain explicitly missing.
The three documented Baseline/sweep memory stops at 10,000 events remain unchanged.

No dashboard previously existed in this checkout. dashboard.html and this report are generated from validated saved records.
The original implementations, runner, generator and test expectations remain unchanged.
All 1170 protected pre-existing files passed SHA-256 preservation checks.

## Protocol and limits

The original 89-test correctness command passed before measurements. Existing tests were not edited.
Final validation passed 99 tests, including ten new reporting/comparability regressions; see report_tests.txt.
All new commands use the unchanged benchmark.py runner with 100000 events, one seed/scenario, Baseline only, and 1000 configured levels.
The existing warm-up, five repetitions, fresh books and separate I/O, timing, latency, memory and diagnostic processes are preserved.
Limits are unchanged: 60 seconds per worker; 900 seconds per command's measurement campaign; 128 MiB input payload and 512 MiB traced allocations.
Preparation is outside the measurement campaign deadline, and memory is measured separately with tracemalloc.
The traced-allocation cap is not an OS RSS cap; loading and warm-up are outside tracing, and the allocation cap is checked between traced events.
Each scenario runs in its own command so the campaign deadline cannot starve later scenarios. Worker conditions match the saved Revised protocol.
Command wall clocks include preparation and every phase. Phase elapsed values are observed stdout completion intervals including parent/checkpoint work; the first also includes preparation.
The worker time limit is never substituted for replay seconds. Null is retained when no complete repetition group exists.

## Actual added outcomes

15 Baseline commands were attempted sequentially.
Sum of command wall times: 2955.860 seconds.

| Seed | Scenario | Command outcome | Command wall, s |
| ---: | --- | --- | ---: |
| 42 | buildup | stopped | 243.084 |
| 42 | crowded | stopped | 242.996 |
| 42 | mixed | stopped | 243.186 |
| 42 | sweep | stopped | 242.815 |
| 42 | cancel_churn | completed | 11.340 |
| 43 | buildup | stopped | 244.045 |
| 43 | crowded | stopped | 243.663 |
| 43 | mixed | stopped | 243.419 |
| 43 | sweep | stopped | 243.451 |
| 43 | cancel_churn | completed | 12.496 |
| 44 | buildup | stopped | 243.703 |
| 44 | crowded | stopped | 243.413 |
| 44 | mixed | stopped | 243.363 |
| 44 | sweep | stopped | 243.357 |
| 44 | cancel_churn | completed | 11.528 |

Phase-job totals: completed=27, failed=0, stopped=48, unattempted=0.

| Seed | Scenario | Phase | Outcome | Repetitions | Observed elapsed, s | Reason |
| ---: | --- | --- | --- | ---: | ---: | --- |
| 42 | buildup | io | completed | 5/5 | 2.924 |  |
| 42 | buildup | timing | stopped | 0/5 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 42 | buildup | latency | stopped | 0/1 | 60.030 | Worker wall limit reached (60.000 seconds) |
| 42 | buildup | memory | stopped | 0/5 | 60.040 | Worker wall limit reached (60.000 seconds) |
| 42 | buildup | diagnostics | stopped | 0/1 | 60.037 | Worker wall limit reached (60.000 seconds) |
| 42 | crowded | io | completed | 5/5 | 2.826 |  |
| 42 | crowded | timing | stopped | 0/5 | 60.039 | Worker wall limit reached (60.000 seconds) |
| 42 | crowded | latency | stopped | 0/1 | 60.037 | Worker wall limit reached (60.000 seconds) |
| 42 | crowded | memory | stopped | 0/5 | 60.036 | Worker wall limit reached (60.000 seconds) |
| 42 | crowded | diagnostics | stopped | 0/1 | 60.040 | Worker wall limit reached (60.000 seconds) |
| 42 | mixed | io | completed | 5/5 | 3.049 |  |
| 42 | mixed | timing | stopped | 0/5 | 60.030 | Worker wall limit reached (60.000 seconds) |
| 42 | mixed | latency | stopped | 0/1 | 60.025 | Worker wall limit reached (60.000 seconds) |
| 42 | mixed | memory | stopped | 0/5 | 60.036 | Worker wall limit reached (60.000 seconds) |
| 42 | mixed | diagnostics | stopped | 0/1 | 60.028 | Worker wall limit reached (60.000 seconds) |
| 42 | sweep | io | completed | 5/5 | 2.647 |  |
| 42 | sweep | timing | stopped | 0/5 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 42 | sweep | latency | stopped | 0/1 | 60.040 | Worker wall limit reached (60.000 seconds) |
| 42 | sweep | memory | stopped | 0/5 | 60.036 | Worker wall limit reached (60.000 seconds) |
| 42 | sweep | diagnostics | stopped | 0/1 | 60.036 | Worker wall limit reached (60.000 seconds) |
| 42 | cancel_churn | io | completed | 5/5 | 2.858 |  |
| 42 | cancel_churn | timing | completed | 5/5 | 1.801 |  |
| 42 | cancel_churn | latency | completed | 1/1 | 1.094 |  |
| 42 | cancel_churn | memory | completed | 5/5 | 4.171 |  |
| 42 | cancel_churn | diagnostics | completed | 1/1 | 1.392 |  |
| 43 | buildup | io | completed | 5/5 | 3.877 |  |
| 43 | buildup | timing | stopped | 0/5 | 60.040 | Worker wall limit reached (60.000 seconds) |
| 43 | buildup | latency | stopped | 0/1 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 43 | buildup | memory | stopped | 0/5 | 60.033 | Worker wall limit reached (60.000 seconds) |
| 43 | buildup | diagnostics | stopped | 0/1 | 60.043 | Worker wall limit reached (60.000 seconds) |
| 43 | crowded | io | completed | 5/5 | 3.514 |  |
| 43 | crowded | timing | stopped | 0/5 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 43 | crowded | latency | stopped | 0/1 | 60.039 | Worker wall limit reached (60.000 seconds) |
| 43 | crowded | memory | stopped | 0/5 | 60.031 | Worker wall limit reached (60.000 seconds) |
| 43 | crowded | diagnostics | stopped | 0/1 | 60.028 | Worker wall limit reached (60.000 seconds) |
| 43 | mixed | io | completed | 5/5 | 3.272 |  |
| 43 | mixed | timing | stopped | 0/5 | 60.021 | Worker wall limit reached (60.000 seconds) |
| 43 | mixed | latency | stopped | 0/1 | 60.044 | Worker wall limit reached (60.000 seconds) |
| 43 | mixed | memory | stopped | 0/5 | 60.039 | Worker wall limit reached (60.000 seconds) |
| 43 | mixed | diagnostics | stopped | 0/1 | 60.025 | Worker wall limit reached (60.000 seconds) |
| 43 | sweep | io | completed | 5/5 | 3.211 |  |
| 43 | sweep | timing | stopped | 0/5 | 60.037 | Worker wall limit reached (60.000 seconds) |
| 43 | sweep | latency | stopped | 0/1 | 60.037 | Worker wall limit reached (60.000 seconds) |
| 43 | sweep | memory | stopped | 0/5 | 60.079 | Worker wall limit reached (60.000 seconds) |
| 43 | sweep | diagnostics | stopped | 0/1 | 60.032 | Worker wall limit reached (60.000 seconds) |
| 43 | cancel_churn | io | completed | 5/5 | 3.468 |  |
| 43 | cancel_churn | timing | completed | 5/5 | 1.989 |  |
| 43 | cancel_churn | latency | completed | 1/1 | 1.106 |  |
| 43 | cancel_churn | memory | completed | 5/5 | 4.582 |  |
| 43 | cancel_churn | diagnostics | completed | 1/1 | 1.331 |  |
| 44 | buildup | io | completed | 5/5 | 3.521 |  |
| 44 | buildup | timing | stopped | 0/5 | 60.039 | Worker wall limit reached (60.000 seconds) |
| 44 | buildup | latency | stopped | 0/1 | 60.038 | Worker wall limit reached (60.000 seconds) |
| 44 | buildup | memory | stopped | 0/5 | 60.043 | Worker wall limit reached (60.000 seconds) |
| 44 | buildup | diagnostics | stopped | 0/1 | 60.038 | Worker wall limit reached (60.000 seconds) |
| 44 | crowded | io | completed | 5/5 | 3.250 |  |
| 44 | crowded | timing | stopped | 0/5 | 60.032 | Worker wall limit reached (60.000 seconds) |
| 44 | crowded | latency | stopped | 0/1 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 44 | crowded | memory | stopped | 0/5 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 44 | crowded | diagnostics | stopped | 0/1 | 60.031 | Worker wall limit reached (60.000 seconds) |
| 44 | mixed | io | completed | 5/5 | 3.209 |  |
| 44 | mixed | timing | stopped | 0/5 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 44 | mixed | latency | stopped | 0/1 | 60.038 | Worker wall limit reached (60.000 seconds) |
| 44 | mixed | memory | stopped | 0/5 | 60.037 | Worker wall limit reached (60.000 seconds) |
| 44 | mixed | diagnostics | stopped | 0/1 | 60.029 | Worker wall limit reached (60.000 seconds) |
| 44 | sweep | io | completed | 5/5 | 3.189 |  |
| 44 | sweep | timing | stopped | 0/5 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 44 | sweep | latency | stopped | 0/1 | 60.045 | Worker wall limit reached (60.000 seconds) |
| 44 | sweep | memory | stopped | 0/5 | 60.034 | Worker wall limit reached (60.000 seconds) |
| 44 | sweep | diagnostics | stopped | 0/1 | 60.038 | Worker wall limit reached (60.000 seconds) |
| 44 | cancel_churn | io | completed | 5/5 | 3.106 |  |
| 44 | cancel_churn | timing | completed | 5/5 | 1.852 |  |
| 44 | cancel_churn | latency | completed | 1/1 | 1.067 |  |
| 44 | cancel_churn | memory | completed | 5/5 | 4.138 |  |
| 44 | cancel_churn | diagnostics | completed | 1/1 | 1.349 |  |

Completed raw repetitions remain in their original run folders. Properly documented stops count as attempted coverage, not completed evidence.

## Comparable results and remaining gaps

| Seed | Scenario | Baseline timing | Revised timing | Speedup B/R | Comparison |
| ---: | --- | --- | --- | ---: | --- |
| 42 | buildup | stopped (0/5) | 0.314934800 s | unavailable | completed groups required |
| 42 | crowded | stopped (0/5) | 0.285689200 s | unavailable | completed groups required |
| 42 | mixed | stopped (0/5) | 0.290096100 s | unavailable | completed groups required |
| 42 | sweep | stopped (0/5) | 0.363932700 s | unavailable | completed groups required |
| 42 | cancel_churn | 0.193283900 s | 0.201017000 s | 0.962 | same inputs, code, Python, machine, limits and protocol; diagnostics match |
| 43 | buildup | stopped (0/5) | missing | unavailable | measurement missing |
| 43 | crowded | stopped (0/5) | missing | unavailable | measurement missing |
| 43 | mixed | stopped (0/5) | missing | unavailable | measurement missing |
| 43 | sweep | stopped (0/5) | missing | unavailable | measurement missing |
| 43 | cancel_churn | 0.203847700 s | missing | unavailable | measurement missing |
| 44 | buildup | stopped (0/5) | missing | unavailable | measurement missing |
| 44 | crowded | stopped (0/5) | missing | unavailable | measurement missing |
| 44 | mixed | stopped (0/5) | missing | unavailable | measurement missing |
| 44 | sweep | stopped (0/5) | missing | unavailable | measurement missing |
| 44 | cancel_churn | 0.204677100 s | missing | unavailable | measurement missing |

A speedup requires identical event count/seed/scenario and workload SHA-256; matching engine/runner/generator hashes; Python, dependencies, machine, clock, GC and limits; complete timing groups; and a complete matching diagnostic pair.
Git revision labels alone are not compared: subsequent data/report commits do not change engine code. Reused Revised source and environment fingerprints are checked directly.
No Baseline result from another event count supplies a large-case speedup. Physical queue/heap storage may differ; common logical diagnostics must agree.
Existing valid completions and documented stops were preserved instead of rerun. Dataset settings and checksums are in every manifest and sidecar.

## Reproduce

The exact executed commands, timestamps, limits and elapsed times are in each new command_wall_time.json and command_output.txt; plan.json identifies the requested missing cases.
Use new output directories for new measurements. The aggregate execution.json records every actual outcome.

~~~console
python -B benchmark_report.py
python -B -m unittest -v test_order_book test_price_heaps test_lazy_cancellation test_benchmark test_benchmark_report
~~~

Open dashboard.html locally. It embeds the audited index, works without a server, and filters counts, seeds, scenarios and phases.
index.json preserves source paths, raw repetitions, summary values, environment/protocol fingerprints, states and reasons.
Remaining limitations are stopped phase groups without complete estimates, missing Revised seeds 43/44, and uncontrolled background machine load.
No implementation, prior result, fixture or existing expected result was changed. Commits and pushes remain under user control.
