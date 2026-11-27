# Limit order book report

**Evidence status:** Canonical clean-tree evidence.

Run label: `canonical`. Recorded code commit: `e3a5ee630b7d221722953b953bb9ae2c5cd9acc5`. The saved report contains 73 datasets and 3744 records.

## Specification and boundaries

This project implements a sequential single-venue BTC limit order book with integer cent prices and integer 10^-8 BTC quantities. Better prices execute first and FIFO breaks ties. Trades use the resting maker price. A market sell consumes bids and discards any residual. The model intentionally excludes fees, balances, hidden orders, self-trade checks, simultaneous execution, networking, and historical exchange calibration; it is not a production trading system.

## Correctness evidence

Completed correctness rows passing ordered-result and final-book agreement: 76/76; 15 were stopped by the declared limit and 0 completed rows disagreed. Independent tests additionally cover worked fills, price-time priority, partial fills, cancellation, atomic validation, quantity/proceeds conservation, input immutability, and defensive inspection copies. Agreement is supporting evidence rather than a proof.

## Implementation and revision

Version A stores active makers in one list and scans for duplicates, cancellations, and the best maker. Version B indexes active identifiers and insertion-ordered FIFO price levels, with sorted price keys and eager empty-level cleanup. Both preserve the same API and tests. The revision targets work that grows with active depth while avoiding tombstones under cancellation churn. Detailed invariants, complexity, and AI decisions are recorded in `IMPLEMENTATION_NOTES.md`.

## Runtime and throughput

| Experiment | Scenario | M | Levels | Version | Phase | Sale % | Seeds | Repeat coverage | Median seconds | Median events/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| liquidation | bid_book | 1000 | 1000 | baseline | application_total | 10 | 3 | 15/15 | 0.030309 | 33,027 |
| liquidation | bid_book | 1000 | 1000 | baseline | application_total | 100 | 3 | 15/15 | 0.068595 | 14,593 |
| liquidation | bid_book | 1000 | 1000 | baseline | application_total | 200 | 3 | 15/15 | 0.067933 | 14,735 |
| liquidation | bid_book | 1000 | 1000 | revised | application_total | 10 | 3 | 15/15 | 0.003257 | 307,358 |
| liquidation | bid_book | 1000 | 1000 | revised | application_total | 100 | 3 | 15/15 | 0.003804 | 263,121 |
| liquidation | bid_book | 1000 | 1000 | revised | application_total | 200 | 3 | 15/15 | 0.003790 | 264,125 |
| liquidation | bid_book | 10000 | 1000 | baseline | application_total | 10 | 3 | 15/15 | 2.770204 | 3,610 |
| liquidation | bid_book | 10000 | 1000 | baseline | application_total | 100 | 3 | 11/15 (4 stopped) | 6.665204 | 1,500 |
| liquidation | bid_book | 10000 | 1000 | baseline | application_total | 200 | 3 | 12/15 (3 stopped) | 6.632860 | 1,508 |
| liquidation | bid_book | 10000 | 1000 | revised | application_total | 10 | 3 | 15/15 | 0.031581 | 316,676 |
| liquidation | bid_book | 10000 | 1000 | revised | application_total | 100 | 3 | 15/15 | 0.036925 | 270,847 |
| liquidation | bid_book | 10000 | 1000 | revised | application_total | 200 | 3 | 15/15 | 0.037010 | 270,222 |
| liquidation | bid_book | 100000 | 1000 | baseline | application_total | 10 | 3 | 0/15 (15 stopped) | - | - |
| liquidation | bid_book | 100000 | 1000 | baseline | application_total | 100 | 3 | 0/15 (15 stopped) | - | - |
| liquidation | bid_book | 100000 | 1000 | baseline | application_total | 200 | 3 | 0/15 (15 stopped) | - | - |
| liquidation | bid_book | 100000 | 1000 | revised | application_total | 10 | 3 | 15/15 | 0.363409 | 275,175 |
| liquidation | bid_book | 100000 | 1000 | revised | application_total | 100 | 3 | 15/15 | 0.438848 | 227,872 |
| liquidation | bid_book | 100000 | 1000 | revised | application_total | 200 | 3 | 15/15 | 0.439548 | 227,509 |
| queue_concentration | buildup | 1000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.028513 | 35,072 |
| queue_concentration | buildup | 1000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.026835 | 37,264 |
| queue_concentration | buildup | 1000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.003472 | 287,987 |
| queue_concentration | buildup | 1000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.001805 | 553,953 |
| queue_concentration | buildup | 1000 | 4 | baseline | application_total | - | 3 | 15/15 | 0.028474 | 35,120 |
| queue_concentration | buildup | 1000 | 4 | baseline | engine_replay | - | 3 | 15/15 | 0.026780 | 37,341 |
| queue_concentration | buildup | 1000 | 4 | revised | application_total | - | 3 | 15/15 | 0.003290 | 303,940 |
| queue_concentration | buildup | 1000 | 4 | revised | engine_replay | - | 3 | 15/15 | 0.001616 | 618,732 |
| queue_concentration | buildup | 10000 | 1000 | baseline | application_total | - | 3 | 15/15 | 2.629219 | 3,803 |
| queue_concentration | buildup | 10000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 2.613654 | 3,826 |
| queue_concentration | buildup | 10000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.033674 | 296,968 |
| queue_concentration | buildup | 10000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.018109 | 552,223 |
| queue_concentration | buildup | 10000 | 4 | baseline | application_total | - | 3 | 15/15 | 2.629797 | 3,803 |
| queue_concentration | buildup | 10000 | 4 | baseline | engine_replay | - | 3 | 15/15 | 2.613254 | 3,827 |
| queue_concentration | buildup | 10000 | 4 | revised | application_total | - | 3 | 15/15 | 0.032711 | 305,709 |
| queue_concentration | buildup | 10000 | 4 | revised | engine_replay | - | 3 | 15/15 | 0.017260 | 579,377 |
| queue_concentration | buildup | 100000 | 1000 | baseline | application_total | - | 3 | 0/15 (15 stopped) | - | - |
| queue_concentration | buildup | 100000 | 1000 | baseline | engine_replay | - | 3 | 0/15 (15 stopped) | - | - |
| queue_concentration | buildup | 100000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.414834 | 241,060 |
| queue_concentration | buildup | 100000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.207707 | 481,447 |
| queue_concentration | buildup | 100000 | 4 | baseline | application_total | - | 3 | 0/15 (15 stopped) | - | - |
| queue_concentration | buildup | 100000 | 4 | baseline | engine_replay | - | 3 | 0/15 (15 stopped) | - | - |
| queue_concentration | buildup | 100000 | 4 | revised | application_total | - | 3 | 15/15 | 0.377226 | 265,093 |
| queue_concentration | buildup | 100000 | 4 | revised | engine_replay | - | 3 | 15/15 | 0.199065 | 502,347 |
| stream | buildup | 1000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.028782 | 34,744 |
| stream | buildup | 1000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.027084 | 36,922 |
| stream | buildup | 1000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.003477 | 287,566 |
| stream | buildup | 1000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.001807 | 553,493 |
| stream | buildup | 10000 | 1000 | baseline | application_total | - | 3 | 15/15 | 2.639918 | 3,788 |
| stream | buildup | 10000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 2.622864 | 3,813 |
| stream | buildup | 10000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.033643 | 297,236 |
| stream | buildup | 10000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.018057 | 553,795 |
| stream | buildup | 100000 | 1000 | baseline | application_total | - | 3 | 0/15 (15 stopped) | - | - |
| stream | buildup | 100000 | 1000 | baseline | engine_replay | - | 3 | 0/15 (15 stopped) | - | - |
| stream | buildup | 100000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.396000 | 252,525 |
| stream | buildup | 100000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.208445 | 479,744 |
| stream | cancel_churn | 1000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.002609 | 383,295 |
| stream | cancel_churn | 1000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.001134 | 881,608 |
| stream | cancel_churn | 1000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.002721 | 367,478 |
| stream | cancel_churn | 1000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.001260 | 793,835 |
| stream | cancel_churn | 10000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.025043 | 399,308 |
| stream | cancel_churn | 10000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.011548 | 865,951 |
| stream | cancel_churn | 10000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.026321 | 379,924 |
| stream | cancel_churn | 10000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.012899 | 775,269 |
| stream | cancel_churn | 100000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.265334 | 376,884 |
| stream | cancel_churn | 100000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.115116 | 868,691 |
| stream | cancel_churn | 100000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.278302 | 359,322 |
| stream | cancel_churn | 100000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.128312 | 779,349 |
| stream | crowded | 1000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.028641 | 34,915 |
| stream | crowded | 1000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.026944 | 37,115 |
| stream | crowded | 1000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.003316 | 301,534 |
| stream | crowded | 1000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.001612 | 620,251 |
| stream | crowded | 10000 | 1000 | baseline | application_total | - | 3 | 15/15 | 2.618928 | 3,818 |
| stream | crowded | 10000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 2.602437 | 3,843 |
| stream | crowded | 10000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.032618 | 306,580 |
| stream | crowded | 10000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.017131 | 583,746 |
| stream | crowded | 100000 | 1000 | baseline | application_total | - | 3 | 0/15 (15 stopped) | - | - |
| stream | crowded | 100000 | 1000 | baseline | engine_replay | - | 3 | 0/15 (15 stopped) | - | - |
| stream | crowded | 100000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.385781 | 259,214 |
| stream | crowded | 100000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.204358 | 489,338 |
| stream | mixed | 1000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.006653 | 150,300 |
| stream | mixed | 1000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.005027 | 198,908 |
| stream | mixed | 1000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.003158 | 316,685 |
| stream | mixed | 1000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.001578 | 633,596 |
| stream | mixed | 10000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.412270 | 24,256 |
| stream | mixed | 10000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.397668 | 25,147 |
| stream | mixed | 10000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.031281 | 319,679 |
| stream | mixed | 10000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.016706 | 598,581 |
| stream | mixed | 100000 | 1000 | baseline | application_total | - | 3 | 0/15 (15 stopped) | - | - |
| stream | mixed | 100000 | 1000 | baseline | engine_replay | - | 3 | 0/15 (15 stopped) | - | - |
| stream | mixed | 100000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.323857 | 308,779 |
| stream | mixed | 100000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.167363 | 597,504 |
| stream | mixed | 1000000 | 1000 | baseline | application_total | - | 1 | 0/5 (5 stopped) | - | - |
| stream | mixed | 1000000 | 1000 | baseline | engine_replay | - | 1 | 0/5 (5 stopped) | - | - |
| stream | mixed | 1000000 | 1000 | revised | application_total | - | 1 | 5/5 | 5.220738 | 191,544 |
| stream | mixed | 1000000 | 1000 | revised | engine_replay | - | 1 | 5/5 | 2.090719 | 478,304 |
| stream | sweep | 1000 | 1000 | baseline | application_total | - | 3 | 15/15 | 0.037149 | 26,918 |
| stream | sweep | 1000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 0.035462 | 28,199 |
| stream | sweep | 1000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.003614 | 276,721 |
| stream | sweep | 1000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.001946 | 513,743 |
| stream | sweep | 10000 | 1000 | baseline | application_total | - | 3 | 15/15 | 3.552743 | 2,815 |
| stream | sweep | 10000 | 1000 | baseline | engine_replay | - | 3 | 15/15 | 3.538058 | 2,826 |
| stream | sweep | 10000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.034242 | 292,038 |
| stream | sweep | 10000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.019402 | 515,410 |
| stream | sweep | 100000 | 1000 | baseline | application_total | - | 3 | 0/15 (15 stopped) | - | - |
| stream | sweep | 100000 | 1000 | baseline | engine_replay | - | 3 | 0/15 (15 stopped) | - | - |
| stream | sweep | 100000 | 1000 | revised | application_total | - | 3 | 15/15 | 0.389348 | 256,840 |
| stream | sweep | 100000 | 1000 | revised | engine_replay | - | 3 | 15/15 | 0.215625 | 463,768 |

Input reading/parsing is measured separately. `engine_replay` includes fresh empty-book construction and event processing; `application_total` adds the paired parse repeat. All displayed values are medians of saved raw repeats, not reciprocal-latency estimates.

## Processing latency

| Experiment | Scenario | M | Levels | Version | Seeds | p50 ns | p95 ns | p99 ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| queue_concentration | buildup | 1000 | 1000 | baseline | 3 | 26,917 | 49,875 | 53,667 |
| queue_concentration | buildup | 1000 | 1000 | revised | 3 | 1,834 | 2,000 | 2,584 |
| queue_concentration | buildup | 1000 | 4 | baseline | 3 | 26,417 | 49,584 | 51,834 |
| queue_concentration | buildup | 1000 | 4 | revised | 3 | 1,625 | 1,750 | 1,958 |
| queue_concentration | buildup | 10000 | 1000 | baseline | 3 | 258,709 | 493,666 | 617,500 |
| queue_concentration | buildup | 10000 | 1000 | revised | 3 | 1,709 | 2,042 | 2,292 |
| queue_concentration | buildup | 10000 | 4 | baseline | 3 | 258,167 | 493,250 | 585,667 |
| queue_concentration | buildup | 10000 | 4 | revised | 3 | 1,667 | 1,833 | 2,083 |
| queue_concentration | buildup | 100000 | 1000 | revised | 3 | 1,834 | 2,333 | 2,792 |
| queue_concentration | buildup | 100000 | 4 | revised | 3 | 1,791 | 2,166 | 2,458 |
| stream | buildup | 1000 | 1000 | baseline | 3 | 26,958 | 50,375 | 55,167 |
| stream | buildup | 1000 | 1000 | revised | 3 | 1,834 | 2,000 | 2,375 |
| stream | buildup | 10000 | 1000 | baseline | 3 | 257,667 | 496,042 | 634,041 |
| stream | buildup | 10000 | 1000 | revised | 3 | 1,709 | 2,042 | 2,291 |
| stream | buildup | 100000 | 1000 | revised | 3 | 1,834 | 2,292 | 2,792 |
| stream | cancel_churn | 1000 | 1000 | baseline | 3 | 1,375 | 1,542 | 1,625 |
| stream | cancel_churn | 1000 | 1000 | revised | 3 | 1,458 | 1,666 | 1,750 |
| stream | cancel_churn | 10000 | 1000 | baseline | 3 | 1,375 | 1,542 | 1,667 |
| stream | cancel_churn | 10000 | 1000 | revised | 3 | 1,458 | 1,666 | 1,791 |
| stream | cancel_churn | 100000 | 1000 | baseline | 3 | 1,375 | 1,542 | 1,625 |
| stream | cancel_churn | 100000 | 1000 | revised | 3 | 1,458 | 1,667 | 1,750 |
| stream | crowded | 1000 | 1000 | baseline | 3 | 26,708 | 50,333 | 54,916 |
| stream | crowded | 1000 | 1000 | revised | 3 | 1,625 | 1,750 | 2,000 |
| stream | crowded | 10000 | 1000 | baseline | 3 | 257,250 | 498,084 | 710,417 |
| stream | crowded | 10000 | 1000 | revised | 3 | 1,666 | 1,875 | 2,084 |
| stream | crowded | 100000 | 1000 | revised | 3 | 1,833 | 2,292 | 3,167 |
| stream | mixed | 1000 | 1000 | baseline | 3 | 3,833 | 11,750 | 25,166 |
| stream | mixed | 1000 | 1000 | revised | 3 | 1,667 | 2,708 | 4,375 |
| stream | mixed | 10000 | 1000 | baseline | 3 | 30,000 | 114,917 | 259,208 |
| stream | mixed | 10000 | 1000 | revised | 3 | 1,708 | 3,042 | 5,250 |
| stream | mixed | 100000 | 1000 | revised | 3 | 1,708 | 3,042 | 5,084 |
| stream | mixed | 1000000 | 1000 | revised | 1 | 1,792 | 3,167 | 5,250 |
| stream | sweep | 1000 | 1000 | baseline | 3 | 21,792 | 153,916 | 287,375 |
| stream | sweep | 1000 | 1000 | revised | 3 | 1,834 | 3,958 | 6,167 |
| stream | sweep | 10000 | 1000 | baseline | 3 | 206,417 | 1,546,417 | 3,217,667 |
| stream | sweep | 10000 | 1000 | revised | 3 | 1,750 | 3,917 | 5,917 |
| stream | sweep | 100000 | 1000 | revised | 3 | 1,833 | 4,583 | 7,209 |

Latency is instrumented separately with `perf_counter_ns`, retained per event, and summarized with nearest-rank percentiles after pooling saved samples across seeds. Saved records also separate LIMIT, CANCEL, and MARKET_SELL events and compare the first and last 10% (capped at 1,000 events).

## Memory

| Experiment | Scenario | M | Levels | Version | Seeds | Current MiB | Peak MiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| queue_concentration | buildup | 1000 | 1000 | baseline | 3 | 0.078 | 0.079 |
| queue_concentration | buildup | 1000 | 1000 | revised | 3 | 0.290 | 0.290 |
| queue_concentration | buildup | 1000 | 4 | baseline | 3 | 0.078 | 0.079 |
| queue_concentration | buildup | 1000 | 4 | revised | 3 | 0.122 | 0.123 |
| queue_concentration | buildup | 10000 | 1000 | baseline | 3 | 0.769 | 0.770 |
| queue_concentration | buildup | 10000 | 1000 | revised | 3 | 1.429 | 1.430 |
| queue_concentration | buildup | 10000 | 4 | baseline | 3 | 0.769 | 0.770 |
| queue_concentration | buildup | 10000 | 4 | revised | 3 | 1.086 | 1.087 |
| queue_concentration | buildup | 100000 | 1000 | revised | 3 | 13.472 | 14.033 |
| queue_concentration | buildup | 100000 | 4 | revised | 3 | 13.704 | 13.880 |
| stream | buildup | 1000 | 1000 | baseline | 3 | 0.078 | 0.079 |
| stream | buildup | 1000 | 1000 | revised | 3 | 0.290 | 0.290 |
| stream | buildup | 10000 | 1000 | baseline | 3 | 0.769 | 0.770 |
| stream | buildup | 10000 | 1000 | revised | 3 | 1.429 | 1.430 |
| stream | buildup | 100000 | 1000 | revised | 3 | 13.472 | 14.033 |
| stream | cancel_churn | 1000 | 1000 | baseline | 3 | 0.001 | 0.002 |
| stream | cancel_churn | 1000 | 1000 | revised | 3 | 0.002 | 0.003 |
| stream | cancel_churn | 10000 | 1000 | baseline | 3 | 0.001 | 0.002 |
| stream | cancel_churn | 10000 | 1000 | revised | 3 | 0.002 | 0.003 |
| stream | cancel_churn | 100000 | 1000 | baseline | 3 | 0.001 | 0.002 |
| stream | cancel_churn | 100000 | 1000 | revised | 3 | 0.002 | 0.003 |
| stream | crowded | 1000 | 1000 | baseline | 3 | 0.078 | 0.079 |
| stream | crowded | 1000 | 1000 | revised | 3 | 0.122 | 0.123 |
| stream | crowded | 10000 | 1000 | baseline | 3 | 0.769 | 0.770 |
| stream | crowded | 10000 | 1000 | revised | 3 | 1.086 | 1.087 |
| stream | crowded | 100000 | 1000 | revised | 3 | 13.704 | 13.880 |
| stream | mixed | 1000 | 1000 | baseline | 3 | 0.016 | 0.017 |
| stream | mixed | 1000 | 1000 | revised | 3 | 0.061 | 0.061 |
| stream | mixed | 10000 | 1000 | baseline | 3 | 0.127 | 0.129 |
| stream | mixed | 10000 | 1000 | revised | 3 | 0.394 | 0.432 |
| stream | mixed | 100000 | 1000 | revised | 3 | 2.601 | 2.841 |
| stream | mixed | 1000000 | 1000 | revised | 1 | 23.107 | 23.108 |
| stream | sweep | 1000 | 1000 | baseline | 3 | 0.036 | 0.066 |
| stream | sweep | 1000 | 1000 | revised | 3 | 0.159 | 0.232 |
| stream | sweep | 10000 | 1000 | revised | 3 | 0.786 | 1.258 |
| stream | sweep | 100000 | 1000 | revised | 3 | 5.739 | 9.534 |

Inputs are prepared before each fresh `tracemalloc` run and excluded. The live book, indexes/levels, final output, and negligible checkpoint integer bookkeeping are included; prior outputs are released. Native/process allocations are excluded, so these values are neither auxiliary space alone nor RSS.

## Large liquidation

| Setup orders | Version | Sale % | Seeds | Repeat coverage | Median sale seconds |
| --- | --- | --- | --- | --- | --- |
| 1000 | baseline | 10 | 3 | 15/15 | 0.009324 |
| 1000 | baseline | 100 | 3 | 15/15 | 0.047458 |
| 1000 | baseline | 200 | 3 | 15/15 | 0.047054 |
| 1000 | revised | 10 | 3 | 15/15 | 0.000075 |
| 1000 | revised | 100 | 3 | 15/15 | 0.000645 |
| 1000 | revised | 200 | 3 | 15/15 | 0.000639 |
| 10000 | baseline | 10 | 3 | 15/15 | 0.920343 |
| 10000 | baseline | 100 | 3 | 11/15 (4 stopped) | 4.797511 |
| 10000 | baseline | 200 | 3 | 12/15 (3 stopped) | 4.783825 |
| 10000 | revised | 10 | 3 | 15/15 | 0.000615 |
| 10000 | revised | 100 | 3 | 15/15 | 0.005777 |
| 10000 | revised | 200 | 3 | 15/15 | 0.005835 |
| 100000 | baseline | 10 | 3 | 0/15 (15 stopped) | - |
| 100000 | baseline | 100 | 3 | 0/15 (15 stopped) | - |
| 100000 | baseline | 200 | 3 | 0/15 (15 stopped) | - |
| 100000 | revised | 10 | 3 | 15/15 | 0.008927 |
| 100000 | revised | 100 | 3 | 15/15 | 0.083848 |
| 100000 | revised | 200 | 3 | 15/15 | 0.083881 |

Each percentage is evaluated against a freshly rebuilt identical bid book. Saved correctness rows contain requested quantity, makers touched, price levels visited, fills, and unfilled residual.

## Bottleneck and operation counts

| Dataset | Requested / processed | Active peak | Level peak | Fills | Visited levels | Final active |
| --- | --- | --- | --- | --- | --- | --- |
| liquidation__bid_book__m100000__seed42__levels1000 | 1000 / 1000 | 1000 | 620 | 0 | 0 | 1000 |
| liquidation__bid_book__m100000__seed43__levels1000 | 1000 / 1000 | 1000 | 621 | 0 | 0 | 1000 |
| liquidation__bid_book__m100000__seed44__levels1000 | 1000 / 1000 | 1000 | 634 | 0 | 0 | 1000 |
| liquidation__bid_book__m10000__seed42__levels1000 | 1000 / 1000 | 1000 | 620 | 0 | 0 | 1000 |
| liquidation__bid_book__m10000__seed43__levels1000 | 1000 / 1000 | 1000 | 621 | 0 | 0 | 1000 |
| liquidation__bid_book__m10000__seed44__levels1000 | 1000 / 1000 | 1000 | 634 | 0 | 0 | 1000 |
| liquidation__bid_book__m1000__seed42__levels1000 | 1000 / 1000 | 1000 | 620 | 0 | 0 | 1000 |
| liquidation__bid_book__m1000__seed43__levels1000 | 1000 / 1000 | 1000 | 621 | 0 | 0 | 1000 |
| liquidation__bid_book__m1000__seed44__levels1000 | 1000 / 1000 | 1000 | 634 | 0 | 0 | 1000 |
| queue_concentration__buildup__m100000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| queue_concentration__buildup__m100000__seed42__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m100000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| queue_concentration__buildup__m100000__seed43__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m100000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| queue_concentration__buildup__m100000__seed44__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m10000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| queue_concentration__buildup__m10000__seed42__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m10000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| queue_concentration__buildup__m10000__seed43__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m10000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| queue_concentration__buildup__m10000__seed44__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m1000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| queue_concentration__buildup__m1000__seed42__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m1000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| queue_concentration__buildup__m1000__seed43__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| queue_concentration__buildup__m1000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| queue_concentration__buildup__m1000__seed44__levels4 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__buildup__m100000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| stream__buildup__m100000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| stream__buildup__m100000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| stream__buildup__m10000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| stream__buildup__m10000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| stream__buildup__m10000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| stream__buildup__m1000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| stream__buildup__m1000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| stream__buildup__m1000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| stream__cancel_churn__m100000__seed42__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m100000__seed43__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m100000__seed44__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m10000__seed42__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m10000__seed43__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m10000__seed44__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m1000__seed42__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m1000__seed43__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__cancel_churn__m1000__seed44__levels1000 | 1000 / 1000 | 1 | 1 | 0 | 0 | 0 |
| stream__crowded__m100000__seed42__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m100000__seed43__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m100000__seed44__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m10000__seed42__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m10000__seed43__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m10000__seed44__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m1000__seed42__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m1000__seed43__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__crowded__m1000__seed44__levels1000 | 1000 / 1000 | 1000 | 8 | 0 | 0 | 1000 |
| stream__mixed__m1000000__seed43__levels1000 | 1000 / 1000 | 181 | 161 | 354 | 341 | 179 |
| stream__mixed__m100000__seed42__levels1000 | 1000 / 1000 | 140 | 126 | 374 | 359 | 138 |
| stream__mixed__m100000__seed43__levels1000 | 1000 / 1000 | 181 | 161 | 354 | 341 | 179 |
| stream__mixed__m100000__seed44__levels1000 | 1000 / 1000 | 162 | 152 | 390 | 381 | 162 |
| stream__mixed__m10000__seed42__levels1000 | 1000 / 1000 | 140 | 126 | 374 | 359 | 138 |
| stream__mixed__m10000__seed43__levels1000 | 1000 / 1000 | 181 | 161 | 354 | 341 | 179 |
| stream__mixed__m10000__seed44__levels1000 | 1000 / 1000 | 162 | 152 | 390 | 381 | 162 |
| stream__mixed__m1000__seed42__levels1000 | 1000 / 1000 | 140 | 126 | 374 | 359 | 138 |
| stream__mixed__m1000__seed43__levels1000 | 1000 / 1000 | 181 | 161 | 354 | 341 | 179 |
| stream__mixed__m1000__seed44__levels1000 | 1000 / 1000 | 162 | 152 | 390 | 381 | 162 |
| stream__sweep__m100000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| stream__sweep__m100000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| stream__sweep__m100000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| stream__sweep__m10000__seed42__levels1000 | 1000 / 1000 | 1000 | 805 | 0 | 0 | 1000 |
| stream__sweep__m10000__seed43__levels1000 | 1000 / 1000 | 1000 | 801 | 0 | 0 | 1000 |
| stream__sweep__m10000__seed44__levels1000 | 1000 / 1000 | 1000 | 775 | 0 | 0 | 1000 |
| stream__sweep__m1000__seed42__levels1000 | 1000 / 1000 | 800 | 661 | 496 | 427 | 411 |
| stream__sweep__m1000__seed43__levels1000 | 1000 / 1000 | 800 | 666 | 510 | 442 | 389 |
| stream__sweep__m1000__seed44__levels1000 | 1000 / 1000 | 800 | 647 | 483 | 419 | 418 |

The baseline can rescan B active orders for validation and each maker fill; the revision usually performs indexed lookup and FIFO-level access but pays O(P) when inserting or deleting a sorted price key. The active-depth, price-level, and fill counts above explain why performance can vary by workload; no claim assumes the revision wins everywhere.

## Limitations

Stopped saved records: 539. Partial timing summaries: 9. Missing timing repeats: 0. Repeat coverage is shown in timing tables; declared stops and missing work are not extrapolated. Results are machine- and interpreter-specific synthetic measurements. Sequential processing excludes networking and queueing, so throughput does not establish live-venue overload capacity. The supplied data are teaching workloads rather than historical or calibrated market data. Passing tests and cross-version agreement do not constitute a formal proof.

## Reproducibility

Python: `3.14.7`; platform: `macOS-15.5-arm64-arm-64bit-Mach-O`; dirty tree: `False`.

Recorded measurement command:

```text
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 tools/run_benchmarks.py --profile canonical --time-limit-seconds 5 --output results/raw_measurements.json.gz
```

Time-limit scope: engine replay, per-event latency, liquidation build/sale, bounded correctness attempts, and memory tracing; input parsing and derived application totals are not independently limited

Run `python3 -m unittest discover -s tests -v`, rebuild the dashboard from the saved result file with `python3 dashboard.py`, and consult `MEASUREMENT_PLAN.md` for exact data preparation, timing, latency, and memory boundaries.
