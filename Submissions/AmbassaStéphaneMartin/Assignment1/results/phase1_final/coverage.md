# Final measured coverage

All values below are regenerated from audited saved data. Documented stops are attempted coverage, not completed estimates.
Required workload cases: 99; phase groups: 891.
States: {'completed': 759, 'stopped': 132, 'unattempted': 0, 'failed': 0}. Missing: 0.
Available complete comparable timing pairs: 67; mismatches: 0.
Diagnostic pairs (checked independently of timing completion): {'matching': 72, 'unavailable': 27}.
Required concentration input pairs with identical quantities, IDs and arrival order: 9 (all-index pairs, including count-120 validation: 10).
New execution totals (command wall time, including preparation): {'commands': 58, 'actual_command_wall_seconds': 7331.083812900179, 'completed_commands': 30, 'commands_with_documented_stops': 28, 'failed_commands': 0, 'note': 'Includes the preserved interference-affected run and its replacement; phases and engine times remain separate.'}.

## Actual outcomes by experiment/count/implementation

| Experiment | Requested count | Version | Completed | Stopped | Failed | Unattempted |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| cancel-churn | 1000 | baseline | 12 | 0 | 0 | 0 |
| cancel-churn | 1000 | revised | 12 | 0 | 0 | 0 |
| cancel-churn | 1000 | shared I/O | 3 | 0 | 0 | 0 |
| cancel-churn | 10000 | baseline | 12 | 0 | 0 | 0 |
| cancel-churn | 10000 | revised | 12 | 0 | 0 | 0 |
| cancel-churn | 10000 | shared I/O | 3 | 0 | 0 | 0 |
| cancel-churn | 100000 | baseline | 12 | 0 | 0 | 0 |
| cancel-churn | 100000 | revised | 12 | 0 | 0 | 0 |
| cancel-churn | 100000 | shared I/O | 3 | 0 | 0 | 0 |
| market-sell | 1000 | baseline | 36 | 0 | 0 | 0 |
| market-sell | 1000 | revised | 36 | 0 | 0 | 0 |
| market-sell | 1000 | shared I/O | 9 | 0 | 0 | 0 |
| market-sell | 10000 | baseline | 26 | 10 | 0 | 0 |
| market-sell | 10000 | revised | 36 | 0 | 0 | 0 |
| market-sell | 10000 | shared I/O | 9 | 0 | 0 | 0 |
| market-sell | 100000 | baseline | 0 | 36 | 0 | 0 |
| market-sell | 100000 | revised | 36 | 0 | 0 | 0 |
| market-sell | 100000 | shared I/O | 9 | 0 | 0 | 0 |
| queue-concentration | 1000 | baseline | 24 | 0 | 0 | 0 |
| queue-concentration | 1000 | revised | 24 | 0 | 0 | 0 |
| queue-concentration | 1000 | shared I/O | 6 | 0 | 0 | 0 |
| queue-concentration | 10000 | baseline | 13 | 11 | 0 | 0 |
| queue-concentration | 10000 | revised | 24 | 0 | 0 | 0 |
| queue-concentration | 10000 | shared I/O | 6 | 0 | 0 | 0 |
| queue-concentration | 100000 | baseline | 0 | 24 | 0 | 0 |
| queue-concentration | 100000 | revised | 24 | 0 | 0 | 0 |
| queue-concentration | 100000 | shared I/O | 6 | 0 | 0 | 0 |
| replay | 1000 | baseline | 60 | 0 | 0 | 0 |
| replay | 1000 | revised | 60 | 0 | 0 | 0 |
| replay | 1000 | shared I/O | 15 | 0 | 0 | 0 |
| replay | 10000 | baseline | 57 | 3 | 0 | 0 |
| replay | 10000 | revised | 60 | 0 | 0 | 0 |
| replay | 10000 | shared I/O | 15 | 0 | 0 | 0 |
| replay | 100000 | baseline | 12 | 48 | 0 | 0 |
| replay | 100000 | revised | 60 | 0 | 0 | 0 |
| replay | 100000 | shared I/O | 15 | 0 | 0 | 0 |

## Complete measured timings

Seconds; construction and sale/replay are distinct. All displayed groups have five repetitions. Speedups are only in the audited comparison table and dashboard.

| Case | Version | Construction, s | Operation, s | Total compute, s | Processed events |
| --- | --- | ---: | ---: | ---: | ---: |
| replay_buildup_n1000_s42_l1000 | baseline | n/a | 0.055556 | 0.055558 | 1000 |
| replay_buildup_n1000_s42_l1000 | revised | n/a | 0.002859 | 0.002862 | 1000 |
| replay_crowded_n1000_s42_l1000 | baseline | n/a | 0.057222 | 0.057226 | 1000 |
| replay_crowded_n1000_s42_l1000 | revised | n/a | 0.002266 | 0.002269 | 1000 |
| replay_mixed_n1000_s42_l1000 | baseline | n/a | 0.010220 | 0.010222 | 1000 |
| replay_mixed_n1000_s42_l1000 | revised | n/a | 0.002534 | 0.002541 | 1000 |
| replay_sweep_n1000_s42_l1000 | baseline | n/a | 0.062656 | 0.062659 | 1000 |
| replay_sweep_n1000_s42_l1000 | revised | n/a | 0.003200 | 0.003202 | 1000 |
| replay_cancel_churn_n1000_s42_l1000 | baseline | n/a | 0.001860 | 0.001861 | 1000 |
| replay_cancel_churn_n1000_s42_l1000 | revised | n/a | 0.001964 | 0.001971 | 1000 |
| market-sell_controlled_bids_n1000_s42_l1000_p10 | baseline | 0.029228 | 0.011584 | 0.041408 | 1 |
| market-sell_controlled_bids_n1000_s42_l1000_p10 | revised | 0.002584 | 0.000144 | 0.002736 | 1 |
| market-sell_controlled_bids_n1000_s42_l1000_p100 | baseline | 0.029378 | 0.061232 | 0.089229 | 1 |
| market-sell_controlled_bids_n1000_s42_l1000_p100 | revised | 0.002539 | 0.001277 | 0.003818 | 1 |
| market-sell_controlled_bids_n1000_s42_l1000_p200 | baseline | 0.027998 | 0.058943 | 0.086944 | 1 |
| market-sell_controlled_bids_n1000_s42_l1000_p200 | revised | 0.002550 | 0.001270 | 0.003801 | 1 |
| queue-concentration_controlled_bids_n1000_s42_l4_p100 | baseline | 0.027198 | 0.070089 | 0.097288 | 1 |
| queue-concentration_controlled_bids_n1000_s42_l4_p100 | revised | 0.002008 | 0.001148 | 0.003112 | 1 |
| queue-concentration_controlled_bids_n1000_s42_l1000_p100 | baseline | 0.028806 | 0.060975 | 0.089398 | 1 |
| queue-concentration_controlled_bids_n1000_s42_l1000_p100 | revised | 0.002500 | 0.001290 | 0.003794 | 1 |
| cancel-churn_anchored_cancel_churn_n1000_s42_l1 | baseline | n/a | 0.003850 | 0.003852 | 2002 |
| cancel-churn_anchored_cancel_churn_n1000_s42_l1 | revised | n/a | 0.003551 | 0.003559 | 2002 |
| replay_buildup_n1000_s43_l1000 | baseline | n/a | 0.053339 | 0.053341 | 1000 |
| replay_buildup_n1000_s43_l1000 | revised | n/a | 0.002897 | 0.002900 | 1000 |
| replay_crowded_n1000_s43_l1000 | baseline | n/a | 0.055984 | 0.055986 | 1000 |
| replay_crowded_n1000_s43_l1000 | revised | n/a | 0.002454 | 0.002458 | 1000 |
| replay_mixed_n1000_s43_l1000 | baseline | n/a | 0.009269 | 0.009270 | 1000 |
| replay_mixed_n1000_s43_l1000 | revised | n/a | 0.002419 | 0.002422 | 1000 |
| replay_sweep_n1000_s43_l1000 | baseline | n/a | 0.063947 | 0.063949 | 1000 |
| replay_sweep_n1000_s43_l1000 | revised | n/a | 0.003206 | 0.003210 | 1000 |
| replay_cancel_churn_n1000_s43_l1000 | baseline | n/a | 0.001844 | 0.001847 | 1000 |
| replay_cancel_churn_n1000_s43_l1000 | revised | n/a | 0.001842 | 0.001845 | 1000 |
| market-sell_controlled_bids_n1000_s43_l1000_p10 | baseline | 0.028316 | 0.010386 | 0.039802 | 1 |
| market-sell_controlled_bids_n1000_s43_l1000_p10 | revised | 0.002616 | 0.000132 | 0.002749 | 1 |
| market-sell_controlled_bids_n1000_s43_l1000_p100 | baseline | 0.028140 | 0.058481 | 0.086150 | 1 |
| market-sell_controlled_bids_n1000_s43_l1000_p100 | revised | 0.002403 | 0.001251 | 0.003651 | 1 |
| market-sell_controlled_bids_n1000_s43_l1000_p200 | baseline | 0.028220 | 0.060141 | 0.088959 | 1 |
| market-sell_controlled_bids_n1000_s43_l1000_p200 | revised | 0.002457 | 0.001350 | 0.003853 | 1 |
| queue-concentration_controlled_bids_n1000_s43_l4_p100 | baseline | 0.031039 | 0.071455 | 0.102358 | 1 |
| queue-concentration_controlled_bids_n1000_s43_l4_p100 | revised | 0.002006 | 0.001129 | 0.003138 | 1 |
| queue-concentration_controlled_bids_n1000_s43_l1000_p100 | baseline | 0.027784 | 0.059393 | 0.087650 | 1 |
| queue-concentration_controlled_bids_n1000_s43_l1000_p100 | revised | 0.002416 | 0.001265 | 0.003714 | 1 |
| cancel-churn_anchored_cancel_churn_n1000_s43_l1 | baseline | n/a | 0.003698 | 0.003699 | 2002 |
| cancel-churn_anchored_cancel_churn_n1000_s43_l1 | revised | n/a | 0.003606 | 0.003609 | 2002 |
| replay_buildup_n1000_s44_l1000 | baseline | n/a | 0.055257 | 0.055259 | 1000 |
| replay_buildup_n1000_s44_l1000 | revised | n/a | 0.002749 | 0.002754 | 1000 |
| replay_crowded_n1000_s44_l1000 | baseline | n/a | 0.056608 | 0.056611 | 1000 |
| replay_crowded_n1000_s44_l1000 | revised | n/a | 0.002298 | 0.002301 | 1000 |
| replay_mixed_n1000_s44_l1000 | baseline | n/a | 0.010333 | 0.010334 | 1000 |
| replay_mixed_n1000_s44_l1000 | revised | n/a | 0.002400 | 0.002402 | 1000 |
| replay_sweep_n1000_s44_l1000 | baseline | n/a | 0.063537 | 0.063539 | 1000 |
| replay_sweep_n1000_s44_l1000 | revised | n/a | 0.003101 | 0.003104 | 1000 |
| replay_cancel_churn_n1000_s44_l1000 | baseline | n/a | 0.001787 | 0.001789 | 1000 |
| replay_cancel_churn_n1000_s44_l1000 | revised | n/a | 0.001873 | 0.001875 | 1000 |
| market-sell_controlled_bids_n1000_s44_l1000_p10 | baseline | 0.027398 | 0.011149 | 0.038396 | 1 |
| market-sell_controlled_bids_n1000_s44_l1000_p10 | revised | 0.002569 | 0.000137 | 0.002737 | 1 |
| market-sell_controlled_bids_n1000_s44_l1000_p100 | baseline | 0.027315 | 0.062398 | 0.090847 | 1 |
| market-sell_controlled_bids_n1000_s44_l1000_p100 | revised | 0.002588 | 0.001234 | 0.003827 | 1 |
| market-sell_controlled_bids_n1000_s44_l1000_p200 | baseline | 0.029268 | 0.058968 | 0.087980 | 1 |
| market-sell_controlled_bids_n1000_s44_l1000_p200 | revised | 0.002508 | 0.001282 | 0.003820 | 1 |
| queue-concentration_controlled_bids_n1000_s44_l4_p100 | baseline | 0.029173 | 0.072149 | 0.102027 | 1 |
| queue-concentration_controlled_bids_n1000_s44_l4_p100 | revised | 0.002012 | 0.001136 | 0.003196 | 1 |
| queue-concentration_controlled_bids_n1000_s44_l1000_p100 | baseline | 0.029720 | 0.061152 | 0.090518 | 1 |
| queue-concentration_controlled_bids_n1000_s44_l1000_p100 | revised | 0.002463 | 0.001254 | 0.003707 | 1 |
| cancel-churn_anchored_cancel_churn_n1000_s44_l1 | baseline | n/a | 0.003937 | 0.003939 | 2002 |
| cancel-churn_anchored_cancel_churn_n1000_s44_l1 | revised | n/a | 0.003642 | 0.003645 | 2002 |
| replay_buildup_n10000_s42_l1000 | baseline | n/a | 5.231033 | 5.231036 | 10000 |
| replay_buildup_n10000_s42_l1000 | revised | n/a | 0.025500 | 0.025504 | 10000 |
| replay_crowded_n10000_s42_l1000 | baseline | n/a | 5.341705 | 5.341711 | 10000 |
| replay_crowded_n10000_s42_l1000 | revised | n/a | 0.025428 | 0.025432 | 10000 |
| replay_mixed_n10000_s42_l1000 | baseline | n/a | 0.762378 | 0.762381 | 10000 |
| replay_mixed_n10000_s42_l1000 | revised | n/a | 0.028049 | 0.028052 | 10000 |
| replay_sweep_n10000_s42_l1000 | baseline | n/a | 6.349202 | 6.349203 | 10000 |
| replay_sweep_n10000_s42_l1000 | revised | n/a | 0.030827 | 0.030831 | 10000 |
| replay_cancel_churn_n10000_s42_l1000 | baseline | n/a | 0.018698 | 0.018700 | 10000 |
| replay_cancel_churn_n10000_s42_l1000 | revised | n/a | 0.018748 | 0.018752 | 10000 |
| market-sell_controlled_bids_n10000_s42_l1000_p10 | baseline | 2.522130 | 1.328087 | 3.849774 | 1 |
| market-sell_controlled_bids_n10000_s42_l1000_p10 | revised | 0.023698 | 0.001476 | 0.025065 | 1 |
| market-sell_controlled_bids_n10000_s42_l1000_p100 | baseline | 2.548904 | 6.889676 | 9.449806 | 1 |
| market-sell_controlled_bids_n10000_s42_l1000_p100 | revised | 0.021584 | 0.012751 | 0.035756 | 1 |
| market-sell_controlled_bids_n10000_s42_l1000_p200 | baseline | 2.518399 | 6.781089 | 9.296014 | 1 |
| market-sell_controlled_bids_n10000_s42_l1000_p200 | revised | 0.023728 | 0.012175 | 0.035908 | 1 |
| queue-concentration_controlled_bids_n10000_s42_l4_p100 | baseline | 2.561793 | 7.340161 | 9.859430 | 1 |
| queue-concentration_controlled_bids_n10000_s42_l4_p100 | revised | 0.020428 | 0.012507 | 0.032884 | 1 |
| queue-concentration_controlled_bids_n10000_s42_l1000_p100 | baseline | 2.545270 | 6.783429 | 9.334521 | 1 |
| queue-concentration_controlled_bids_n10000_s42_l1000_p100 | revised | 0.021019 | 0.013490 | 0.034353 | 1 |
| cancel-churn_anchored_cancel_churn_n10000_s42_l1 | baseline | n/a | 0.038521 | 0.038524 | 20002 |
| cancel-churn_anchored_cancel_churn_n10000_s42_l1 | revised | n/a | 0.037324 | 0.037333 | 20002 |
| replay_buildup_n10000_s43_l1000 | baseline | n/a | 5.202065 | 5.202068 | 10000 |
| replay_buildup_n10000_s43_l1000 | revised | n/a | 0.027082 | 0.027086 | 10000 |
| replay_crowded_n10000_s43_l1000 | baseline | n/a | 5.317558 | 5.317561 | 10000 |
| replay_crowded_n10000_s43_l1000 | revised | n/a | 0.024249 | 0.024260 | 10000 |
| replay_mixed_n10000_s43_l1000 | baseline | n/a | 0.808750 | 0.808753 | 10000 |
| replay_mixed_n10000_s43_l1000 | revised | n/a | 0.028311 | 0.028320 | 10000 |
| replay_sweep_n10000_s43_l1000 | baseline | n/a | 6.270694 | 6.270696 | 10000 |
| replay_sweep_n10000_s43_l1000 | revised | n/a | 0.031447 | 0.031455 | 10000 |
| replay_cancel_churn_n10000_s43_l1000 | baseline | n/a | 0.018992 | 0.018995 | 10000 |
| replay_cancel_churn_n10000_s43_l1000 | revised | n/a | 0.019419 | 0.019424 | 10000 |
| market-sell_controlled_bids_n10000_s43_l1000_p10 | baseline | 2.476642 | 1.269234 | 3.745879 | 1 |
| market-sell_controlled_bids_n10000_s43_l1000_p10 | revised | 0.023228 | 0.001274 | 0.024506 | 1 |
| market-sell_controlled_bids_n10000_s43_l1000_p100 | baseline | 2.527083 | 6.830055 | 9.353306 | 1 |
| market-sell_controlled_bids_n10000_s43_l1000_p100 | revised | 0.022831 | 0.012735 | 0.036205 | 1 |
| market-sell_controlled_bids_n10000_s43_l1000_p200 | baseline | 2.551204 | 6.835133 | 9.386340 | 1 |
| market-sell_controlled_bids_n10000_s43_l1000_p200 | revised | 0.022068 | 0.012461 | 0.034204 | 1 |
| queue-concentration_controlled_bids_n10000_s43_l4_p100 | revised | 0.021768 | 0.013791 | 0.035570 | 1 |
| queue-concentration_controlled_bids_n10000_s43_l1000_p100 | revised | 0.022594 | 0.014601 | 0.038350 | 1 |
| cancel-churn_anchored_cancel_churn_n10000_s43_l1 | baseline | n/a | 0.046235 | 0.046242 | 20002 |
| cancel-churn_anchored_cancel_churn_n10000_s43_l1 | revised | n/a | 0.042665 | 0.042669 | 20002 |
| replay_buildup_n10000_s44_l1000 | baseline | n/a | 5.210952 | 5.210959 | 10000 |
| replay_buildup_n10000_s44_l1000 | revised | n/a | 0.025985 | 0.025989 | 10000 |
| replay_crowded_n10000_s44_l1000 | baseline | n/a | 5.333202 | 5.333209 | 10000 |
| replay_crowded_n10000_s44_l1000 | revised | n/a | 0.025405 | 0.025408 | 10000 |
| replay_mixed_n10000_s44_l1000 | baseline | n/a | 0.767451 | 0.767455 | 10000 |
| replay_mixed_n10000_s44_l1000 | revised | n/a | 0.026826 | 0.026835 | 10000 |
| replay_sweep_n10000_s44_l1000 | baseline | n/a | 6.325530 | 6.325534 | 10000 |
| replay_sweep_n10000_s44_l1000 | revised | n/a | 0.032229 | 0.032239 | 10000 |
| replay_cancel_churn_n10000_s44_l1000 | baseline | n/a | 0.017906 | 0.017910 | 10000 |
| replay_cancel_churn_n10000_s44_l1000 | revised | n/a | 0.018699 | 0.018707 | 10000 |
| market-sell_controlled_bids_n10000_s44_l1000_p10 | baseline | 2.653890 | 1.317729 | 4.009241 | 1 |
| market-sell_controlled_bids_n10000_s44_l1000_p10 | revised | 0.024128 | 0.001305 | 0.025599 | 1 |
| market-sell_controlled_bids_n10000_s44_l1000_p100 | revised | 0.027869 | 0.015870 | 0.042511 | 1 |
| market-sell_controlled_bids_n10000_s44_l1000_p200 | revised | 0.022715 | 0.012961 | 0.035720 | 1 |
| queue-concentration_controlled_bids_n10000_s44_l4_p100 | revised | 0.021944 | 0.012693 | 0.034535 | 1 |
| queue-concentration_controlled_bids_n10000_s44_l1000_p100 | baseline | 2.708537 | 6.892590 | 9.528581 | 1 |
| queue-concentration_controlled_bids_n10000_s44_l1000_p100 | revised | 0.021766 | 0.013154 | 0.035638 | 1 |
| cancel-churn_anchored_cancel_churn_n10000_s44_l1 | baseline | n/a | 0.039858 | 0.039862 | 20002 |
| cancel-churn_anchored_cancel_churn_n10000_s44_l1 | revised | n/a | 0.038843 | 0.038854 | 20002 |
| replay_buildup_n100000_s42_l1000 | revised | n/a | 0.314935 | 0.314942 | 100000 |
| replay_crowded_n100000_s42_l1000 | revised | n/a | 0.285689 | 0.285696 | 100000 |
| replay_mixed_n100000_s42_l1000 | revised | n/a | 0.290096 | 0.290106 | 100000 |
| replay_sweep_n100000_s42_l1000 | revised | n/a | 0.363933 | 0.363939 | 100000 |
| replay_cancel_churn_n100000_s42_l1000 | baseline | n/a | 0.193284 | 0.193289 | 100000 |
| replay_cancel_churn_n100000_s42_l1000 | revised | n/a | 0.201017 | 0.201026 | 100000 |
| market-sell_controlled_bids_n100000_s42_l1000_p10 | revised | 0.246411 | 0.014442 | 0.261315 | 1 |
| market-sell_controlled_bids_n100000_s42_l1000_p100 | revised | 0.248601 | 0.145897 | 0.400213 | 1 |
| market-sell_controlled_bids_n100000_s42_l1000_p200 | revised | 0.246420 | 0.144914 | 0.388401 | 1 |
| queue-concentration_controlled_bids_n100000_s42_l4_p100 | revised | 0.247171 | 0.143733 | 0.392867 | 1 |
| queue-concentration_controlled_bids_n100000_s42_l1000_p100 | revised | 0.253066 | 0.147045 | 0.408071 | 1 |
| cancel-churn_anchored_cancel_churn_n100000_s42_l1 | baseline | n/a | 0.390773 | 0.390778 | 200002 |
| cancel-churn_anchored_cancel_churn_n100000_s42_l1 | revised | n/a | 0.388009 | 0.388020 | 200002 |
| replay_buildup_n100000_s43_l1000 | revised | n/a | 0.287297 | 0.287303 | 100000 |
| replay_crowded_n100000_s43_l1000 | revised | n/a | 0.276318 | 0.276325 | 100000 |
| replay_mixed_n100000_s43_l1000 | revised | n/a | 0.268093 | 0.268102 | 100000 |
| replay_sweep_n100000_s43_l1000 | revised | n/a | 0.347133 | 0.347145 | 100000 |
| replay_cancel_churn_n100000_s43_l1000 | baseline | n/a | 0.203848 | 0.203853 | 100000 |
| replay_cancel_churn_n100000_s43_l1000 | revised | n/a | 0.193329 | 0.193336 | 100000 |
| market-sell_controlled_bids_n100000_s43_l1000_p10 | revised | 0.246972 | 0.015892 | 0.265415 | 1 |
| market-sell_controlled_bids_n100000_s43_l1000_p100 | revised | 0.257541 | 0.147000 | 0.407706 | 1 |
| market-sell_controlled_bids_n100000_s43_l1000_p200 | revised | 0.256610 | 0.142999 | 0.398261 | 1 |
| queue-concentration_controlled_bids_n100000_s43_l4_p100 | revised | 0.248290 | 0.138293 | 0.389358 | 1 |
| queue-concentration_controlled_bids_n100000_s43_l1000_p100 | revised | 0.258308 | 0.146006 | 0.411500 | 1 |
| cancel-churn_anchored_cancel_churn_n100000_s43_l1 | baseline | n/a | 0.395951 | 0.395956 | 200002 |
| cancel-churn_anchored_cancel_churn_n100000_s43_l1 | revised | n/a | 0.390822 | 0.390835 | 200002 |
| replay_buildup_n100000_s44_l1000 | revised | n/a | 0.287432 | 0.287439 | 100000 |
| replay_crowded_n100000_s44_l1000 | revised | n/a | 0.279668 | 0.279675 | 100000 |
| replay_mixed_n100000_s44_l1000 | revised | n/a | 0.268599 | 0.268608 | 100000 |
| replay_sweep_n100000_s44_l1000 | revised | n/a | 0.350497 | 0.350505 | 100000 |
| replay_cancel_churn_n100000_s44_l1000 | baseline | n/a | 0.204677 | 0.204681 | 100000 |
| replay_cancel_churn_n100000_s44_l1000 | revised | n/a | 0.197884 | 0.197890 | 100000 |
| market-sell_controlled_bids_n100000_s44_l1000_p10 | revised | 0.244324 | 0.014981 | 0.259311 | 1 |
| market-sell_controlled_bids_n100000_s44_l1000_p100 | revised | 0.251469 | 0.143993 | 0.395366 | 1 |
| market-sell_controlled_bids_n100000_s44_l1000_p200 | revised | 0.251385 | 0.142934 | 0.393919 | 1 |
| queue-concentration_controlled_bids_n100000_s44_l4_p100 | revised | 0.247752 | 0.145086 | 0.390511 | 1 |
| queue-concentration_controlled_bids_n100000_s44_l1000_p100 | revised | 0.253639 | 0.144197 | 0.399684 | 1 |
| cancel-churn_anchored_cancel_churn_n100000_s44_l1 | baseline | n/a | 0.405726 | 0.405731 | 200002 |
| cancel-churn_anchored_cancel_churn_n100000_s44_l1 | revised | n/a | 0.388416 | 0.388429 | 200002 |

## Incomplete groups

| Case | Version | Phase | Repetitions | Reason |
| --- | --- | --- | ---: | --- |
| replay_sweep_n10000_s42_l1000 | baseline | memory | 3/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s42_l1000_p100 | baseline | memory | 2/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s42_l1000_p200 | baseline | memory | 2/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s42_l4_p100 | baseline | memory | 1/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s42_l1000_p100 | baseline | memory | 2/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n10000_s43_l1000 | baseline | memory | 3/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s43_l1000_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s43_l1000_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s43_l1000_p200 | baseline | memory | 2/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s43_l4_p100 | baseline | timing | 4/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s43_l4_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s43_l4_p100 | baseline | memory | 1/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s43_l1000_p100 | baseline | timing | 2/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s43_l1000_p100 | baseline | memory | 1/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n10000_s44_l1000 | baseline | memory | 3/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s44_l1000_p100 | baseline | timing | 4/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s44_l1000_p100 | baseline | memory | 1/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s44_l1000_p200 | baseline | timing | 4/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s44_l1000_p200 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n10000_s44_l1000_p200 | baseline | memory | 1/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s44_l4_p100 | baseline | timing | 4/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s44_l4_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s44_l4_p100 | baseline | memory | 1/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n10000_s44_l1000_p100 | baseline | memory | 2/5 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s42_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s42_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s42_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s42_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s42_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s42_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s42_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s42_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s42_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s42_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s42_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s42_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s42_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s42_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s42_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s42_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p10 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p10 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p10 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p10 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p200 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p200 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p200 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s42_l1000_p200 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l4_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l4_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l4_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l4_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l1000_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l1000_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l1000_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s42_l1000_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s43_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s43_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s43_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s43_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s43_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s43_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s43_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s43_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s43_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s43_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s43_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s43_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s43_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s43_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s43_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s43_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p10 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p10 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p10 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p10 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p200 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p200 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p200 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s43_l1000_p200 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l4_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l4_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l4_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l4_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l1000_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l1000_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l1000_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s43_l1000_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s44_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s44_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s44_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_buildup_n100000_s44_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s44_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s44_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s44_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_crowded_n100000_s44_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s44_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s44_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s44_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_mixed_n100000_s44_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s44_l1000 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s44_l1000 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s44_l1000 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| replay_sweep_n100000_s44_l1000 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p10 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p10 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p10 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p10 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p200 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p200 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p200 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| market-sell_controlled_bids_n100000_s44_l1000_p200 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l4_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l4_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l4_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l4_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l1000_p100 | baseline | timing | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l1000_p100 | baseline | latency | 0/1 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l1000_p100 | baseline | memory | 0/5 | Worker wall limit reached (60.000 seconds) |
| queue-concentration_controlled_bids_n100000_s44_l1000_p100 | baseline | diagnostics | 0/1 | Worker wall limit reached (60.000 seconds) |

## Optional million-event decision

One bounded mixed-workload million-event probe was feasible after mandatory coverage; no other million-event cases attempted. Actual states: {'completed': 5, 'stopped': 4}. See optional_audit.json for saved per-phase outcomes and elapsed time.
The optional probe is separate from required coverage. Its generated input is excluded from submission; settings, checksums, raw results and actual stops are retained.

## Findings and limits

Passive growth and full book construction expose the Baseline list scans. Revised replay is complete across all required seeds, while large Baseline stops prevent most large-book cross-version speedups.
Small-live-book cancellation streams are a different workload; the supplied alternating stream peaks at one active order. The controlled old-head churn stream captures retained inactive objects and final cleanup separately.
Controlled full-depth and oversized sales may touch every maker, but fewer price levels when orders concentrate at four prices. Sale residual and level counts were independently checked from ordered source bids.
Where Baseline memory stopped, no memory comparison is made even if timing is complete.
Exact actual elapsed command times and settings remain in each run's command_wall_time.json. No estimate replaces a missing measurement.

## Historical evidence gap

No contemporaneous initial failing TDD record was available; this historical requirement cannot be verified retroactively.

See REPORT.md at the submission root for algorithms, complexity, profiling, modeling assumptions and AI assistance.
