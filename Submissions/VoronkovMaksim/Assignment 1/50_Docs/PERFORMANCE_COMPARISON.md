# Version A vs. Version B — Performance Comparison

This is a bounded comparative run, not a complete set of finished measurements. On 23 November 2026, five workload families, three event counts, and seeds 42, 43 and 44 produced 45 input streams and 90 version/workload configurations. The unchanged instructor generator used 1,000 available levels; the supplied 10,000-event, seed-42 streams were reused. Input SHA-256 values, code hashes, machine and Python details, and exact statuses are in `40_Results/full_comparison_20261123_171219/`.

Each replay or separate diagnostic was limited to **10 seconds of wall time** after input loading, for both versions. A child process was terminated if the limit expired, including during a single event. Loading had a separate 60-second limit. No process-memory limit was enforced. Timed replay includes a shared progress-counter write per event; generation, loading, tracing and per-event latency instrumentation are outside replay timing. Five raw repeats and their median are reported only when all five finish. Reading/parsing times are saved separately. One warm-up precedes timing. A stopped warm-up means no timed repeats were started for that configuration.

Correctness was checked before timing in a separate combined run. All ordered event results and final books were compared; 1,000-event streams additionally compared full state after every event. **24 of 45 checks completed and matched; 21 were stopped** at the limit. Stopped checks leave full equivalence unverified for those workloads, even where Version B replay measurements finished. Existing correctness tests also passed before this benchmark; they do not establish correctness of every larger stream.

## Completed, verified replay measurements

The table shows the median across the three seed-specific replay medians, in seconds. Each seed-specific median uses five raw repetitions. Only workloads with completed correctness checks are shown.

| Scenario | Events | Version A | Version B |
|---|---:|---:|---:|
| buildup | 1,000 | 0.047390 | 0.006396 |
| crowded | 1,000 | 0.063398 | 0.005613 |
| mixed | 1,000 | 0.011073 | 0.003454 |
| mixed | 10,000 | 1.113735 | 0.023417 |
| sweep | 1,000 | 0.074626 | 0.006110 |
| cancel churn | 1,000 | 0.002154 | 0.002476 |
| cancel churn | 10,000 | 0.022174 | 0.022684 |
| cancel churn | 100,000 | 0.204922 | 0.275947 |

Version B improved these growing-book and mixed examples, but was slower on cancellation churn, where the active book stays tiny and maintaining indices and heaps has overhead. These measurements do not prove universal superiority. Earlier Version A diagnostics motivated the revision: buildup latency increased as the book grew, and sweep repeatedly scanned the list for makers. Version B indexes orders by ID and groups them at exact prices, with heaps for best-price lookup; its cleanup and dictionary operations also have costs.

For mixed 10,000 seed 42, separate per-event runs measured cancellation median/p95/p99 of 44.9/117.4/231.7 µs for A and 1.6/3.5/4.9 µs for B; market-sell values were 124.4/523.0/997.6 µs and 3.6/12.1/20.4 µs. Percentiles use nearest rank, `ceil(p*n)`. Throughput in `runs.csv` is events divided by the median replay seconds; latency is measured per event in a separate run and cannot be inferred from reciprocal throughput. Early/late LIMIT samples are recorded for each stream; interpret them as buildup comparisons only for buildup.

## Controlled trials and memory

Controlled trials built identical 1,000-order bid books before every sell, compared both results and final books, and timed construction separately. At four price levels the median 100% sell took 0.126916 s for A and 0.002272 s for B; at 1,000 levels it took 0.117547 s and 0.002453 s. Each filled 1,000 makers. The 200% sell filled the available 10,000 units and returned 10,000 unfilled. At four versus 1,000 levels, cancelling the last order had A medians of 59 versus 72 µs and B medians of 9 versus 10 µs. `controlled.csv` retains all five repeats, construction times, fills and distinct prices. Fill and price counts are observed operation counts; individual examined-order counts were not instrumented.

In separate `tracemalloc` runs, inputs were loaded before tracing. Traced memory includes the book, retained current event result, and measurement instrumentation; Version A's peak-level counting creates temporary sets and Version B's rebuild counter wraps its cleanup method. Thus peaks are not pure book sizes, auxiliary-space measurements, or total process memory. On 100,000-event churn, all three seeds peaked at 776 traced bytes for A and 1,472 bytes for B; final traced allocations were 248 and 944 bytes. B finished with zero heap entries and recorded 50,000 rebuilds per stream, since emptying the last level immediately crosses its rebuild threshold. This shows bounded cleanup under this workload, with measurable cleanup overhead; it does not establish memory behavior for every workload.

## Incomplete runs and reproduction

All 90 warm-ups were attempted: 69 completed and 21 Version A warm-ups stopped. The 69 completed configurations have 345 completed raw timing repeats. Twenty-two Version A memory runs and 21 Version A latency runs stopped; all 45 Version B memory and latency runs completed. The stopped correctness checks were buildup and crowded at 10,000 and 100,000 events, mixed at 100,000, and sweep at 10,000 and 100,000, across all three seeds. Inspect `runs.csv` for each stop's processed-event count, elapsed time and reason. No throughput or median is invented for an incomplete replay. Version B timings on those workloads are retained for later use, but are not presented above as verified comparisons.

Run `python -B 20_Code/full_benchmark.py` from the assignment root to repeat. It writes a new timestamped result directory and reuses generated streams in `10_Data/full_benchmark_inputs/` when present. The comparison did not attempt a million-event workload; the 100,000-event Version A warm-up stops demonstrate the practical limit of this bounded run. Median calculations were checked against raw repeats, all 45 workload keys were present, and the source and instructor-file hashes matched their recorded values. The dashboard was not changed.
