# Bitcoin limit order book — short report

## Specification and model

The assignment models a sequential BTC order book at one venue. Limit orders execute at the best eligible resting price, with FIFO priority at each price; a residual limit rests. Market sells consume bids and discard any unfilled remainder. Cancellations remove the target's remaining quantity. Prices are integer cents per BTC and quantities are integer 10⁻⁸ BTC units; proceeds are the sum of price × quantity, divided by 10¹⁰ for dollars. The model excludes fees, balances, hidden orders, network delay, self-trade checks and simultaneous events. Synthetic data are not historical or calibrated market observations.

## Correctness and invariants

Each maker has one active identity and a positive remaining quantity. Matching uses best price, then original arrival rank; partial fills retain that rank. Incoming quantity equals executed quantity plus returned residual, and fills use the maker's price. Invalid events are rejected without advancing the accepted sequence or changing the book. Both versions use the project-specific identifier policy: nonempty strings and integers, excluding Booleans.

The latest recorded suite passed 27 tests, including hand-calculated cases and the provided example. In that example makers b1, b2, b3 and b4 fill 1, 1, 3 and 1 BTC, yielding $359,400; four BTC remain on b4 and the ask is unchanged. All 15 targeted 10,000-event streams subsequently produced identical ordered event results and final books in separate checks. Five short generated streams were also compared after every event. Passing tests are evidence, not proof of correctness.

## Runtime, throughput and latency

The targeted run used five scenarios, seeds 42–44, 10,000 events, a warm-up and five timed replays per seed on identical inputs. Per-scenario results below are medians of the three seed-specific medians. Time uses `perf_counter`; throughput equals events divided by median replay time. Per-event latency was measured separately, with nearest-rank p95 and p99; it is not the reciprocal of throughput. The 120-second per-phase limit applied equally, and timing included a progress update once per 100 events.

| Scenario | A median (s) | B median (s) | A/B ratio of scenario medians |
|---|---:|---:|---:|
| buildup | 9.395343 | 0.032185 | 291.9 |
| crowded | 15.984131 | 0.030683 | 520.9 |
| mixed | 1.459713 | 0.034120 | 42.8 |
| sweep | 21.022947 | 0.053545 | 392.6 |
| cancel churn | 0.028604 | 0.036132 | 0.79 |

The dashboard also shows **each seed's A/B ratio**, which is not necessarily equal to the ratio of scenario medians. On this machine Version B improved the growing-book and sell workloads; A was faster under churn, where active depth stayed tiny. The synthetic workloads and machine matter, and these results do not establish live-exchange capacity.

## Memory and profiling

Separate `tracemalloc` runs excluded preloaded input but included the live book, retained output and instrumentation. Version A uses temporary sets to count active levels, while Version B wraps cleanup to count rebuilds; measured allocations are not pure book memory or total process memory. Four A memory runs stopped at 120 seconds: buildup seeds 42 and 44, sweep seeds 42 and 43. Missing peaks are not zero. Version B's indices and heaps add storage and cleanup work; churn seed 42 finished with zero heap entries and 5,000 rebuilds. More detailed measurements and limits are in `TARGETED_COMPARISON.md`.

## Revision, complexity and limitations

Version A uses one list; B uses an ID dictionary, exact-price FIFO dictionaries and bid/ask heaps. B immediately removes inactive orders, lazily removes obsolete heap prices, and rebuilds a heap when it exceeds three times its active levels. Negative bid prices make a min-heap select the highest bid. Hash lookup is expected/amortized, and a rebuild can cost O(P) in one operation.

Let B be active orders, P occupied prices, F maker fills and K stale heap entries cleaned. A's duplicate lookup and cancellation are O(B); a sell is O((F+1)B) worst case. B's ID lookup and cancellation are expected O(1), except occasional O(P) rebuilds. A valid heap root gives best price in O(1); stale cleanup costs O(K log P). B processes F makers with price-heap maintenance and output construction; ordered dictionary iteration can traverse internal deleted slots, so first-maker selection is not guaranteed worst-case constant time. A and B inspection both sort B orders in O(B log B) and return copies; B stores O(B+P) active structures plus O(F) current fills. Bounds depend on the implementation and dictionary behavior.

```text
LIMIT: while an eligible opposite maker exists, choose best price then FIFO;
       trade min(remaining quantities) at maker price; remove exhausted maker;
       rest incoming residual at its original sequence.
CANCEL: find active ID; remove remaining order and empty level if needed;
        otherwise return not_found.
MARKET SELL: repeatedly choose best bid and FIFO maker, update and record fills;
             discard unfilled residual.
```

Version A finds the maker by scanning; Version B uses heaps and price queues, cleaning stale prices as needed. Tests and input files were preserved. The earlier broader benchmark has stopped runs and the historical controlled trials use earlier source hashes, so neither should be silently mixed with the targeted results. No million-event measurement was completed. The assignment's full 100,000-event matrix was attempted under a shorter limit and many A cases stopped; see `PERFORMANCE_COMPARISON.md`.

## AI assistance

AI assisted with test design, the baseline, the indexed revision, measurement scripts and documentation. The user selected and authorized the indexed structure and benchmark phases. An initial mismatch in identifier acceptance was identified and the user specified a shared policy; both versions and tests were updated. The earlier 10-second benchmark limit stopped meaningful checks, so the user requested the targeted 120-second comparison. These are recorded decisions and corrections; no unsupported claim about other accepted or rejected suggestions is implied.

## 100,000-Event Scaling and Limitations

On 24 November 2026, a targeted single-attempt experiment revisited the 100,000-event cases. This avoided repeating the full benchmark, latency, or memory runs. The same 15 saved inputs and a 120-second wall-time limit were used for both current implementations. Inputs were loaded before timing, and progress was recorded after each 1,000 completed events. Each point is one observed run, including progress-reporting overhead.

Version A completed all three cancellation-churn streams in approximately 0.14–0.15 seconds. The other 12 attempts stopped at the limit. Their last confirmed counts were:

| Scenario | Seed 42 | Seed 43 | Seed 44 |
|---|---:|---:|---:|
| buildup | 49,000 | 50,000 | 46,000 |
| crowded | 44,000 | 45,000 | 45,000 |
| mixed | 89,000 | 89,000 | 87,000 |
| sweep | 43,000 | 44,000 | 49,000 |

All 15 current Version B attempts completed, with individual times and throughput in `40_Results/scaling_100000_20261124_114134/attempts.csv`. Five-repeat Version B medians from `full_comparison_20261123_171219/` were retained as historical evidence after checking matching input fingerprints and generator settings. They use an earlier B source hash, before identifier-validation harmonization, and per-event progress reporting. They are not measurements of current B. Because those versions and instrumentation differ, new current B single attempts were collected for the comparison. Of the prior 100,000-event correctness checks, 12 stopped and the three cancellation-churn checks completed for the earlier code. No 100,000-event comparison was rerun for the current code; the completed 10,000-event checks and existing tests are the available current-code correctness evidence.

Linear and quadratic **hypothetical estimates** multiply the matching scenario-and-seed 10,000-event A median by 10 and 100 respectively. They are not measured completion times, a guaranteed range, or confidence intervals. Across seeds, estimates in seconds were:

| Scenario | Linear | Quadratic |
|---|---:|---:|
| buildup | 73.72–134.71 | 737.16–1,347.10 |
| crowded | 147.76–163.82 | 1,477.59–1,638.20 |
| mixed | 12.89–15.03 | 128.89–150.26 |
| sweep | 132.19–220.46 | 1,321.93–2,204.56 |
| cancel churn | 0.28–0.29 | 2.81–2.92 |

Event count alone does not control active depth, maker fills or workload composition. In particular, a sweep's work depends on available liquidity and fills. For stopped A runs, the dashboard's conservative relative-time bound uses the last confirmed A processing timestamp divided by the matching current B single-attempt time. This avoids treating the supervisor's 120-second timer, which starts just before the worker timer, as exactly 120 seconds of measured engine processing. The original timeout-based calculation is preserved in `attempts_original.csv`; `attempts.csv` corrects only that derived field. These ratios are conditional on the timing and correctness limitations above, not extrapolated speedups or statistical guarantees.

The observed progress supports the conclusion that a growing list-based book can become expensive under these workloads. It does not establish that completion is mathematically impossible. Direct completed A/B comparisons were not obtained for 12 configurations within the chosen budget. Detailed outcomes, observed progress, input and code hashes, historic references and environment information are saved in the scaling results directory.

**Important finding**

The 100,000-event experiment demonstrates that Version A's scalability is determined not only by the number of incoming events but also by the evolving state of the order book. In buildup, crowded, and sweep workloads, repeated full-book searches progressively reduce throughput. In contrast, cancellation churn remains extremely fast because the active book stays almost empty. This supports replacing repeated list scans with indexed order lookup and price-level structures, as implemented in Version B.


## Submission corrections and additional evidence

The current versions were compared on all five 1,000-event scenarios and seeds 42–44: 15 separate checks compared ordered event results and canonical books after every event, and all passed. Each version then completed one warm-up and five replay repetitions for each workload. The run is `40_Results/current_1000_20261124_151858/`; its recorded algorithm hashes match the targeted 10,000-event run. The older diagnostic and controlled measurements retain their earlier source hashes and are not silently treated as current-code measurements.

The following **derived application-cost estimates** add each saved input-reading/parsing time to the replay time from the same repetition, take the median of five sums for each seed, then the median of the three seeds. They are not separately timed end-to-end runs: process startup, inter-process scheduling and printing are excluded. Figures are seconds for 10,000 events.

| Scenario | Version A | Version B |
|---|---:|---:|
| buildup | 9.418698 | 0.061203 |
| crowded | 16.012109 | 0.063167 |
| mixed | 1.484701 | 0.063297 |
| sweep | 21.052343 | 0.095036 |
| cancel churn | 0.068665 | 0.073209 |

Historical controlled trials timed fresh construction of 1,000 bid orders separately from selling. For the five 100% sell trials, median construction times were 0.062756 s for A and 0.005768 s for B at four prices; at 1,000 prices they were 0.071236 s and 0.004595 s. These use the earlier code versions recorded in `40_Results/full_comparison_20261123_171219/environment.json`; they are not current-code measurements.

In the 10,000-event targeted cancellation-churn runs, all seeds finished with zero active orders. Final traced allocations were 248 bytes for A and 944 bytes for B on each seed. Preloaded input was excluded; instrumentation, book objects, and the final returned result were included. These values are not total process memory or pure book storage. Four other Version A memory runs stopped at 120 seconds; their peaks remain unknown. The current versions' full 100,000-event equivalence was not checked: 12 earlier-code checks stopped and three churn checks completed.

The 1,000,000-event experiment was not performed because Version A's observed scaling made it computationally infeasible within the available resources and time budget. This is not a claim that completing the experiment is mathematically impossible. No new scan-count profiling was added; the available controlled trials count fills and visited prices, and Version A's repeated scans are evident in its source and theoretical cost.


## Construction Scaling and Price Concentration

This experiment separately measures building a fresh, initially empty book from non-crossing BUY limit orders; it is not a full-stream replay or a market-sell test. For 100, 1,000, 5,000 and 10,000 orders, each concentrated input occupied exactly four prices; the corresponding dispersed input occupied 100 prices for 100 orders and 1,000 prices for larger sizes. Inputs were deterministically generated with seed 42, saved with fingerprints, and reused for both implementations. Quantities matched across versions, and each pair of price distributions used the same quantity sequence.

Each configuration had one warm-up and five timed repetitions on fresh books. Book creation and order processing are inside `perf_counter` timing; input generation, loading and correctness verification are outside. A shared progress write every 100 completed orders is included. The attempt limit was 30 seconds. All 16 version/configuration combinations completed; no attempts stopped. Separate verification checked every event rested without fills, both final canonical books matched an independently sorted expected book, quantities and arrival order were preserved, and inputs were unchanged.

At 1,000 and 10,000 orders respectively, A's median construction time rose from 0.041441 s to 3.976877 s at four prices, and from 0.038846 s to 3.371033 s with 1,000 prices. B rose from 0.002580 s to 0.021150 s at four prices, and from 0.005652 s to 0.023305 s with 1,000 prices. For 10,000 orders, the measured A/B median ratios were 188.0× and 144.7× respectively. The chart and raw CSV show all four order counts and each repetition.

The measurements are consistent with A's repeated scans and B's ID dictionary and price-level index. For these unique-ID, passive inputs, every submission makes one duplicate-ID lookup; the stream contains P new-level insertions and N−P submissions to existing levels. A's duplicate-ID scan has N(N−1)/2 prior-order comparisons in the theoretical model: 49,995,000 at N=10,000. These counts are derived from the verified stream and code, not measured by internal instrumentation; A also scans resting orders during matching. B's ID lookup and existing-level insertion are expected O(1), and creating a level may add an O(log P) heap push. These claims do not guarantee a particular empirical scaling exponent.

In this run, dispersed prices increased B's median from 0.002580 s to 0.005652 s at 1,000 orders and from 0.021150 s to 0.023305 s at 10,000. A's 10,000-order medians were 3.976877 s and 3.371033 s respectively. The sizes, one seed and normal timing variability limit interpretation; the results do not establish that one price distribution always wins. Raw timings, input fingerprints, operation counts, statuses, source hashes and environment details are in `40_Results/construction_scaling_20261124_162635/`.

The final order and occupied-price counts recorded alongside timing rows come from the separate untimed verification, not from inspecting each timed book.
